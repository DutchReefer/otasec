"""OT incident history: load and validate config/incidents.yaml, and shape it
for the /incidents/ page (map blips plus the searchable list)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .config import ROOT
from .geo import CONTINENTS, project, spread, world
from .i18n import _MONTHS
from .normalize import no_em_dash, safe_url

INCIDENTS_FILE = ROOT / "config" / "incidents.yaml"
IMPACTS = ("process", "disruption", "intrusion")
STATUSES = ("confirmed", "reported", "disputed")
_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")
BLIP_GAP = 11.0   # min distance between blips on the world view, in map units


class IncidentError(ValueError):
    pass


def load_incidents(path: Path = INCIDENTS_FILE, sectors: dict | None = None) -> list[dict]:
    """Read and validate the curated list. Raises IncidentError on any problem,
    so a typo in the YAML fails the build (and the tests) instead of the page."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise IncidentError("incidents.yaml must be a list")
    seen: set[str] = set()
    out = []
    for n, inc in enumerate(data, 1):
        where = f"incident #{n} ({inc.get('id', '?')})"
        try:
            iid = str(inc["id"])
            if not _ID.match(iid) or iid in seen:
                raise IncidentError(f"{where}: id must be a unique lowercase slug")
            seen.add(iid)
            if not _DATE.match(str(inc["date"])):
                raise IncidentError(f"{where}: date must be YYYY, YYYY-MM or YYYY-MM-DD")
            lat, lon = float(inc["lat"]), float(inc["lon"])
            if not (-60 <= lat <= 85 and -180 <= lon <= 180):
                raise IncidentError(f"{where}: lat/lon out of range")
            if inc["continent"] not in CONTINENTS:
                raise IncidentError(f"{where}: unknown continent {inc['continent']!r}")
            if inc["impact"] not in IMPACTS:
                raise IncidentError(f"{where}: impact must be one of {IMPACTS}")
            if inc["status"] not in STATUSES:
                raise IncidentError(f"{where}: status must be one of {STATUSES}")
            if sectors is not None and inc["sector"] not in sectors:
                raise IncidentError(f"{where}: unknown sector {inc['sector']!r}")
            for key in ("name", "place", "actor", "summary", "lesson"):
                for lang in ("en", "nl"):
                    if not str(inc[key][lang]).strip():
                        raise IncidentError(f"{where}: {key}.{lang} is empty")
            srcs = inc.get("sources") or []
            if not srcs or any(not safe_url(s.get("url", "")).startswith("https://") for s in srcs):
                raise IncidentError(f"{where}: needs at least one source, all https")
        except (KeyError, TypeError) as e:
            raise IncidentError(f"{where}: missing or malformed field {e}") from e
        out.append(inc)
    out.sort(key=lambda i: str(i["date"]), reverse=True)
    return out


def fmt_date(value: str, lang: str) -> str:
    y, m, d = _DATE.match(str(value)).groups()
    if not m:
        return y
    mon = _MONTHS[lang][int(m) - 1]
    return f"{int(d)} {mon} {y}" if d else f"{mon} {y}"


def _t(v, lang):
    return no_em_dash(str(v.get(lang) or v.get("en") or "")) if isinstance(v, dict) else no_em_dash(str(v))


def view_incidents(incidents: list[dict], lang: str, t: dict) -> dict:
    """Everything the template needs: list entries, blip positions, continent
    shapes with counts and zoom boxes, and the map viewBox."""
    w = world()
    # Oldest first for the layout, so long-known incidents keep their exact spot.
    order = sorted(incidents, key=lambda i: str(i["date"]))
    true_xy = [project(i["lon"], i["lat"], w) for i in order]
    shown_xy = dict(zip((i["id"] for i in order), spread(true_xy, BLIP_GAP)))
    true_by_id = dict(zip((i["id"] for i in order), true_xy))

    items = []
    for i in incidents:
        x, y = shown_xy[i["id"]]
        tx, ty = true_by_id[i["id"]]
        name, place, summary = _t(i["name"], lang), _t(i["place"], lang), _t(i["summary"], lang)
        actor, lesson = _t(i["actor"], lang), _t(i["lesson"], lang)
        malware = [no_em_dash(str(m)) for m in i.get("malware") or []]
        sector = t["sectors"].get(i["sector"], i["sector"])
        items.append({
            "id": i["id"],
            "date": str(i["date"]),
            "year": str(i["date"])[:4],
            "date_label": fmt_date(i["date"], lang),
            "name": name, "place": place, "summary": summary, "actor": actor, "lesson": lesson,
            "malware": malware,
            "continent": i["continent"],
            "sector": i["sector"], "sector_label": sector,
            "impact": i["impact"], "status": i["status"],
            "sources": [{"title": no_em_dash(str(s.get("title") or s["url"])), "url": safe_url(s["url"])}
                        for s in i["sources"] if safe_url(s["url"])],
            "x": x, "y": y, "tx": tx, "ty": ty,
        })

    continents = []
    for key in CONTINENTS:
        c = w["continents"][key]
        mine = [it for it in items if it["continent"] == key]
        x0, y0, x1, y1 = c["bbox"]
        for it in mine:                      # make sure every blip is inside the zoom box
            x0, y0 = min(x0, it["tx"], it["x"]), min(y0, it["ty"], it["y"])
            x1, y1 = max(x1, it["tx"], it["x"]), max(y1, it["ty"], it["y"])
        pad = max(x1 - x0, y1 - y0) * 0.06 + 8
        continents.append({
            "key": key, "label": t["continents"][key], "d": c["d"], "count": len(mine),
            "zoom": [round(x0 - pad, 1), round(y0 - pad, 1), round(x1 - x0 + 2 * pad, 1), round(y1 - y0 + 2 * pad, 1)],
        })

    years = [int(i["year"]) for i in items]
    return {
        "items": items,
        "continents": continents,
        "borders": w["borders"],
        "viewbox": " ".join(str(v) for v in w["viewbox"]),
        "total": len(items),
        "first_year": min(years) if years else "",
        "last_year": max(years) if years else "",
        "impact_counts": {k: sum(1 for i in items if i["impact"] == k) for k in IMPACTS},
        "sectors_used": sorted({i["sector"] for i in items}, key=lambda s: t["sectors"].get(s, s)),
    }
