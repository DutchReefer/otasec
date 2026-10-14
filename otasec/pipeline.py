"""Glue: ingest -> classify -> (daily) briefing -> build."""
from __future__ import annotations

import logging

from . import briefing as briefing_mod
from . import feeds, xsource
from .classify import classify_items
from .config import Config
from .store import Store, iso, utcnow

log = logging.getLogger(__name__)


def merge_items(existing: list[dict], fetched: list[dict]) -> tuple[list[dict], int]:
    """Add unseen items; keep stored versions (and their classification) for known ids."""
    by_id = {i["id"]: i for i in existing}
    added = 0
    for it in fetched:
        if it["id"] in by_id:
            continue
        by_id[it["id"]] = it
        added += 1
    return list(by_id.values()), added


def ingest(cfg: Config, store: Store) -> list[dict]:
    items = store.load_items()
    health = store.load_health()
    state = health.setdefault("state", {})

    fetched, feed_health = feeds.fetch_all(cfg.feeds)
    items, added = merge_items(items, fetched)
    log.info("feeds: %d fetched, %d new", len(fetched), added)

    x_items, x_status = xsource.collect(cfg.x_bearer, cfg.sources.get("x", {}), state, items)
    items, x_added = merge_items(items, x_items)

    health["sources"] = {**health.get("sources", {}), **feed_health, "x": x_status}
    # Drop health rows for feeds removed from config.
    known = {f["id"] for f in cfg.feeds} | {"x"}
    health["sources"] = {k: v for k, v in health["sources"].items() if k in known}
    state["last_ingest"] = iso(utcnow())
    state["last_ingest_added"] = added + x_added
    store.save_health(health)
    return items


def run(cfg: Config, *, fetch: bool = True, classify: bool = True, do_briefing: bool = True,
        force_briefing: bool = False, build: bool = True) -> None:
    store = Store(cfg.data_dir)
    items = ingest(cfg, store) if fetch else store.load_items()

    if classify:
        classify_items(items, cfg.anthropic_key, cfg.models["classify"],
                       batch_size=cfg.site["classify"]["batch_size"],
                       max_items=cfg.site["classify"]["max_items_per_run"])
    items = store.save_items(items, cfg.site["feed"]["retention_days"])

    if do_briefing:
        briefing_mod.generate(store, items, cfg.site, cfg.anthropic_key, cfg.models["briefing"],
                              force=force_briefing)

    if build:
        from .build import build_site
        build_site(cfg, store)
