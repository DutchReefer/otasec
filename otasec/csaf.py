"""CISA ICS advisories from CISA's official CSAF repository on GitHub.

cisa.gov blocks requests from GitHub's runners (HTTP 403), but CISA publishes
every ICS advisory as a CSAF JSON file in https://github.com/cisagov/CSAF.
We look up the year folder's tree SHA (Contents API on the parent folder) and
list it with the Git Trees API (no 1,000-entry limit), pick the
advisories released in the last `lookback_days` (the release date is encoded
in the file name: icsa-YY-DDD-NN.json, DDD = day of year), and download those
files from raw.githubusercontent.com.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

from .feeds import get_limited
from .normalize import clean_url, clean_text, item_id, safe_netloc
from .store import iso, parse_iso, utcnow

log = logging.getLogger(__name__)

MAX_CSAF_BYTES = 5 * 1024 * 1024

CONTENTS = "https://api.github.com/repos/{repo}/contents/{parent}?ref={branch}"
TREE = "https://api.github.com/repos/{repo}/git/trees/{sha}"
RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}/{name}"
NAME_RE = re.compile(r"^icsa-(\d{2})-(\d{3})-(\d{2}[a-z]?)\.json$", re.IGNORECASE)


def release_date(name: str) -> date | None:
    m = NAME_RE.match(name)
    if not m:
        return None
    year, doy = 2000 + int(m.group(1)), int(m.group(2))
    try:
        return date(year, 1, 1) + timedelta(days=doy - 1)
    except ValueError:
        return None


def recent_names(names: list[str], since: date) -> list[str]:
    picked = [(release_date(n), n) for n in names]
    return [n for d, n in sorted((p for p in picked if p[0] and p[0] >= since), reverse=True)]


def _is_cisa(url: str) -> bool:
    host = safe_netloc(urlsplit(url or "").netloc).split(":")[0]
    return host == "cisa.gov" or host.endswith(".cisa.gov")


def to_item(doc: dict, feed: dict, now: datetime | None = None) -> dict | None:
    d = doc.get("document", {})
    tracking = d.get("tracking", {})
    adv_id = tracking.get("id", "")
    web = next((r["url"] for r in d.get("references", [])
                if r.get("category") == "self" and _is_cisa(r.get("url", ""))), "")
    url = clean_url(web)
    if not url or not d.get("title"):
        return None
    notes = {n.get("category"): n.get("text", "") for n in d.get("notes", [])}
    sectors = next((n.get("text", "") for n in d.get("notes", [])
                    if n.get("title") == "Critical infrastructure sectors"), "")
    excerpt = clean_text(" ".join(x for x in (notes.get("summary", ""),
                                              f"Sectors: {sectors}." if sectors else "") if x), 600)
    now = now or utcnow()
    published = parse_iso(tracking.get("initial_release_date")) or now
    if published > now:
        published = now   # never let a future date pin an item to the top
    cves = []
    for v in doc.get("vulnerabilities", []):
        c = (v.get("cve") or "").upper()
        if c and c not in cves:
            cves.append(c)
    return {
        "id": item_id(url),
        "url": url,
        "title": clean_text(f"{adv_id}: {d['title']}" if adv_id else d["title"], 300),
        "excerpt": excerpt,
        "source_id": feed["id"],
        "source": feed["name"],
        "lang": "en",
        "kind": "advisory",
        "focus": feed.get("focus", "ot"),
        "published": iso(published),
        "fetched": iso(now),
        "cves": cves[:12],
        "x_mentions": 0,
        "cls": None,
    }


def fetch(client: httpx.Client, feed: dict) -> tuple[list[dict], dict]:
    repo = feed.get("repo", "cisagov/CSAF")
    branch = feed.get("branch", "develop")
    lookback = int(feed.get("lookback_days", 7))
    limit = int(feed.get("max_files", 40))
    today = utcnow().date()
    since = today - timedelta(days=lookback)
    status = {"name": feed["name"], "url": f"https://github.com/{repo}", "checked": iso(utcnow())}

    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    names: list[tuple[str, str]] = []  # (path, name)
    years = sorted({since.year, today.year})
    try:
        parent = feed.get("path", "csaf_files/OT/white")
        resp = client.get(CONTENTS.format(repo=repo, parent=parent, branch=branch), headers=headers)
        resp.raise_for_status()
        shas = {e["name"]: e["sha"] for e in resp.json() if e.get("type") == "dir"}
        for year in years:
            if str(year) not in shas:
                continue  # new year's folder not created yet
            path = f"{parent}/{year}"
            resp = client.get(TREE.format(repo=repo, sha=shas[str(year)]), headers=headers)
            resp.raise_for_status()
            tree = resp.json().get("tree", [])
            for n in recent_names([t["path"] for t in tree if t.get("type") == "blob"], since):
                names.append((path, n))
        items = []
        for path, name in names[:limit]:
            code, body = get_limited(client, RAW.format(repo=repo, branch=branch, path=path, name=name),
                                     limit=MAX_CSAF_BYTES)
            if code != 200:
                continue
            it = to_item(json.loads(body), feed)
            if it:
                items.append(it)
    except (httpx.HTTPError, ValueError) as exc:
        status.update(ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return [], status
    status.update(ok=True, entries=len(items))
    return items, status
