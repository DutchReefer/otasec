"""Security hardening (update 6): URL parsing, X trust, LLM output, size caps, RSS."""
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest
from conftest import make_item

from otasec import briefing, classify, xsource
from otasec.build import build_site
from otasec.csaf import to_item
from otasec.feeds import ResponseTooLarge, fetch_one, get_limited
from otasec.normalize import clean_text, clean_url, safe_netloc, safe_url, scrub_model_text
from otasec.store import iso, utcnow

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("url", [
    "https://evil.com\\.cisa.gov/a",          # browser goes to evil.com, Python sees *.cisa.gov
    "https://www.cisa.gov@evil.com/a",        # user-info trick
    "https://evil.com%2f.cisa.gov/a",
    "https://127.0.0.1/a",                    # IP literals
    "https://[::1]/a",
    "javascript:alert(1)",
    "data:text/html,x",
    "https://exa mple.com/a",
    "https://example.com/a‮",            # bidi override
    "https://localhost/a",
    "https://example.com:99999x/a",
])
def test_unsafe_urls_rejected(url):
    assert clean_url(url) == ""
    assert safe_url(url) == ""


def test_safe_urls_kept():
    assert clean_url("HTTPS://WWW.CISA.gov/news?utm_source=x&id=1#top") == "https://www.cisa.gov/news?id=1"
    assert safe_url("https://www.cisa.gov/news") == "https://www.cisa.gov/news"
    assert safe_netloc("bücher.de") == "xn--bcher-kva.de"
    assert safe_netloc("example.com:8443") == "example.com:8443"


def test_backslash_host_is_not_trusted():
    trusted = {"cisa.gov"}
    assert not xsource.is_trusted("evil.com\\.cisa.gov", trusted)
    payload = {"data": [{"id": "1", "author_id": "u", "text": "t",
                         "entities": {"urls": [{"expanded_url": "https://evil.com\\.cisa.gov/x",
                                                "title": "Fake CISA"}]}}], "includes": {}}
    assert xsource.posts_to_signals(payload) == []


def test_user_content_subdomains_not_trusted():
    trusted = {"microsoft.com", "cloud.google.com", "siemens.com"}
    assert xsource.is_trusted("msrc.microsoft.com", trusted)
    assert xsource.is_trusted("www.siemens.com", trusted)
    for host in ("techcommunity.microsoft.com", "answers.microsoft.com",
                 "storage.cloud.google.com", "support.community.siemens.com"):
        assert not xsource.is_trusted(host, trusted), host
    assert not xsource.is_trusted("blog.siemens.com", trusted, {"blog.siemens.com"})


def test_x_post_text_never_becomes_a_headline():
    trusted = {"nist.gov"}
    sig = {"post_id": "1", "url": "https://csrc.nist.gov/x", "host": "csrc.nist.gov", "title": "",
           "description": "", "text": "BREAKING: send BTC to ... (attacker text)",
           "created_at": None, "handle": "a", "engagement": 0}
    assert xsource.merge_signals([], [sig], trusted) == []
    sig2 = dict(sig, title="SP 800-82r4", description="")
    new = xsource.merge_signals([], [sig2], trusted)
    assert new[0]["title"] == "SP 800-82r4" and new[0]["excerpt"] == ""


def test_scrub_model_text():
    out = scrub_model_text("Patch now at https://evil.example/fix or www.evil.example ‮ok\x00", 500)
    assert "http" not in out and "www." not in out and "‮" not in out and "\x00" not in out
    assert len(scrub_model_text("word " * 500, 100)) <= 101


def test_classifier_output_is_scrubbed(monkeypatch):
    it = make_item(1, cls=None, focus="broad")
    reply = {"results": [{"id": "id1", "relevant": True, "score": 90, "category": "advisory",
                          "sectors": ["energy"], "vendors": ["Siemens https://evil.example", "x" * 500],
                          "summary_en": "Visit https://evil.example/patch now. " + "a " * 400,
                          "summary_nl": "Zie www.evil.example"}]}
    monkeypatch.setattr(classify, "complete_json", lambda *a, **k: reply)
    classify.classify_items([it], "key", "model")
    s = it["cls"]["summary"]
    assert "evil" not in s["en"] and "evil" not in s["nl"]
    assert len(s["en"]) <= classify.SUMMARY_MAX + 1
    assert all("http" not in v and len(v) <= 61 for v in it["cls"]["vendors"])


def test_prompts_mark_input_as_untrusted():
    assert "untrusted" in classify.SYSTEM and "untrusted" in briefing.SYSTEM


def test_briefing_output_is_scrubbed():
    items = [make_item(1)]
    result = {"title_en": "T https://evil.example", "title_nl": "T", "intro_en": "I", "intro_nl": "I",
              "stories": [{"item_ids": ["id1"], "heading_en": "H www.evil.example", "heading_nl": "H",
                           "summary_en": "S " * 2000, "summary_nl": "S", "takeaway_en": "Go to http://x.example",
                           "takeaway_nl": "T"}] * 30}
    b = briefing.assemble(result, items, "2026-10-19", "m")
    assert len(b["stories"]) == briefing.MAX_STORIES_HARD
    en = b["stories"][0]["i18n"]["en"]
    assert "evil" not in en["heading"] and "http" not in en["takeaway"]
    assert len(en["summary"]) <= briefing.LIMITS["summary"] + 1
    assert "evil" not in b["i18n"]["en"]["title"]


def test_feed_size_cap():
    big = b"x" * 2048
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=big)))
    with pytest.raises(ResponseTooLarge):
        get_limited(client, "https://example.com/feed", limit=1024)
    assert get_limited(client, "https://example.com/feed", limit=4096) == (200, big)
    import otasec.feeds as feeds_mod
    old = feeds_mod.MAX_FEED_BYTES
    try:
        feeds_mod.MAX_FEED_BYTES = 1024
        get_limited.__defaults__ = (None, 1024)
        _, items, status = fetch_one(client, {"id": "f", "name": "F", "url": "https://example.com/feed"})
    finally:
        feeds_mod.MAX_FEED_BYTES = old
        get_limited.__defaults__ = (None, old)
    assert items == [] and status["ok"] is False and "larger than" in status["error"]


def test_csaf_self_link_must_be_cisa_host_and_date_not_future():
    doc = {"document": {"title": "Vendor PLC", "tracking": {"id": "ICSA-1",
                                                             "initial_release_date": "2099-01-01T00:00:00Z"},
                        "references": [{"category": "self", "url": "https://evil.example/cisa.gov/x"}]}}
    assert to_item(doc, {"id": "cisa-ics", "name": "CISA"}) is None
    doc["document"]["references"] = [{"category": "self", "url": "https://www.cisa.gov/news-events/ics-advisories/icsa-1"}]
    it = to_item(doc, {"id": "cisa-ics", "name": "CISA"})
    assert it and it["published"] <= iso(utcnow())


def test_control_chars_do_not_break_rss(cfg, store):
    store.save_items([make_item(1, title="Bad\x01 \x0bchars￾ here", url="https://example.com/a/1")], 60)
    store.items_path.write_text(store.items_path.read_text().replace("Bad", "Bad\\u0002"))  # pre-existing dirty data
    build_site(cfg, store)
    for lang in ("en", "nl"):
        ET.parse(cfg.dist_dir / lang / "news.xml")   # raises on invalid XML
    assert clean_text("a\x00b​c") == "abc"


def test_htaccess_security_headers():
    ht = (ROOT / "templates" / "htaccess").read_text()
    for needle in ("Strict-Transport-Security", "Content-Security-Policy", "frame-ancestors 'none'",
                   "X-Content-Type-Options", "Options -Indexes", r"RedirectMatch 404 /\.(?!well-known/)"):
        assert needle in ht
    assert "unsafe-inline" not in ht and "unsafe-eval" not in ht


def test_workflows_least_privilege():
    pipe = (ROOT / ".github" / "workflows" / "pipeline.yml").read_text()
    tests = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "permissions: {}" in pipe and "contents: read" in tests
    assert "sftp:auto-confirm" not in pipe and "ftp:ssl-force yes" in pipe
    assert "--require-hashes" in pipe and "--require-hashes" in tests
    import re
    for wf in (pipe, tests):
        for ref in re.findall(r"uses:\s*(\S+)", wf):
            assert re.search(r"@[0-9a-f]{40}$", ref), f"action not pinned to a SHA: {ref}"
    build = pipe.split("  publish:")[0]
    assert "FTP_PASSWORD" not in build and "persist-credentials: false" in build
