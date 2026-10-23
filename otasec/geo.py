"""Map geometry for the incident map: Equal Earth projection and blip layout.

The continent outlines are generated once by tools/world_map.py (from Natural
Earth, public domain) into otasec/geodata/world.json. That file stores the
projection's scale and offset, so build.py projects incident coordinates with
exactly the same numbers and the blips land on the outlines.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

GEODATA = Path(__file__).resolve().parent / "geodata" / "world.json"

CONTINENTS = ("europe", "asia", "north_america", "south_america", "africa", "oceania")

# Equal Earth (Savric, Patterson & Jenny 2018): equal-area, pleasant shapes,
# no external dependency.
_A1, _A2, _A3, _A4 = 1.340264, -0.081106, 0.000893, 0.003796
_M = math.sqrt(3) / 2


def equal_earth(lon: float, lat: float) -> tuple[float, float]:
    """Degrees in, unitless map coordinates out (y grows northwards)."""
    lam, phi = math.radians(lon), math.radians(lat)
    t = math.asin(_M * math.sin(phi))
    t2 = t * t
    t6 = t2 * t2 * t2
    x = lam * math.cos(t) / (_M * (_A1 + 3 * _A2 * t2 + t6 * (7 * _A3 + 9 * _A4 * t2)))
    y = t * (_A1 + _A2 * t2 + t6 * (_A3 + _A4 * t2))
    return x, y


@lru_cache(maxsize=1)
def world() -> dict:
    return json.loads(GEODATA.read_text(encoding="utf-8"))


def project(lon: float, lat: float, w: dict | None = None) -> tuple[float, float]:
    """Degrees to SVG user units of the generated map (y grows downwards)."""
    w = w or world()
    x, y = equal_earth(lon, lat)
    return round((x - w["x0"]) * w["scale"], 1), round((w["y0"] - y) * w["scale"], 1)


def spread(points: list[tuple[float, float]], min_dist: float) -> list[tuple[float, float]]:
    """Greedy collision avoidance: keep each point where it is if it is free,
    otherwise move it outwards on a spiral until it is min_dist from all
    previously placed points. The same algorithm runs in incidents.js when the
    map is zoomed, with min_dist in screen pixels."""
    placed: list[tuple[float, float]] = []
    golden = math.pi * (3 - math.sqrt(5))
    for x, y in points:
        cx, cy = x, y
        k = 0
        while any((cx - px) ** 2 + (cy - py) ** 2 < min_dist ** 2 for px, py in placed) and k < 400:
            k += 1
            r = min_dist * 0.55 * math.sqrt(k)
            a = k * golden
            cx, cy = x + r * math.cos(a), y + r * math.sin(a)
        placed.append((round(cx, 1), round(cy, 1)))
    return placed
