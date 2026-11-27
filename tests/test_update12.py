"""Update 12: English headlines get a Dutch title on otasec.nl (title_nl)."""
import json

from conftest import make_item

from otasec import classify
from otasec.build import build_site, view_item
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")


def _fake(results, calls):
    def fake(api_key, model, system, user, schema, **kw):
        calls.append({"system": system, "user": user, "schema": schema})
        return {"results": results}
    return fake


def test_english_titles_translated_for_nl(monkeypatch):
    en = make_item(1, lang="en", title="Ransomware hits water utility — patch now")
    nl = make_item(2, lang="nl", title="Lek in PLC-software verholpen")
    irrelevant = make_item(3, lang="en", cls=dict(make_item(3)["cls"], relevant=False))
    calls = []
    monkeypatch.setattr(classify, "complete_json", _fake(
        [{"id": "id1", "title_nl": "Ransomware treft waterbedrijf — patch nu"}], calls))

    assert classify.translate_titles([en, nl, irrelevant], "key", "m", target="nl") == 1
    sent = json.loads(calls[0]["user"])
    assert [s["id"] for s in sent] == ["id1"]
    assert "Dutch" in calls[0]["system"]
    assert calls[0]["schema"]["properties"]["results"]["items"]["required"] == ["id", "title_nl"]
    assert en["title_nl"] == "Ransomware treft waterbedrijf, patch nu"  # em dash scrubbed
    assert "title_en" not in en

    assert view_item(en, "nl", TZ)["title"] == "Ransomware treft waterbedrijf, patch nu"
    assert view_item(en, "en", TZ)["title"] == "Ransomware hits water utility — patch now"
    assert view_item(nl, "nl", TZ)["title"] == "Lek in PLC-software verholpen"
    # Already translated items are not sent again.
    assert classify.translate_titles([en], "key", "m", target="nl") == 0


def test_only_items_in_the_feed_window_are_translated(monkeypatch):
    new = make_item(1, lang="en", published="2026-11-20T10:00:00Z")
    old = make_item(2, lang="en", published="2026-09-01T10:00:00Z")
    calls = []
    monkeypatch.setattr(classify, "complete_json", _fake([], calls))
    classify.translate_titles([new, old], "key", "m", target="nl", since="2026-10-28T00:00:00Z")
    sent = [s["id"] for s in json.loads(calls[0]["user"])]
    assert sent == ["id1"]


def test_dutch_to_english_still_works(monkeypatch):
    nl = make_item(1, lang="nl", title="Lek in PLC-software verholpen")
    calls = []
    monkeypatch.setattr(classify, "complete_json", _fake(
        [{"id": "id1", "title_en": "Flaw in PLC software fixed"}], calls))
    assert classify.translate_titles([nl], "key", "m") == 1  # default target is English
    assert view_item(nl, "en", TZ)["title"] == "Flaw in PLC software fixed"
    assert "title_nl" not in nl


def test_bad_model_output_is_ignored(monkeypatch):
    en = make_item(1, lang="en", title="PLC flaw fixed")
    monkeypatch.setattr(classify, "complete_json", _fake(
        [{"id": "other", "title_nl": "x"}, "not a dict", {"id": "id1", "title_nl": ""}], []))
    assert classify.translate_titles([en], "key", "m", target="nl") == 0
    assert "title_nl" not in en
    assert classify.translate_titles([en], "key", "m", target="de") == 0
    assert classify.translate_titles([en], "", "m", target="nl") == 0


def test_nl_site_and_feed_use_dutch_title(cfg, store, monkeypatch):
    en = make_item(1, lang="en", title="PLC flaw fixed")
    en["title_nl"] = "Lek in PLC verholpen"
    store.save_items([en], 60)
    store.save_health({"sources": {}, "state": {}})
    build_site(cfg, store)
    nl_home = (cfg.dist_dir / "nl" / "index.html").read_text()
    en_home = (cfg.dist_dir / "en" / "index.html").read_text()
    assert "Lek in PLC verholpen" in nl_home and "Lek in PLC verholpen" not in en_home
    assert "PLC flaw fixed" in en_home
    nl_feed = (cfg.dist_dir / "nl" / "data" / "feed.json").read_text()
    assert "Lek in PLC verholpen" in nl_feed
