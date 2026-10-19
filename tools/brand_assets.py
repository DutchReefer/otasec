"""Derive the website's brand assets from the master SVGs in brand/.

    python tools/brand_assets.py

Masters (from the OTASEC brand work): brand/wordmark.svg, brand/symbol.svg,
brand/favicon.svg. Outputs go to static/ and are committed, so the pipeline
itself never needs Cairo.
"""
import re
from pathlib import Path

import cairosvg

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "brand", ROOT / "static" / "brand"
PETROL, SAND, ORANGE = "#0B3C49", "#EFEBE3", "#E8702A"
OUT.mkdir(parents=True, exist_ok=True)

wordmark = (SRC / "wordmark.svg").read_text()
symbol = (SRC / "symbol.svg").read_text()
favicon = (SRC / "favicon.svg").read_text()


def reverse(svg: str) -> str:
    return svg.replace(f'fill="{PETROL}"', f'fill="{SAND}"')


def compact(svg: str) -> str:
    """Wordmark without the 'OT ASSET SECURITY' tagline (the last two paths, y >= 244)."""
    paths = re.findall(r"\s*<path [^>]*/>", svg)
    head = svg.split("<path", 1)[0].replace('viewBox="-6 -6 1328 294.0"', 'viewBox="-6 -6 1328 212"') \
        .replace('height="294"', 'height="212"').replace("OTASEC – OT Asset Security", "OTASEC")
    return head + "".join(paths[:3]) + "\n</svg>\n"


files = {
    "otasec-wordmark.svg": wordmark,
    "otasec-wordmark-reverse.svg": reverse(wordmark),
    "otasec-wordmark-compact.svg": compact(wordmark),
    "otasec-wordmark-compact-reverse.svg": reverse(compact(wordmark)),
    "otasec-symbol.svg": symbol,
    "otasec-symbol-reverse.svg": reverse(symbol),
}
for name, content in files.items():
    (OUT / name).write_text(content)
(ROOT / "static" / "favicon.svg").write_text(favicon)

# Social card: sand wordmark centred on petrol (same composition as the brand OG image).
inner = reverse(wordmark).split(">", 1)[1].rsplit("</svg>", 1)[0]
inner = re.sub(r"<title>.*?</title>", "", inner)
scale = 860 / 1328
og = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">'
      f'<rect width="1200" height="630" fill="{PETROL}"/>'
      f'<g transform="translate({(1200 - 860) / 2} {(630 - 294 * scale) / 2:.1f}) scale({scale:.4f}) translate(6 6)">{inner}</g>'
      f'</svg>')
(OUT / "og-image.svg").write_text(og)
cairosvg.svg2png(bytestring=og.encode(), write_to=str(OUT / "og-image.png"), output_width=1200, output_height=630)
# App icons: full-bleed petrol square (platforms round the corners themselves).
full_bleed = re.sub(r'<path fill="#0B3C49" d="M104,0[^"]*"/>', '<rect width="512" height="512" fill="#0B3C49"/>', favicon)
assert full_bleed != favicon, "favicon tile path not found"
for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
    cairosvg.svg2png(bytestring=full_bleed.encode(), write_to=str(ROOT / "static" / name),
                     output_width=size, output_height=size)
# favicon.ico (16/32/48) for browsers that ask for /favicon.ico
import io
from PIL import Image
png = cairosvg.svg2png(bytestring=favicon.encode(), output_width=256, output_height=256)
Image.open(io.BytesIO(png)).save(ROOT / "static" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("brand assets written to", OUT)
