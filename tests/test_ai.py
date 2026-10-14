from datetime import datetime, timezone

from conftest import make_item

from otasec import briefing, classify


def test_heuristic_without_key():
    items = [make_item(1, cls=None, focus="broad", title="New SCADA flaw in water utility"),
             make_item(2, cls=None, focus="broad", title="Browser update fixes bugs"),
             make_item(3, cls=None, focus="ot", title="Anything from an OT source")]
    assert classify.classify_items(items, "", "m") == 3
    assert [i["cls"]["relevant"] for i in items] == [True, False, True]


def test_llm_classification_sanitises(monkeypatch):
    items = [make_item(1, cls=None, focus="ot"), make_item(2, cls=None, focus="broad")]

    def fake(api_key, model, system, user, schema, **kw):
        return {"results": [
            {"id": "id1", "relevant": False, "score": 250, "category": "bogus", "sectors": ["energy", "mars"],
             "vendors": [" Siemens ", ""], "summary_en": "One.", "summary_nl": "Een."},
            {"id": "id2", "relevant": False, "score": 10, "category": "industry", "sectors": [],
             "vendors": [], "summary_en": "x", "summary_nl": "y"},
            {"id": "unknown", "relevant": True, "score": 1, "category": "incident", "sectors": [],
             "vendors": [], "summary_en": "", "summary_nl": ""},
        ]}

    monkeypatch.setattr(classify, "complete_json", fake)
    assert classify.classify_items(items, "key", "model-x") == 2
    c1 = items[0]["cls"]
    assert c1["relevant"] is True          # OT-focused source is always kept
    assert c1["score"] == 100 and c1["category"] == "industry"
    assert c1["sectors"] == ["energy"] and c1["vendors"] == ["Siemens"]
    assert items[1]["cls"]["relevant"] is False


def test_briefing_assemble_drops_unknown_ids():
    items = [make_item(1, source="A", cves=["CVE-2026-1"]), make_item(2, source="B", x_mentions=2),
             make_item(3, source="A")]
    result = {
        "title_en": "T", "title_nl": "T-nl", "intro_en": "I", "intro_nl": "I-nl",
        "stories": [
            {"item_ids": ["id1", "id2", "id3", "ghost"], "heading_en": "H", "heading_nl": "H-nl",
             "summary_en": "S", "summary_nl": "S-nl", "takeaway_en": "K", "takeaway_nl": "K-nl"},
            {"item_ids": ["ghost"], "heading_en": "Made up", "heading_nl": "", "summary_en": "",
             "summary_nl": "", "takeaway_en": "", "takeaway_nl": ""},
        ],
    }
    b = briefing.assemble(result, items, "2026-10-14", "m")
    assert len(b["stories"]) == 1
    s = b["stories"][0]
    assert s["source_count"] == 2 and len(s["sources"]) == 3
    assert s["x_mentions"] == 2 and s["cves"] == ["CVE-2026-1"]
    assert s["i18n"]["nl"]["heading"] == "H-nl"


def test_briefing_due(store, cfg, monkeypatch):
    site = cfg.site
    fixed = datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc)  # 06:00 Amsterdam
    monkeypatch.setattr(briefing, "utcnow", lambda: fixed)
    assert briefing.due(store, site) is None                 # before publish hour
    fixed2 = datetime(2026, 10, 14, 6, 30, tzinfo=timezone.utc)  # 08:30 Amsterdam
    monkeypatch.setattr(briefing, "utcnow", lambda: fixed2)
    assert briefing.due(store, site) == "2026-10-14"
    store.save_briefing({"date": "2026-10-14", "i18n": {}, "stories": []})
    assert briefing.due(store, site) is None
    assert briefing.due(store, site, force=True) == "2026-10-14"
