"""Render the static sites: dist/en (otasec.com) and dist/nl (otasec.nl)."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .classify import publishable
from .config import STATIC_DIR, TEMPLATE_DIR, Config
from .i18n import STRINGS, fmt_long_date, fmt_short, plural
from .normalize import safe_url
from .store import Store, parse_iso, utcnow

log = logging.getLogger(__name__)


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


def _asset_version() -> str:
    h = hashlib.sha1()
    for p in sorted(STATIC_DIR.rglob("*")):
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()[:10]


def view_item(it: dict, lang: str, tz: ZoneInfo) -> dict:
    cls = it.get("cls") or {}
    published = (parse_iso(it.get("published")) or utcnow()).astimezone(tz)
    summary = (cls.get("summary") or {}).get(lang) or ""
    if not summary and it.get("lang") == lang:
        summary = it.get("excerpt", "")
    return {
        "id": it["id"],
        "url": safe_url(it["url"]),
        "title": it["title"],
        "source": it["source"],
        "source_id": it.get("source_id", ""),
        "published": it.get("published"),
        "time": fmt_short(published, lang),
        "day": published.date().isoformat(),
        "summary": summary,
        "category": cls.get("category", ""),
        "sectors": cls.get("sectors", []),
        "vendors": cls.get("vendors", []),
        "cves": it.get("cves", [])[:6],
        "score": cls.get("score", 0),
        "x": it.get("x_mentions", 0),
        "lang": it.get("lang", "en"),
    }


def view_briefing(b: dict, lang: str, tz: ZoneInfo) -> dict:
    loc = b["i18n"].get(lang) or b["i18n"].get("en", {})
    date = parse_iso(b["date"] + "T12:00:00+00:00")
    stories = []
    for s in b.get("stories", []):
        sl = s["i18n"].get(lang) or s["i18n"].get("en", {})
        stories.append({
            **sl,
            "sources": [{**x, "url": safe_url(x["url"])} for x in s["sources"] if safe_url(x["url"])],
            "source_count": s.get("source_count", len(s["sources"])),
            "x": s.get("x_mentions", 0),
            "cves": s.get("cves", []),
        })
    return {
        "date": b["date"],
        "date_label": fmt_long_date(date, lang),
        "published": b.get("published"),
        "title": loc.get("title", ""),
        "intro": loc.get("intro", ""),
        "stories": stories,
        "path": f"/briefing/{b['date']}/",
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _rss(title: str, link: str, desc: str, lang: str, entries: list[dict]) -> str:
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:atom": "http://www.w3.org/2005/Atom"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = title
    ET.SubElement(ch, "link").text = link
    ET.SubElement(ch, "description").text = desc
    ET.SubElement(ch, "language").text = "nl-NL" if lang == "nl" else "en"
    for e in entries:
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = e["title"]
        ET.SubElement(it, "link").text = e["link"]
        ET.SubElement(it, "guid", isPermaLink="false").text = e["guid"]
        ET.SubElement(it, "pubDate").text = format_datetime(parse_iso(e["date"]) or utcnow())
        if e.get("description"):
            ET.SubElement(it, "description").text = e["description"]
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode")


def build_site(cfg: Config, store: Store) -> None:
    site = cfg.site
    tz = ZoneInfo(site["timezone"])
    env = _env()
    items_all = store.load_items()
    briefings = store.load_briefings()
    health = store.load_health()
    version = _asset_version()
    now_local = utcnow().astimezone(tz)

    window = utcnow() - timedelta(days=site["feed"]["window_days"])
    min_score = site["feed"].get("min_score", 0)
    relevant = [i for i in items_all
                if publishable(i, min_score)
                and (parse_iso(i.get("published")) or utcnow()) >= window]
    relevant.sort(key=lambda i: i.get("published") or "", reverse=True)

    active_sources = sorted({i["source"] for i in relevant})
    feed_count = len([f for f in cfg.feeds if f.get("enabled", True)])

    for lang in cfg.languages:
        out = cfg.dist_dir / lang
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        shutil.copytree(STATIC_DIR, out / "assets")

        base_url = site["languages"][lang]["base_url"].rstrip("/")
        others = {l: site["languages"][l]["base_url"].rstrip("/") for l in cfg.languages}
        t = STRINGS[lang]
        vitems = [view_item(i, lang, tz) for i in relevant]
        vbriefings = [view_briefing(b, lang, tz) for b in briefings]
        latest = vbriefings[0] if vbriefings else None
        is_today = bool(latest and latest["date"] == now_local.date().isoformat())

        def render(template: str, path: str, **ctx) -> None:
            html = env.get_template(template).render(
                lang=lang, t=t, site=site, base_url=base_url, path=path, others=others,
                languages=site["languages"], v=version, now=now_local,
                updated=fmt_short(now_local, lang), plural=lambda k, n: plural(lang, k, n),
                **ctx,
            )
            target = out / path.strip("/") / "index.html" if path.endswith("/") else out / path.lstrip("/")
            _write(target, html)

        # Live feed page (homepage)
        render("home.html", "/", items=vitems[: site["feed"]["homepage_items"]], total=len(vitems),
               latest=latest, is_today=is_today, sources=active_sources, feed_count=feed_count,
               categories=t["categories"], sectors=t["sectors"])

        # Full JSON for client-side filtering / "show more"
        _write(out / "data" / "feed.json", json.dumps(
            {"updated": now_local.isoformat(), "items": vitems}, ensure_ascii=False, separators=(",", ":")))

        # Briefings
        for idx, b in enumerate(vbriefings):
            newer = vbriefings[idx - 1] if idx > 0 else None
            older = vbriefings[idx + 1] if idx + 1 < len(vbriefings) else None
            render("briefing.html", b["path"], b=b, newer=newer, older=older)
        render("briefings.html", "/briefings/", briefings=vbriefings)

        # About + source health
        sources_view = []
        for f in (f for f in cfg.feeds if f.get("enabled", True)):
            h = health.get("sources", {}).get(f["id"], {})
            sources_view.append({"name": f["name"], "url": f["url"], "focus": f.get("focus"),
                                 "lang": f.get("lang"), "ok": h.get("ok"),
                                 "checked": fmt_short(parse_iso(h["checked"]).astimezone(tz), lang)
                                 if h.get("checked") else ""})
        xh = health.get("sources", {}).get("x", {})
        render(f"about_{lang}.html", "/about/", sources=sources_view, x_status=xh,
               x_enabled=bool(cfg.sources.get("x", {}).get("enabled")))

        render("404.html", "/404.html")

        # RSS: briefings + live feed
        _write(out / "rss.xml", _rss(
            f"OTASEC — {t['rss_briefings']}", base_url + "/", t["tagline"], lang,
            [{"title": b["title"] or b["date_label"], "link": base_url + b["path"], "guid": f"otasec-briefing-{b['date']}-{lang}",
              "date": b["published"], "description": b["intro"]} for b in vbriefings[:30]]))
        _write(out / "news.xml", _rss(
            f"OTASEC — {t['rss_news']}", base_url + "/", t["tagline"], lang,
            [{"title": f"{i['title']} ({i['source']})", "link": i["url"], "guid": f"otasec-item-{i['id']}",
              "date": i["published"], "description": i["summary"]} for i in vitems[:100] if i["url"]]))

        # robots + sitemap + Apache headers
        _write(out / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n")
        urls = ["/", "/briefings/", "/about/"] + [b["path"] for b in vbriefings]
        _write(out / "sitemap.xml", env.get_template("sitemap.xml").render(base_url=base_url, urls=urls))
        shutil.copy(TEMPLATE_DIR / "htaccess", out / ".htaccess")

    log.info("built %s: %d feed items, %d briefings", ", ".join(cfg.languages), len(relevant), len(briefings))
