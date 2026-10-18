"""Fetch RSS/Atom feeds and turn entries into OTASEC items."""
from __future__ import annotations

import calendar
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import feedparser
import httpx

from .normalize import canonical_url, clean_text, extract_cves, item_id
from .store import iso, utcnow

log = logging.getLogger(__name__)

# Many outlets sit behind Cloudflare and reject obvious bots.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 OTASEC-aggregator"
)
HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
}
BOT_HEADERS = {
    "User-Agent": "OTASEC/2.0 (+https://otasec.com/about/; RSS reader)",
    "Accept": HEADERS["Accept"],
}


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def parse_feed(content: bytes, feed: dict, now: datetime | None = None) -> list[dict]:
    now = now or utcnow()
    parsed = feedparser.parse(content)
    items = []
    for entry in parsed.entries:
        url = canonical_url(entry.get("link", ""))
        title = clean_text(entry.get("title", ""), 300)
        if not url or not title:
            continue
        summary = clean_text(entry.get("summary") or entry.get("description") or "", 600)
        published = _entry_time(entry)
        # Undated or future-dated entries get the fetch time (some feeds misreport).
        if published is None or published > now:
            published = now
        items.append({
            "id": item_id(url),
            "url": url,
            "title": title,
            "excerpt": summary,
            "source_id": feed["id"],
            "source": feed["name"],
            "lang": feed.get("lang", "en"),
            "kind": feed.get("kind", "news"),
            "focus": feed.get("focus", "broad"),
            "published": iso(published),
            "fetched": iso(now),
            "cves": extract_cves(title, summary),
            "x_mentions": 0,
            "cls": None,
        })
    return items


def fetch_one(client: httpx.Client, feed: dict) -> tuple[dict, list[dict], dict]:
    status = {"name": feed["name"], "url": feed["url"], "checked": iso(utcnow())}
    try:
        resp = client.get(feed["url"])
        if resp.status_code in (401, 403):
            # Some WAFs (Akamai, Cloudflare) reject a browser UA whose TLS
            # fingerprint isn't a browser's; an honest bot UA often passes.
            resp = client.get(feed["url"], headers=BOT_HEADERS)
            if resp.status_code < 400:
                status["ua"] = "bot"
        status["http"] = resp.status_code
        if resp.status_code >= 400:
            status.update(ok=False, error=f"HTTP {resp.status_code}")
            return feed, [], status
        items = parse_feed(resp.content, feed)
        if not items:
            status.update(ok=False, error="no entries parsed")
        else:
            status.update(ok=True, entries=len(items))
        return feed, items, status
    except (httpx.HTTPError, ValueError) as exc:
        status.update(ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return feed, [], status


def fetch_all(feeds: list[dict], max_workers: int = 8) -> tuple[list[dict], dict]:
    """Fetch every enabled feed concurrently. Returns (items, health-by-source)."""
    enabled = [f for f in feeds if f.get("enabled", True)]
    health: dict[str, dict] = {}
    items: list[dict] = []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client, \
            ThreadPoolExecutor(max_workers=max_workers) as pool:
        for feed, got, status in pool.map(lambda f: fetch_one(client, f), enabled):
            health[feed["id"]] = status
            items.extend(got)
            log.info("%-28s %s", feed["name"], f"{len(got)} items" if status.get("ok") else status.get("error"))
    return items, health
