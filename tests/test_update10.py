"""Update 10: logo version 2 (chamfered wordmark, gear and signal symbol)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import brand_draw as draw  # noqa: E402

BRAND = ROOT / "static" / "brand"
ORANGE = draw.ORANGE


def test_committed_brand_files_match_the_drawing():
    """The SVGs in the repo are exactly what tools/brand_draw.py draws."""
    assert (ROOT / "brand" / "lockup.svg").read_text() == draw.lockup_svg()
    assert (BRAND / "otasec-lockup-reverse.svg").read_text() == draw.lockup_svg(draw.SAND)
    assert (BRAND / "otasec-wordmark.svg").read_text() == draw.wordmark_svg()
    assert (BRAND / "otasec-symbol.svg").read_text() == draw.symbol_svg()
    assert (ROOT / "static" / "favicon.svg").read_text() == draw.favicon_svg()


def test_orange_is_a_signal_not_a_letter_accent():
    """Orange lives in the symbol's signal arcs; the wordmark is one colour."""
    for name in ("otasec-wordmark.svg", "otasec-wordmark-reverse.svg", "otasec-wordmark-compact.svg"):
        assert ORANGE not in (BRAND / name).read_text(), name
    for name in ("otasec-lockup.svg", "otasec-lockup-reverse.svg", "otasec-symbol.svg"):
        assert (BRAND / name).read_text().count(ORANGE) == 1, name
    assert (ROOT / "static" / "favicon.svg").read_text().count(ORANGE) == 1


def test_logo_files_are_plain_paths():
    """No fonts, strokes, transforms, clip paths or scripts in the logo files."""
    for name in ("otasec-lockup.svg", "otasec-lockup-reverse.svg", "otasec-wordmark.svg", "otasec-symbol.svg"):
        svg = (BRAND / name).read_text()
        for banned in ("<text", "stroke", "transform", "clip-path", "<script", "href"):
            assert banned not in svg, (name, banned)
        assert "<title>" in svg and 'role="img"' in svg


def test_header_and_footer_show_the_lockup_at_its_true_proportions():
    base = (ROOT / "templates" / "base.html").read_text()
    logos = re.findall(r'<img class="(brand__logo|footer__logo)" src="/assets/brand/([\w-]+\.svg)\?v=\{\{ v \}\}"'
                       r'[^>]* width="(\d+)" height="(\d+)"', base)
    assert [(c, f) for c, f, _, _ in logos] == [("brand__logo", "otasec-lockup-reverse.svg"),
                                                ("footer__logo", "otasec-lockup-reverse.svg")]
    for _, _, w, h in logos:
        assert (int(w), int(h)) == draw.lockup_size(int(h))


def test_favicons_are_versioned_so_browsers_pick_up_the_new_icon():
    base = (ROOT / "templates" / "base.html").read_text()
    for href in ("/favicon.ico?v={{ v }}", "/assets/favicon.svg?v={{ v }}", "/apple-touch-icon.png?v={{ v }}"):
        assert f'href="{href}"' in base, href
