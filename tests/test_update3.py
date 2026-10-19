import json
from datetime import date, timedelta

import httpx
from conftest import FIXTURES, make_item

from otasec import csaf, xsource
from otasec.build import collapse, dedupe_sources
from otasec.store import utcnow

FEED = {"id": "cisa-ics", "name": "CISA ICS Advisories", "focus": "ot", "kind": "advisory",
        "repo": "cisagov/CSAF", "branch": "develop", "path": "csaf_files/OT/white", "lookback_days": 7}


def test_release_date_from_name():
    assert csaf.release_date("icsa-26-288-02.json") == date(2026, 10, 15)
    assert csaf.release_date("icsa-26-288-02.json.asc") is None
    names = ["icsa-26-280-01.json", "icsa-26-288-02.json", "icsa-26-288-02.json.sha512", "README.md"]
    assert csaf.recent_names(names, date(2026, 10, 10)) == ["icsa-26-288-02.json"]


def test_csaf_to_item():
    doc = json.loads((FIXTURES / "csaf_icsa-26-288-02.json").read_text())
    it = csaf.to_item(doc, FEED)
    assert it["url"] == "https://www.cisa.gov/news-events/ics-advisories/icsa-26-288-02"
    assert it["title"].startswith("ICSA-26-288-02: ")
    assert it["published"] == "2026-10-15T06:00:00Z"
    assert "CVE-2026-107617" in it["cves"] and "Sectors:" in it["excerpt"]
    assert it["kind"] == "advisory" and it["focus"] == "ot"


def test_csaf_fetch_with_mocked_github(monkeypatch):
    today = utcnow().date()
    doy = (today - date(today.year, 1, 1)).days + 1
    fresh = f"icsa-{today.year % 100:02d}-{doy:03d}-01.json"
    old = f"icsa-{today.year % 100:02d}-{max(1, doy - 30):03d}-01.json"
    body = json.loads((FIXTURES / "csaf_icsa-26-288-02.json").read_text())
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if "/contents/" in request.url.path:
            return httpx.Response(200, json=[{"name": str(today.year), "type": "dir", "sha": "abc"}])
        if request.url.path.endswith("/git/trees/abc"):
            return httpx.Response(200, json={"tree": [{"path": n, "type": "blob"}
                                                      for n in (fresh, fresh + ".asc", old)]})
        if request.url.host == "raw.githubusercontent.com":
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    monkeypatch.setenv("GITHUB_TOKEN", "t0k")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    items, status = csaf.fetch(client, FEED)
    assert status["ok"] and len(items) == 1
    assert sum("raw.githubusercontent.com" in u for u in seen) == 1  # only the fresh .json


def _v(n, **kw):
    base = {"id": f"v{n}", "url": f"https://e.com/{n}", "title": f"T{n}", "source": "Siemens ProductCERT",
            "source_id": "siemens", "published": "2026-10-14T10:00:00Z", "day": "2026-10-14",
            "day_label": "14 Oct", "kind": "advisory", "category": "advisory", "cves": [f"CVE-2026-{n}"]}
    base.update(kw)
    return base


def test_collapse_groups_patch_day():
    items = [_v(1), _v(2, kind="news", source_id="ic", source="Industrial Cyber"), _v(3), _v(4), _v(5),
             _v(6, day="2026-10-13")]
    rows = collapse(items)
    assert len(rows) == 3
    g = rows[0]
    assert g["group"] and g["count"] == 4 and g["cves"] == ["CVE-2026-1", "CVE-2026-3", "CVE-2026-4", "CVE-2026-5"]
    assert rows[1]["id"] == "v2" and rows[2]["id"] == "v6"
    assert len(collapse(items[:3])) == 3  # below the threshold nothing is grouped


def test_dedupe_sources():
    out = dedupe_sources([{"name": "Security.NL", "url": "a"}, {"name": "IC", "url": "b"},
                          {"name": "Security.NL", "url": "c"}])
    assert [(s["name"], len(s["links"])) for s in out] == [("Security.NL", 2), ("IC", 1)]


def test_x_rename_and_homepage_skip():
    feed_item = make_item(1, url="https://industrialcyber.co/a", source="Industrial Cyber")
    x_item = make_item(2, url="https://industrialcyber.co/b", source="industrialcyber.co", source_id="x")
    xsource.rename_sources([feed_item, x_item])
    assert x_item["source"] == "Industrial Cyber"
    payload = {"data": [{"id": "1", "author_id": "u", "text": "t",
                         "entities": {"urls": [{"expanded_url": "https://www.cisa.gov/"}]}}], "includes": {}}
    assert xsource.posts_to_signals(payload) == []


def test_x_display_names():
    a = make_item(1, url="https://csrc.nist.gov/pubs/x", source="csrc.nist.gov", source_id="x")
    b = make_item(2, url="https://www.securityweek.com/a", source="securityweek.com", source_id="x")
    c = make_item(3, url="https://unknown.example/a", source="unknown.example", source_id="x")
    xsource.rename_sources([a, b, c], {"nist.gov": "NIST", "securityweek.com": "SecurityWeek"})
    assert (a["source"], b["source"], c["source"]) == ("NIST", "SecurityWeek", "unknown.example")
