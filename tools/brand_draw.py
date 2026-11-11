"""Draw the OTASEC logo from geometry. No dependencies.

    python tools/brand_draw.py        # writes the masters in brand/

The logo (version 2, Nov 2026) has two parts:

- Wordmark: heavy capitals with 45-degree chamfered corners, like machined
  metal, in a single colour. The tagline "OT ASSET SECURITY" sits below it,
  spaced out to the same width.
- Symbol: a gear with a factory inside, and two orange signal arcs taking over
  the gear's top right quarter. Orange is used for the arcs and nowhere else.

Every shape is a plain filled path in absolute coordinates (no fonts, strokes,
transforms or clip paths), so the files look the same in any browser or tool.
`tools/brand_assets.py` turns these drawings into the files the site uses.
"""
from __future__ import annotations

import math
from pathlib import Path

PETROL, SAND, ORANGE = "#0B3C49", "#EFEBE3", "#E8702A"
TITLE = "OTASEC | OT Asset Security"

H = 200.0            # cap height of the wordmark, in drawing units
STROKE = 44.0        # stroke weight of the wordmark letters
CHAMFER = 40.0       # corner cut of the wordmark letters
TRACK = 22.0         # space between wordmark letters
TAG_STROKE, TAG_CHAMFER, TAG_SCALE = 38.0, 34.0, 0.19
TAG_GAP = 44.0       # space between wordmark and tagline
TAGLINE = "OT ASSET SECURITY"
PAD = 6.0            # clear margin inside every viewBox
SYMBOL_GAP = 56.0    # space between symbol and wordmark in the lockup


def _n(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _poly(pts, ox=0.0, oy=0.0, k=1.0) -> str:
    return "M" + " L".join(f"{_n(ox + x * k)},{_n(oy + y * k)}" for x, y in pts) + " Z"


def _inner(c: float, s: float) -> float:
    """Inner corner cut that keeps a diagonal stroke as thick as the straight ones."""
    return max(c - 0.586 * s, 0.0)


# ---------------------------------------------------------------- letters
# Each letter returns (polygons, extra polygons, width). The polygons of a
# letter never overlap, so a whole line can share one even-odd path; shapes
# that do overlap (the leg of the R) go into the extra list and get their own.

def _O(s, c, W=190.0):
    i = _inner(c, s)
    return [[(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)],
            [(s + i, s), (W - s - i, s), (W - s, s + i), (W - s, H - s - i), (W - s - i, H - s),
             (s + i, H - s), (s, H - s - i), (s, s + i)]], [], W


def _C(s, c, W=172.0):
    i = _inner(c, s)
    return [[(W, 0), (c, 0), (0, c), (0, H - c), (c, H), (W, H), (W, H - s), (s + i, H - s),
             (s, H - s - i), (s, s + i), (s + i, s), (W, s)]], [], W


def _S(s, c, W=178.0):
    m = H / 2
    i = max(min(_inner(c, s), (m - 1.5 * s) / 2 - 1), 0.0)
    return [[(W, 0), (c, 0), (0, c), (0, m + s / 2 - c), (c, m + s / 2), (W - s - i, m + s / 2),
             (W - s, m + s / 2 + i), (W - s, H - s - i), (W - s - i, H - s), (0, H - s), (0, H),
             (W - c, H), (W, H - c), (W, m - s / 2 + c), (W - c, m - s / 2), (s + i, m - s / 2),
             (s, m - s / 2 - i), (s, s + i), (s + i, s), (W, s)]], [], W


def _E(s, c, W=158.0):
    m = H / 2
    return [[(0, 0), (W, 0), (W, s), (s, s), (s, m - s / 2), (W * 0.88, m - s / 2), (W * 0.88, m + s / 2),
             (s, m + s / 2), (s, H - s), (W, H - s), (W, H), (0, H)]], [], W


def _T(s, c, W=168.0):
    return [[(0, 0), (W, 0), (W, s), (W / 2 + s / 2, s), (W / 2 + s / 2, H), (W / 2 - s / 2, H),
             (W / 2 - s / 2, s), (0, s)]], [], W


def _A(s, c, W=192.0):
    ca = W * 0.31
    i = _inner(ca, s)
    bar_y, bar = H * 0.57, s * 0.9
    return [[(ca, 0), (W - ca, 0), (W, ca), (W, H), (W - s, H), (W - s, bar_y + bar), (s, bar_y + bar),
             (s, H), (0, H), (0, ca)],
            [(s + i, s), (W - s - i, s), (W - s, s + i), (W - s, bar_y), (s, bar_y), (s, s + i)]], [], W


def _U(s, c, W=182.0):
    i = _inner(c, s)
    return [[(0, 0), (s, 0), (s, H - s - i), (s + i, H - s), (W - s - i, H - s), (W - s, H - s - i),
             (W - s, 0), (W, 0), (W, H - c), (W - c, H), (c, H), (0, H - c)]], [], W


def _R(s, c, W=180.0):
    i = _inner(c, s)
    bowl = H * 0.60
    leg_w, leg_x = s * 1.2, W * 0.40
    return ([[(0, 0), (W - c, 0), (W, c), (W, bowl - c), (W - c, bowl), (s, bowl), (s, H), (0, H)],
             [(s, s), (W - s - i, s), (W - s, s + i), (W - s, bowl - s - i), (W - s - i, bowl - s), (s, bowl - s)]],
            [[(leg_x, bowl - 2), (leg_x + leg_w, bowl - 2), (W, H), (W - leg_w, H)]], W)


def _I(s, c, W=None):
    return [[(0, 0), (s, 0), (s, H), (0, H)]], [], s


def _Y(s, c, W=186.0):
    arm, join = s * 1.18, H * 0.56
    slope = (W / 2 - s / 2) / join
    notch = (W / 2 - arm) / slope
    return [[(0, 0), (arm, 0), (W / 2, notch), (W - arm, 0), (W, 0), (W / 2 + s / 2, join),
             (W / 2 + s / 2, H), (W / 2 - s / 2, H), (W / 2 - s / 2, join)]], [], W


LETTERS = dict(O=_O, T=_T, A=_A, S=_S, E=_E, C=_C, U=_U, R=_R, I=_I, Y=_Y)


def _line_width(text, s, c, track, space):
    x = 0.0
    for ch in text:
        x += space if ch == " " else LETTERS[ch](s, c)[2] + track
    return x - track


def _line(text, s, c, track, space, ox, oy, k):
    """Path data for a line of text: (main path, extra path)."""
    main, extra, x = [], [], 0.0
    for ch in text:
        if ch == " ":
            x += space
            continue
        polys, more, w = LETTERS[ch](s, c)
        main += [_poly(p, ox + x * k, oy, k) for p in polys]
        extra += [_poly(p, ox + x * k, oy, k) for p in more]
        x += w + track
    return " ".join(main), " ".join(extra)


WORD_W = _line_width("OTASEC", STROKE, CHAMFER, TRACK, 0)
WORD_H = H
FULL_H = H + TAG_GAP + H * TAG_SCALE


def _wordmark(fg, ox, oy, tagline=True):
    d, _ = _line("OTASEC", STROKE, CHAMFER, TRACK, 0, ox, oy, 1.0)
    out = [f'<path fill="{fg}" fill-rule="evenodd" d="{d}"/>']
    if tagline:
        # Space the tagline out to exactly the width of the wordmark.
        letters = sum(1 for ch in TAGLINE if ch != " ")
        words = TAGLINE.count(" ")
        raw = _line_width(TAGLINE, TAG_STROKE, TAG_CHAMFER, 0, 0)
        track = (WORD_W / TAG_SCALE - raw) / ((letters - 1) + words * 1.6)
        d, extra = _line(TAGLINE, TAG_STROKE, TAG_CHAMFER, track, track * 1.6, ox, oy + H + TAG_GAP, TAG_SCALE)
        out.append(f'<path fill="{fg}" fill-rule="evenodd" d="{d}"/>')
        out.append(f'<path fill="{fg}" d="{extra}"/>')
    return out


# ---------------------------------------------------------------- symbol
def _band(cx, cy, k, r1, r2, a0, a1):
    """Ring segment between radii r1 < r2, from angle a0 to a1 (degrees, 0 = right, 90 = top)."""
    def pt(r, a):
        t = math.radians(a)
        return f"{_n(cx + k * r * math.cos(t))},{_n(cy - k * r * math.sin(t))}"
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 < a0 else 0
    return (f"M{pt(r2, a0)} A{_n(k * r2)},{_n(k * r2)} 0 {large} {sweep} {pt(r2, a1)} "
            f"L{pt(r1, a1)} A{_n(k * r1)},{_n(k * r1)} 0 {large} {1 - sweep} {pt(r1, a0)} Z")


def _tooth(cx, cy, k, angle, r_in, r_out, w_in, w_out):
    t = math.radians(angle)
    ux, uy = math.cos(t), -math.sin(t)
    vx, vy = -uy, ux
    pts = [(r * ux + w * vx, r * uy + w * vy)
           for r, w in ((r_in, -w_in / 2), (r_out, -w_out / 2), (r_out, w_out / 2), (r_in, w_in / 2))]
    return _poly(pts, cx, cy, k)


SYMBOL_R = 101.0     # outer radius of the symbol (tips of the teeth)


def _symbol(fg, cx, cy, k, small=False, accent=ORANGE):
    """Gear, factory and signal arcs around (cx, cy). `small` is the bolder
    drawing without the factory, for favicons and other tiny sizes."""
    if small:
        ri, ro, tooth = 50, 82, (36, 27)
        arcs = ((84, 100, 86, -22), (50, 70, 85, 16))
    else:
        ri, ro, tooth = 60, 83, (30, 22)
        arcs = ((85, 99, 86.5, -20), (60, 76, 86.5, 18))
    out = [f'<path fill="{fg}" d="{_band(cx, cy, k, ri, ro, 93.5, 330)}"/>']
    teeth = " ".join(_tooth(cx, cy, k, a, ro - 3, SYMBOL_R, *tooth) for a in (112.5, 157.5, 202.5, 247.5, 292.5))
    out.append(f'<path fill="{fg}" d="{teeth}"/>')
    if not small:
        gy = 36.0                                   # ground level inside the gear
        gx = math.sqrt((ri + 1) ** 2 - gy ** 2)
        r = _n(k * (ri + 1))
        ground = (f"M{_n(cx - k * gx)},{_n(cy + k * gy)} L{_n(cx + k * gx)},{_n(cy + k * gy)} "
                  f"A{r},{r} 0 0 1 {_n(cx - k * gx)},{_n(cy + k * gy)} Z")
        hall = _poly([(-40, gy + 1), (-40, -10), (-17, 10), (-17, -10), (6, 10), (6, gy + 1)], cx, cy, k)
        stack = _poly([(13, gy + 1), (15, -40), (29, -40), (31, gy + 1)], cx, cy, k)
        out += [f'<path fill="{fg}" d="{ground}"/>', f'<path fill="{fg}" d="{hall}"/>',
                f'<path fill="{fg}" d="{stack}"/>']
    d = " ".join(_band(cx, cy, k, *a) for a in arcs)
    out.append(f'<path fill="{accent}" d="{d}"/>')
    return out


# ---------------------------------------------------------------- documents
def _svg(w, h, body, title=TITLE, pad=PAD, background=""):
    box = f"{_n(-pad)} {_n(-pad)} {_n(w + 2 * pad)} {_n(h + 2 * pad)}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" width="{round(w + 2 * pad)}" '
            f'height="{round(h + 2 * pad)}" role="img" aria-label="{title}">\n  <title>{title}</title>\n'
            + background + "".join(f"  {el}\n" for el in body) + "</svg>\n")


def wordmark_svg(fg=PETROL, tagline=True) -> str:
    h = FULL_H if tagline else WORD_H
    return _svg(WORD_W, h, _wordmark(fg, 0, 0, tagline), TITLE if tagline else "OTASEC")


def symbol_svg(fg=PETROL) -> str:
    r = SYMBOL_R
    return _svg(2 * r, 2 * r, _symbol(fg, r, r, 1.0), "OTASEC symbol", pad=2)


# In the lockup the symbol is a little taller than the text block, so the
# factory and the arcs stay readable at header size.
LOCKUP_H = 340.0
LOCKUP_K = LOCKUP_H / (2 * SYMBOL_R)
LOCKUP_W = LOCKUP_H + SYMBOL_GAP + WORD_W


def _lockup(fg, ox=0.0, oy=0.0):
    return (_symbol(fg, ox + LOCKUP_H / 2, oy + LOCKUP_H / 2, LOCKUP_K)
            + _wordmark(fg, ox + LOCKUP_H + SYMBOL_GAP, oy + (LOCKUP_H - FULL_H) / 2))


def lockup_svg(fg=PETROL) -> str:
    """Symbol and wordmark side by side: the main logo, used in the site header."""
    return _svg(LOCKUP_W, LOCKUP_H, _lockup(fg))


def lockup_size(height: int) -> tuple[int, int]:
    """Pixel size of the lockup for a given height, for <img width height>."""
    return round(height * (LOCKUP_W + 2 * PAD) / (LOCKUP_H + 2 * PAD)), height


def favicon_svg(full_bleed=False) -> str:
    """The symbol on a petrol tile. `full_bleed` gives a square tile for app
    icons, where the platform rounds the corners itself."""
    tile = (f'<rect width="512" height="512" fill="{PETROL}"/>' if full_bleed else
            f'<path fill="{PETROL}" d="M104,0 L408,0 A104,104 0 0 1 512,104 L512,408 A104,104 0 0 1 408,512 '
            f'L104,512 A104,104 0 0 1 0,408 L0,104 A104,104 0 0 1 104,0 Z"/>')
    k = 1.85 if full_bleed else 2.05
    return _svg(512, 512, [tile] + _symbol(SAND, 256, 256, k, small=True), "OTASEC", pad=0)


def og_svg() -> str:
    """Social card, 1200 x 630: the sand lockup centred on petrol."""
    width = 940.0
    k = width / LOCKUP_W
    ox, oy = (1200 - width) / 2, (630 - LOCKUP_H * k) / 2
    body = [f'<rect width="1200" height="630" fill="{PETROL}"/>']
    # The card is only ever used as a PNG, so one transform to scale the lockup is fine here.
    body.append(f'<g transform="translate({_n(ox)} {_n(oy)}) scale({k:.4f})">' + "".join(_lockup(SAND)) + "</g>")
    return _svg(1200, 630, body, pad=0)


MASTERS = {
    "lockup.svg": lockup_svg,
    "wordmark.svg": wordmark_svg,
    "symbol.svg": symbol_svg,
    "favicon.svg": favicon_svg,
}

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "brand"
    out.mkdir(exist_ok=True)
    for name, draw in MASTERS.items():
        (out / name).write_text(draw())
    print("logo masters written to", out)
