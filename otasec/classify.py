"""Tag new items with Claude: OT relevance, category, sectors, and EN/NL one-liners.

Dedicated OT sources are always kept; broad-press items are published only if
Claude judges them OT/ICS-relevant. Without an API key a keyword heuristic is
used instead (no summaries), so the site still works.
"""
from __future__ import annotations

import json
import logging

from .llm import LLMError, complete_json
from .normalize import keyword_relevant
from .store import iso, utcnow

log = logging.getLogger(__name__)

CATEGORIES = ["advisory", "incident", "threat", "regulation", "research", "industry", "guidance"]
SECTORS = ["energy", "water", "manufacturing", "oil_gas", "chemical", "transport",
           "healthcare", "building", "food", "government", "cross_sector"]

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "relevant", "score", "category", "sectors", "vendors",
                             "summary_en", "summary_nl"],
                "properties": {
                    "id": {"type": "string"},
                    "relevant": {"type": "boolean"},
                    "score": {"type": "integer"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "sectors": {"type": "array", "items": {"type": "string", "enum": SECTORS}},
                    "vendors": {"type": "array", "items": {"type": "string"}},
                    "summary_en": {"type": "string"},
                    "summary_nl": {"type": "string"},
                },
            },
        }
    },
}

SYSTEM = """You tag news items for OTASEC (OT Asset Security), a news service for
people who own, operate and secure industrial assets: OT/ICS, SCADA, PLCs,
building automation, IIoT and critical infrastructure, plus OT-relevant
standards and regulation (IEC 62443, NIS2, CRA, ISO 55001 where security-related).

For each item return:
- relevant: true only if the item has a real OT/ICS/critical-infrastructure
  security angle. General IT, consumer, crypto or cloud news is NOT relevant
  unless it directly affects industrial operations or critical infrastructure.
  NCSC-style advisories for office software (Microsoft, browsers) are NOT relevant;
  advisories for industrial vendors/products ARE.
  Product marketing, webinars, company/product pages, job postings, training
  or book ads and event listings are NOT relevant, even if they mention SCADA or OT.
- score: 0-100 importance for an OT security professional (active exploitation,
  real-world disruption, widely deployed products and new regulation score high;
  marketing and minor updates score low).
- category: advisory | incident | threat | regulation | research | industry | guidance
- sectors: affected sectors (empty if unclear; cross_sector if broad).
- vendors: industrial vendors/products named in the item (e.g. "Siemens", "Rockwell Automation"); empty if none.
- summary_en / summary_nl: ONE neutral sentence (max 30 words) in English and in
  Dutch saying what happened, using only facts in the title/excerpt. Keep
  technical terms, product names and CVE ids unchanged. No hype.

Return one result per input id, using the exact id."""


def publishable(it: dict, min_score: int = 0) -> bool:
    """Shown on the site / eligible for the briefing: relevant, and for broad
    sources (press, X) important enough. Dedicated OT sources always pass."""
    cls = it.get("cls") or {}
    if not cls.get("relevant"):
        return False
    return it.get("focus") == "ot" or int(cls.get("score") or 0) >= min_score


def _payload(batch: list[dict]) -> str:
    rows = [{
        "id": it["id"],
        "source": it["source"],
        "source_focus": it.get("focus"),
        "lang": it.get("lang"),
        "title": it["title"],
        "excerpt": it.get("excerpt", "")[:500],
    } for it in batch]
    return json.dumps(rows, ensure_ascii=False)


def _heuristic(it: dict) -> dict:
    relevant = it.get("focus") == "ot" or keyword_relevant(it["title"], it.get("excerpt", ""))
    return {
        "relevant": relevant,
        "score": 50 if relevant else 0,
        "category": "advisory" if it.get("kind") == "advisory" else "industry",
        "sectors": [],
        "vendors": [],
        "summary": {},
        "model": "heuristic",
        "at": iso(utcnow()),
    }


def classify_items(items: list[dict], api_key: str, model: str,
                   batch_size: int = 20, max_items: int = 200) -> int:
    """Classify items whose `cls` is empty (in place). Returns number classified."""
    pending = [i for i in items if not i.get("cls") or i["cls"].get("model") == "heuristic" and api_key]
    if not pending:
        return 0
    if not api_key:
        for it in pending:
            it["cls"] = _heuristic(it)
        return len(pending)

    # Newest first, capped per run as a cost guard; the rest waits for the next run.
    pending.sort(key=lambda i: i.get("published") or "", reverse=True)
    pending = pending[:max_items]
    done = 0
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        try:
            result = complete_json(api_key, model, SYSTEM, _payload(batch), SCHEMA, max_tokens=8000)
        except LLMError as exc:
            log.error("classification batch failed: %s", exc)
            continue
        by_id = {r["id"]: r for r in result.get("results", [])}
        for it in batch:
            r = by_id.get(it["id"])
            if r is None:
                continue
            relevant = bool(r["relevant"]) or it.get("focus") == "ot"
            it["cls"] = {
                "relevant": relevant,
                "score": max(0, min(100, int(r.get("score", 0)))),
                "category": r["category"] if r.get("category") in CATEGORIES else "industry",
                "sectors": [s for s in r.get("sectors", []) if s in SECTORS],
                "vendors": [v.strip() for v in r.get("vendors", []) if v.strip()][:6],
                "summary": {"en": r.get("summary_en", "").strip(), "nl": r.get("summary_nl", "").strip()},
                "model": model,
                "at": iso(utcnow()),
            }
            done += 1
    log.info("classified %d/%d items with %s", done, len(pending), model)
    return done
