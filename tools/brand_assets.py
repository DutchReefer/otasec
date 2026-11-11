"""Write the logo masters and every brand file the website uses.

    pip install cairosvg pillow      # only for this step, not for the pipeline
    python tools/brand_assets.py

The drawing itself lives in tools/brand_draw.py. This script writes:

- brand/                 the masters (lockup, wordmark, symbol, favicon)
- static/brand/          lockup, wordmark, compact wordmark and symbol, each in
                         petrol (for light backgrounds) and sand ("reverse",
                         for the petrol header), plus the social card
- static/                favicon.svg, favicon.ico, apple-touch-icon, app icons

The outputs are committed, so the pipeline itself never needs Cairo.
"""
import io
import sys
from pathlib import Path

import cairosvg
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_draw as draw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MASTERS, STATIC = ROOT / "brand", ROOT / "static"
OUT = STATIC / "brand"
MASTERS.mkdir(exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

for name, fn in draw.MASTERS.items():
    (MASTERS / name).write_text(fn())

files = {
    "otasec-lockup.svg": draw.lockup_svg(draw.PETROL),
    "otasec-lockup-reverse.svg": draw.lockup_svg(draw.SAND),
    "otasec-wordmark.svg": draw.wordmark_svg(draw.PETROL),
    "otasec-wordmark-reverse.svg": draw.wordmark_svg(draw.SAND),
    "otasec-wordmark-compact.svg": draw.wordmark_svg(draw.PETROL, tagline=False),
    "otasec-wordmark-compact-reverse.svg": draw.wordmark_svg(draw.SAND, tagline=False),
    "otasec-symbol.svg": draw.symbol_svg(draw.PETROL),
    "otasec-symbol-reverse.svg": draw.symbol_svg(draw.SAND),
}
for name, content in files.items():
    (OUT / name).write_text(content)

favicon = draw.favicon_svg()
(STATIC / "favicon.svg").write_text(favicon)

# Social card: the sand lockup centred on petrol.
og = draw.og_svg()
(OUT / "og-image.svg").write_text(og)
cairosvg.svg2png(bytestring=og.encode(), write_to=str(OUT / "og-image.png"), output_width=1200, output_height=630)

# App icons: full-bleed petrol square (platforms round the corners themselves).
full_bleed = draw.favicon_svg(full_bleed=True)
for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
    cairosvg.svg2png(bytestring=full_bleed.encode(), write_to=str(STATIC / name),
                     output_width=size, output_height=size)

# favicon.ico (16/32/48) for browsers that ask for /favicon.ico
png = cairosvg.svg2png(bytestring=favicon.encode(), output_width=256, output_height=256)
Image.open(io.BytesIO(png)).save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

print("brand assets written to", MASTERS, "and", OUT)
print("header logo size at 52 px high:", draw.lockup_size(52), "| footer at 60 px:", draw.lockup_size(60))
