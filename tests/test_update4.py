from datetime import datetime, timezone

from conftest import make_item

from otasec import briefing
from otasec.build import build_site

NOW = datetime(2026, 10, 19, 6, 30, tzinfo=timezone.utc)  # 08:30 Amsterdam


def _story(ids):
    return {"sources": [{"id": i, "name": "S", "url": f"https://e.com/{i}", "title": i} for i in ids],
            "source_count": 1, "x_mentions": 0, "cves": [],
            "i18n": {l: {"heading": f"H {ids[0]}", "summary": "s", "takeaway": "k"} for l in ("en", "nl")}}


def _fake_llm(calls):
    def fake(api_key, model, system, user, schema, **kw):
        calls.append(user)
        import json, re
        ids = re.findall(r'"id": "([^"]+)"', user)
        return {"title_en": "T", "title_nl": "T", "intro_en": "I", "intro_nl": "I",
                "stories": [{"item_ids": ids, "heading_en": "New", "heading_nl": "Nieuw", "summary_en": "s",
                             "summary_nl": "s", "takeaway_en": "k", "takeaway_nl": "k"}]}
    return fake


def test_used_items_are_not_reused(store, cfg, monkeypatch):
    monkeypatch.setattr(briefing, "utcnow", lambda: NOW)
    store.save_briefing({"date": "2026-10-18", "stories": [_story(["id1"])], "i18n": {}})
    items = [make_item(1, published="2026-10-18T20:00:00Z"), make_item(2, published="2026-10-18T21:00:00Z")]
    calls = []
    monkeypatch.setattr(briefing, "complete_json", _fake_llm(calls))
    b = briefing.generate(store, items, cfg.site, "key", "m")
    assert [s["id"] for s in b["stories"][0]["sources"]] == ["id2"]
    assert '"id1"' not in calls[0]
    assert "2026-10-18: H id1" in briefing.recent_headings(store.load_briefings(), before="2026-10-19")


def test_quiet_day_then_upgrade_when_news_arrives(store, cfg, monkeypatch):
    monkeypatch.setattr(briefing, "utcnow", lambda: NOW)
    store.save_briefing({"date": "2026-10-18", "stories": [_story(["id1"])], "i18n": {}})
    calls = []
    monkeypatch.setattr(briefing, "complete_json", _fake_llm(calls))

    q = briefing.generate(store, [make_item(1, published="2026-10-18T20:00:00Z")], cfg.site, "key", "m")
    assert q["quiet"] and q["extra"]["en"] and q["extra"]["nl"] and calls == []
    # Next run, still nothing new: quiet edition is left alone.
    assert briefing.generate(store, [make_item(1, published="2026-10-18T20:00:00Z")], cfg.site, "key", "m") is None
    # News arrives later that day: the quiet edition is replaced.
    b = briefing.generate(store, [make_item(1, published="2026-10-18T20:00:00Z"),
                                  make_item(3, published="2026-10-19T06:00:00Z")], cfg.site, "key", "m")
    assert not b.get("quiet") and store.load_briefing("2026-10-19")["stories"]
    # A real briefing is not regenerated without --force.
    assert briefing.generate(store, [make_item(4)], cfg.site, "key", "m") is None


def test_quiet_entries_rotate_without_repeats():
    entries = briefing.load_quiet_entries()
    assert len(entries) >= 20 and all(e["kind"] in ("joke", "wisdom") for e in entries)
    seen, history = [], []
    for day in range(len(entries)):
        b = briefing.quiet_briefing(f"2026-11-{day + 1:02d}", history, entries)
        history.append(b)
        seen.append(b["extra"]["en"])
    assert len(set(seen)) == len(entries)


def test_quiet_day_renders(cfg, store, monkeypatch):
    monkeypatch.setattr(briefing, "utcnow", lambda: NOW)
    store.save_items([make_item(1)], 60)
    store.save_briefing(briefing.quiet_briefing("2026-10-19", [], briefing.load_quiet_entries()))
    build_site(cfg, store)
    nl = (cfg.dist_dir / "nl" / "briefing" / "2026-10-19" / "index.html").read_text()
    en_archive = (cfg.dist_dir / "en" / "briefings" / "index.html").read_text()
    assert "Een rustige dag in OT-security" in nl and "OT-grap van de dag" in nl
    assert "Quiet day" in en_archive
    assert "Read the full briefing" not in (cfg.dist_dir / "en" / "index.html").read_text()
