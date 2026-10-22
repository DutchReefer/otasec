import re
from pathlib import Path

from conftest import ROOT, make_item

from otasec import classify
from otasec.build import build_site, view_item
from otasec.normalize import no_em_dash
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")


def test_dutch_titles_translated_for_com(monkeypatch):
    nl = make_item(1, lang="nl", title="Lek in PLC-software verholpen")
    en = make_item(2, lang="en", title="PLC flaw fixed")
    irrelevant = make_item(3, lang="nl", cls=dict(make_item(3)["cls"], relevant=False))
    calls = []

    def fake(api_key, model, system, user, schema, **kw):
        calls.append(user)
        return {"results": [{"id": "id1", "title_en": "Flaw in PLC software fixed — update now"}]}

    monkeypatch.setattr(classify, "complete_json", fake)
    assert classify.translate_titles([nl, en, irrelevant], "key", "m") == 1
    assert '"id1"' in calls[0] and '"id2"' not in calls[0] and '"id3"' not in calls[0]
    assert nl["title_en"] == "Flaw in PLC software fixed, update now"
    assert view_item(nl, "en", TZ)["title"] == "Flaw in PLC software fixed, update now"
    assert view_item(nl, "nl", TZ)["title"] == "Lek in PLC-software verholpen"
    assert view_item(en, "en", TZ)["title"] == "PLC flaw fixed"
    # Already translated items are not sent again.
    assert classify.translate_titles([nl], "key", "m") == 0


def test_x_disabled_hides_x_everywhere(cfg, store):
    assert cfg.sources["x"]["enabled"] is False
    store.save_items([make_item(1, x_mentions=3)], 60)
    store.save_health({"sources": {"x": {"ok": True}}, "state": {}})
    build_site(cfg, store)
    for lang in ("en", "nl"):
        home = (cfg.dist_dir / lang / "index.html").read_text()
        about = (cfg.dist_dir / lang / "about" / "index.html").read_text()
        assert 'tag--x">shared' not in home and 'tag--x">3' not in home
        feed = (cfg.dist_dir / lang / "data" / "feed.json").read_text()
        assert '"x":0' in feed
        assert "X (recent search)" not in about and "op X" not in about and "posts on X" not in about
    assert "X_BEARER_TOKEN" not in (ROOT / ".github/workflows/pipeline.yml").read_text()


def test_tlp_label_colours_present():
    css = (ROOT / "static/style.css").read_text()
    for cat in ("incident", "threat", "advisory", "guidance", "research", "industry", "regulation"):
        assert f".tag--{cat}" in css
    theme = (ROOT / "static/theme.css").read_text()
    assert theme.count("--tlp-amber-bg") == 3  # light, dark toggle, dark via OS


def test_house_style_no_em_dashes():
    assert no_em_dash("Siemens — patch now") == "Siemens, patch now"
    assert no_em_dash("CVE scores 7–9") == "CVE scores 7-9"
    exts = {".py", ".html", ".css", ".js", ".yaml", ".yml", ".md", ".webmanifest", ".svg"}
    offenders = []
    for p in ROOT.rglob("*"):
        if p.is_file() and (p.suffix in exts or p.name == "htaccess") \
                and not {".git", "data", "dist", "tests"} & set(p.relative_to(ROOT).parts):
            if "—" in p.read_text(errors="ignore"):
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == []
