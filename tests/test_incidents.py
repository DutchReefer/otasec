import math
import re

import pytest
from conftest import ROOT

from otasec.build import build_site
from otasec.geo import CONTINENTS, project, spread, world
from otasec.i18n import STRINGS
from otasec.incidents import IncidentError, fmt_date, load_incidents, view_incidents


def test_dataset_is_valid_and_covers_the_world():
    inc = load_incidents(sectors=STRINGS["en"]["sectors"])
    assert len(inc) >= 40
    assert {i["continent"] for i in inc} == set(CONTINENTS)
    assert min(str(i["date"])[:4] for i in inc) == "2008"
    assert [str(i["date"]) for i in inc] == sorted((str(i["date"]) for i in inc), reverse=True)
    text = (ROOT / "config/incidents.yaml").read_text()
    assert "—" not in text and "–" not in text


@pytest.mark.parametrize("patch, msg", [
    ({"sources": [{"title": "x", "url": "javascript:alert(1)"}]}, "https"),
    ({"sources": [{"title": "x", "url": "http://example.com/"}]}, "https"),
    ({"continent": "atlantis"}, "continent"),
    ({"impact": "catastrophic"}, "impact"),
    ({"date": "Dec 2015"}, "date"),
    ({"lat": 123}, "lat/lon"),
])
def test_bad_entries_are_rejected(tmp_path, patch, msg):
    import yaml
    good = yaml.safe_load((ROOT / "config/incidents.yaml").read_text())[0]
    p = tmp_path / "incidents.yaml"
    p.write_text(yaml.safe_dump([{**good, **patch}]), encoding="utf-8")
    with pytest.raises(IncidentError, match=msg):
        load_incidents(p)


def test_duplicate_ids_rejected(tmp_path):
    import yaml
    good = yaml.safe_load((ROOT / "config/incidents.yaml").read_text())[0]
    p = tmp_path / "incidents.yaml"
    p.write_text(yaml.safe_dump([good, good]), encoding="utf-8")
    with pytest.raises(IncidentError, match="unique"):
        load_incidents(p)


def test_projection_lands_on_the_right_continent():
    w = world()
    x0, y0, x1, y1 = w["continents"]["europe"]["bbox"]
    x, y = project(4.9, 52.37)                     # Amsterdam
    assert x0 <= x <= x1 and y0 <= y <= y1
    x, y = project(151.2, -33.9)                   # Sydney
    ox0, oy0, ox1, oy1 = w["continents"]["oceania"]["bbox"]
    assert ox0 <= x <= ox1 and oy0 <= y <= oy1


def test_spread_keeps_blips_apart():
    pts = spread([(100, 100)] * 6 + [(300, 300)], 10)
    assert pts[0] == (100, 100) and pts[-1] == (300, 300)
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            assert math.dist(a, b) >= 9.9


def test_dates_formatted_per_language():
    assert fmt_date("2015-12-23", "en") == "23 Dec 2015"
    assert fmt_date("2015-12", "nl") == "dec 2015"
    assert fmt_date("2008", "en") == "2008"


def test_incidents_page_in_both_languages(cfg, store):
    build_site(cfg, store)
    inc = load_incidents()
    for lang, title in (("en", "OT incident map"), ("nl", "OT-incidentenkaart")):
        out = cfg.dist_dir / lang
        page = (out / "incidents" / "index.html").read_text()
        assert title in page
        assert page.count('class="inc"') == len(inc)
        assert page.count('class="blip blip--') == len(inc)
        assert all(f'id="{i["id"]}"' in page for i in inc)
        assert page.count('class="land"') == len(CONTINENTS)
        assert "javascript:" not in page and "—" not in page
        external = [h for h in re.findall(r'href="([^"]+)"', page) if ":" in h]
        assert external and all(h.startswith("https://") for h in external)
        assert 'style="' not in page                      # CSP: no inline styles
        assert (out / "assets" / "incidents.js").is_file()
        assert 'href="/incidents/"' in (out / "index.html").read_text()   # nav link
        assert "/incidents/</loc>" in (out / "sitemap.xml").read_text()
    nl = (cfg.dist_dir / "nl" / "incidents" / "index.html").read_text()
    assert "Oekraïne" in nl and "Operationele verstoring" in nl


def test_view_has_zoom_box_containing_every_blip():
    inc = load_incidents()
    v = view_incidents(inc, "en", STRINGS["en"])
    for c in v["continents"]:
        x, y, w, h = c["zoom"]
        for i in v["items"]:
            if i["continent"] == c["key"]:
                assert x <= i["tx"] <= x + w and y <= i["ty"] <= y + h, (c["key"], i["id"])


def test_incidents_js_is_csp_safe():
    js = (ROOT / "static/incidents.js").read_text()
    assert "innerHTML" not in js and "eval(" not in js and 'setAttribute("style"' not in js
