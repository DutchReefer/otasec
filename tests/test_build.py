import json
from datetime import timedelta

from conftest import make_item

from otasec.build import build_site
from otasec.store import iso, utcnow


def _seed(store):
    items = [
        make_item(1, title="<script>alert(1)</script> PLC flaw", cves=["CVE-2026-12345"]),
        make_item(2, url="javascript:alert(1)", title="Bad link"),
        make_item(3, cls=dict(make_item(3)["cls"], relevant=False), title="Irrelevant IT news"),
        make_item(4, published=iso(utcnow() - timedelta(days=45)), title="Too old for feed"),
    ]
    store.save_items(items, 60)
    store.save_briefing({
        "date": utcnow().date().isoformat(), "published": iso(utcnow()), "model": "m", "item_count": 2,
        "i18n": {"en": {"title": "Daily <b>title</b>", "intro": "Intro"}, "nl": {"title": "Dagtitel", "intro": "Inleiding"}},
        "stories": [{"sources": [{"id": "id1", "name": "Source 1", "url": "https://example.com/a/1", "title": "x"},
                                 {"id": "id2", "name": "Evil", "url": "javascript:alert(1)", "title": "y"}],
                     "source_count": 2, "x_mentions": 0, "cves": [],
                     "i18n": {"en": {"heading": "Story", "summary": "Sum", "takeaway": "Patch now"},
                              "nl": {"heading": "Verhaal", "summary": "Sam", "takeaway": "Patch nu"}}}],
    })


def test_build_both_languages(cfg, store):
    _seed(store)
    build_site(cfg, store)
    for lang in ("en", "nl"):
        out = cfg.dist_dir / lang
        for f in ("index.html", "about/index.html", "briefings/index.html", "404.html", "rss.xml",
                  "news.xml", "sitemap.xml", "robots.txt", ".htaccess", "assets/style.css",
                  "assets/app.js", "data/feed.json"):
            assert (out / f).is_file(), f"{lang}/{f}"
        home = (out / "index.html").read_text()
        assert "<script>alert(1)</script>" not in home
        assert "&lt;script&gt;" in home
        assert "javascript:alert" not in home
        assert "Irrelevant IT news" not in home
        assert "Too old for feed" not in home
        assert 'hreflang="nl-NL" href="https://otasec.nl/"' in home
        feed = json.loads((out / "data" / "feed.json").read_text())
        assert len(feed["items"]) == 2
        assert all(i["url"] == "" or i["url"].startswith("https://") for i in feed["items"])

    en_home = (cfg.dist_dir / "en" / "index.html").read_text()
    nl_home = (cfg.dist_dir / "nl" / "index.html").read_text()
    assert "EN summary." in en_home and "NL samenvatting." in nl_home
    assert "Daily &lt;b&gt;title&lt;/b&gt;" in en_home and "Dagtitel" in nl_home
    briefing_page = next((cfg.dist_dir / "nl" / "briefing").glob("*/index.html")).read_text()
    assert "Patch nu" in briefing_page and "javascript:" not in briefing_page
