"""Daily briefing: the day's most-covered OT/ICS stories in one bilingual post.

Popularity = cross-source corroboration (+ X mentions). Claude clusters items
that report the same event, and writes each story in English and Dutch in a
single call. Stories reference items by id, never by URL, so every link in a
briefing is guaranteed to come from a real fetched item.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .llm import LLMError, complete_json
from .store import Store, iso, parse_iso, utcnow

log = logging.getLogger(__name__)

_STR = {"type": "string"}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title_en", "title_nl", "intro_en", "intro_nl", "stories"],
    "properties": {
        "title_en": _STR, "title_nl": _STR, "intro_en": _STR, "intro_nl": _STR,
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item_ids", "heading_en", "heading_nl", "summary_en", "summary_nl",
                             "takeaway_en", "takeaway_nl"],
                "properties": {
                    "item_ids": {"type": "array", "items": _STR},
                    "heading_en": _STR, "heading_nl": _STR,
                    "summary_en": _STR, "summary_nl": _STR,
                    "takeaway_en": _STR, "takeaway_nl": _STR,
                },
            },
        },
    },
}

SYSTEM = """You are the editor of OTASEC (OT Asset Security), a daily briefing for
asset owners, OT engineers and security leads in industry and critical
infrastructure. You receive today's OT/ICS-relevant news items (already
filtered), each with an id, source, title, excerpt, tags and the number of X
posts that shared it.

Write ONE briefing, in English AND Dutch:
1. Cluster items that report the SAME event or advisory into one story.
2. Rank stories by how many DISTINCT sources cover them (the main popularity
   signal), then X mentions, then real-world impact (active exploitation,
   operational disruption, widely deployed products, binding regulation).
3. Select at most {max_stories} stories. Fewer is fine on a quiet day. Routine
   vendor advisories with no exploitation can be grouped into one story
   ("Other advisories") if there are several.
4. Per story: a short factual heading; a 2-3 sentence neutral summary using only
   facts in the inputs; and a one-sentence takeaway for asset owners (what to
   check or do — e.g. patch, segment, monitor, review supplier) that does not
   invent facts. Keep product names, CVE ids and acronyms (PLC, HMI, ICS,
   IEC 62443, NIS2) unchanged in Dutch.
5. item_ids: every input id you clustered into the story, copied exactly.
6. A 1-2 sentence intro per language setting up the day, and a short title per
   language that includes the date {date_label}.

Dutch should read naturally for Dutch professionals (not a literal translation)."""


def local_now(tz: str) -> datetime:
    return utcnow().astimezone(ZoneInfo(tz))


def due(store: Store, site: dict, force: bool = False) -> str | None:
    """Return today's local date if a briefing should be generated now."""
    now = local_now(site["timezone"])
    date = now.date().isoformat()
    if store.has_briefing(date) and not force:
        return None
    if now.hour < site["briefing"]["publish_hour_local"] and not force:
        return None
    return date


def select_items(items: list[dict], hours: int) -> list[dict]:
    cutoff = utcnow() - timedelta(hours=hours)
    return [i for i in items
            if i.get("cls", {}) and i["cls"].get("relevant")
            and (parse_iso(i.get("published")) or utcnow()) >= cutoff]


def _payload(items: list[dict]) -> str:
    rows = [{
        "id": i["id"],
        "source": i["source"],
        "published": i["published"],
        "title": i["title"],
        "excerpt": i.get("excerpt", "")[:400],
        "category": i["cls"].get("category"),
        "sectors": i["cls"].get("sectors"),
        "cves": i.get("cves", [])[:8],
        "x_mentions": i.get("x_mentions", 0),
    } for i in items]
    return json.dumps(rows, ensure_ascii=False)


def assemble(result: dict, items: list[dict], date: str, model: str) -> dict:
    """Map item ids back to real sources, drop unknown ids, compute source counts."""
    by_id = {i["id"]: i for i in items}
    stories = []
    for s in result.get("stories", []):
        sources, seen_urls = [], set()
        for iid in s.get("item_ids", []):
            it = by_id.get(iid)
            if it is None or it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            sources.append({"id": it["id"], "name": it["source"], "url": it["url"], "title": it["title"]})
        if not sources:
            continue  # no verifiable backlink -> drop
        stories.append({
            "sources": sources,
            "source_count": len({x["name"] for x in sources}),
            "x_mentions": sum(by_id[x["id"]].get("x_mentions", 0) for x in sources),
            "cves": sorted({c for x in sources for c in by_id[x["id"]].get("cves", [])}),
            "i18n": {
                lang: {
                    "heading": s.get(f"heading_{lang}", "").strip(),
                    "summary": s.get(f"summary_{lang}", "").strip(),
                    "takeaway": s.get(f"takeaway_{lang}", "").strip(),
                } for lang in ("en", "nl")
            },
        })
    return {
        "date": date,
        "published": iso(utcnow()),
        "model": model,
        "item_count": len(items),
        "i18n": {lang: {"title": result.get(f"title_{lang}", "").strip(),
                        "intro": result.get(f"intro_{lang}", "").strip()} for lang in ("en", "nl")},
        "stories": stories,
    }


def generate(store: Store, items: list[dict], site: dict, api_key: str, model: str,
             force: bool = False) -> dict | None:
    date = due(store, site, force=force)
    if date is None:
        return None
    if not api_key:
        log.warning("briefing due but ANTHROPIC_API_KEY is not set; skipping")
        return None

    cfg = site["briefing"]
    selected = select_items(items, cfg["lookback_hours"])
    if len(selected) < cfg["min_items"]:
        selected = select_items(items, cfg["fallback_lookback_hours"])
    if not selected:
        log.warning("no relevant items for briefing %s", date)
        return None
    selected.sort(key=lambda i: (i["cls"].get("score", 0), i.get("x_mentions", 0)), reverse=True)
    selected = selected[:120]

    date_label = datetime.fromisoformat(date).strftime("%d-%m-%Y")
    system = SYSTEM.format(max_stories=cfg["max_stories"], date_label=date_label)
    try:
        result = complete_json(api_key, model, system,
                               f"Date: {date}\n\nItems:\n{_payload(selected)}", SCHEMA, max_tokens=12000)
    except LLMError as exc:
        log.error("briefing generation failed: %s", exc)
        return None

    briefing = assemble(result, selected, date, model)
    if not briefing["stories"]:
        log.error("briefing had no stories with valid sources; not published")
        return None
    store.save_briefing(briefing)
    log.info("published briefing %s with %d stories", date, len(briefing["stories"]))
    return briefing
