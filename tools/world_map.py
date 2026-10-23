"""Generate otasec/geodata/world.json: continent outlines for the incident map.

    curl -LO https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson
    pip install shapely
    python tools/world_map.py ne_110m_admin_0_countries.geojson

Source: Natural Earth 1:110m admin-0 countries (public domain). Countries are
merged per continent (Antarctica dropped), Russia is split at the Urals (60 E)
and overseas parts are assigned by location (French Guiana goes to South
America), then projected with Equal Earth (otasec/geo.py) into a 1000-unit
wide SVG coordinate space. The output is committed, so the pipeline never
needs shapely or the download.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import shapely
from shapely.geometry import MultiPolygon, Polygon, box, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from otasec.geo import CONTINENTS, equal_earth  # noqa: E402

OUT = ROOT / "otasec" / "geodata" / "world.json"
WIDTH = 1000.0
NE_CONTINENT = {
    "Europe": "europe", "Asia": "asia", "North America": "north_america",
    "South America": "south_america", "Africa": "africa", "Oceania": "oceania",
}


def part_continent(country_cont: str, part: Polygon) -> str | None:
    c = part.representative_point()
    if country_cont == "europe" and c.x < -25:       # French Guiana and similar
        return "south_america" if c.y < 15 else "north_america"
    return country_cont


def main(src: str) -> None:
    feats = json.loads(Path(src).read_text(encoding="utf-8"))["features"]
    groups: dict[str, list] = {k: [] for k in CONTINENTS}
    borders = []
    for f in feats:
        cont = NE_CONTINENT.get(f["properties"].get("CONTINENT"))
        if not cont:
            continue                                       # Antarctica, Seven seas
        geom = shape(f["geometry"]).buffer(0)
        if f["properties"].get("ADM0_A3") == "RUS":        # split at the Urals
            # West of the Urals is Europe; Siberia and Chukotka (which Natural
            # Earth cuts at the antimeridian, so it has negative longitudes) are Asia.
            groups["europe"].append(geom.intersection(box(0, -90, 60, 90)))
            groups["asia"].append(geom.difference(box(0, -90, 60, 90)))
            borders.append(geom)
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
        for p in parts:
            pc = part_continent(cont, p)
            if pc:
                groups[pc].append(p)
        borders.append(geom)

    def proj(geom):
        return shapely.make_valid(shapely.transform(geom, lambda a: [equal_earth(x, y) for x, y in a]))

    merged = {k: proj(unary_union(v).buffer(0)).buffer(0) for k, v in groups.items()}

    allb = unary_union(list(merged.values())).bounds
    scale = WIDTH / (allb[2] - allb[0])
    x0, y0 = allb[0], allb[3]
    pad = 6

    def to_svg(geom):
        return shapely.transform(geom, lambda a: [((x - x0) * scale, (y0 - y) * scale) for x, y in a])

    def path(geom, tol=0.45, min_area=6.0) -> str:
        g = to_svg(geom).simplify(tol, preserve_topology=True)
        polys = [p for p in getattr(g, "geoms", [g]) if isinstance(p, Polygon)] + [q for p in getattr(g, "geoms", []) if isinstance(p, MultiPolygon) for q in p.geoms]
        out = []
        for p in polys:
            if p.area < min_area:
                continue
            for ring in [p.exterior, *p.interiors]:
                pts = list(ring.coords)[:-1]
                if len(pts) < 3:
                    continue
                out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
        return "".join(out)

    continents = {}
    for k, g in merged.items():
        # Zoom box: the main land masses only, so a far-flung island group
        # (Fiji across the antimeridian, the Aleutians) doesn't zoom out the view.
        sg = to_svg(g)
        polys = [p for p in getattr(sg, "geoms", [sg]) if isinstance(p, Polygon)]
        big = max(p.area for p in polys)
        b = unary_union([p for p in polys if p.area >= big * 0.01]).bounds
        continents[k] = {"d": path(g), "bbox": [round(v, 1) for v in b]}

    # Country borders as thin lines (only the shared edges), for orientation.
    lines = unary_union([to_svg(proj(g)).boundary for g in borders])
    coast = unary_union([to_svg(g).boundary for g in merged.values()])
    inner = lines.difference(coast.buffer(0.6)).simplify(0.45)
    segs = []
    for ln in getattr(inner, "geoms", [inner]):
        pts = list(getattr(ln, "coords", []))
        if len(pts) >= 2 and ln.length > 2:
            segs.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts))

    height = (allb[3] - allb[1]) * scale
    data = {
        "source": "Natural Earth 1:110m admin-0 countries (public domain), Equal Earth projection",
        "viewbox": [-pad, -pad, round(WIDTH + 2 * pad, 1), round(height + 2 * pad, 1)],
        "scale": scale, "x0": x0, "y0": y0,
        "continents": continents,
        "borders": "".join(segs),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1024:.0f} KB, "
          f"viewBox {data['viewbox']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ne_110m_admin_0_countries.geojson")
