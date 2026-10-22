"""X (Twitter) API v2 recent search as an extra news signal.

Posts that link to an article we already have raise that item's `x_mentions`
count (a popularity signal used by the briefing). Posts linking to articles we
don't have yet become their own items only if the linked site is trusted
(config `x.trusted_domains` plus every domain our RSS feeds link to); links to
anything else (SEO pages, job boards, shops, unknown blogs) are ignored.

Cost control (X is pay-per-use): runs at most every `min_interval_hours`,
reads at most `max_posts_per_run` posts, and keeps `since_id` per query so a
post is never read (and paid for) twice.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import urlsplit

import httpx

from .normalize import clean_url, clean_text, extract_cves, item_id, safe_netloc
from .store import iso, parse_iso, utcnow

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
_SKIP_HOSTS = {"x.com", "twitter.com", "t.co", "youtube.com", "youtu.be", "linkedin.com", "lnkd.in"}

# Subdomains of trusted sites where anyone can publish (forums, Q&A, user
# storage). A link there must not become an OTASEC item just because the parent
# domain (microsoft.com, cloud.google.com, siemens.com, ...) is trusted.
# Extend per site with `x.untrusted_hosts` in config/sources.yaml.
_UGC_LABELS = {
    "community", "communities", "techcommunity", "forum", "forums", "answers", "discuss",
    "discussion", "discussions", "groups", "storage", "sites", "social", "support-community",
    "qna", "feedback", "ideas", "gist", "pages", "users", "user", "members",
}


def _queries(cfg: dict) -> list[dict]:
    queries = list(cfg.get("queries", []))
    accounts = [a.lstrip("@") for a in cfg.get("accounts", []) if a]
    if accounts:
        frm = " OR ".join(f"from:{a}" for a in accounts)
        queries.append({"id": "accounts", "query": f"({frm}) has:links -is:retweet"})
    return queries


def due(cfg: dict, state: dict) -> bool:
    last = parse_iso(state.get("x_last_run"))
    return last is None or utcnow() - last >= timedelta(hours=cfg.get("min_interval_hours", 6))


def search(bearer: str, query: str, since_id: str | None, max_results: int) -> dict:
    params = {
        "query": query,
        "max_results": max(10, min(100, max_results)),
        "tweet.fields": "created_at,public_metrics,entities,lang",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    if since_id:
        params["since_id"] = since_id
    resp = httpx.get(SEARCH_URL, params=params, timeout=30,
                     headers={"Authorization": f"Bearer {bearer}"})
    resp.raise_for_status()
    return resp.json()


def posts_to_signals(payload: dict) -> list[dict]:
    """Flatten an API response into one record per (post, external link)."""
    users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}
    out = []
    for post in payload.get("data", []):
        author = users.get(post.get("author_id"), {})
        metrics = post.get("public_metrics", {})
        for u in post.get("entities", {}).get("urls", []):
            link = clean_url(u.get("unwound_url") or u.get("expanded_url") or "")
            host = urlsplit(link).netloc.removeprefix("www.") if link else ""
            if not link or host in _SKIP_HOSTS or urlsplit(link).path in ("", "/"):
                continue  # social links and bare homepages aren't articles
            out.append({
                "post_id": post["id"],
                "url": link,
                "host": host,
                "title": clean_text(u.get("title") or "", 300),
                "description": clean_text(u.get("description") or "", 600),
                "text": clean_text(post.get("text", ""), 400),
                "created_at": post.get("created_at"),
                "handle": author.get("username", ""),
                "engagement": int(metrics.get("like_count", 0)) + 2 * int(metrics.get("retweet_count", 0)),
            })
    return out


def _host(url: str) -> str:
    return safe_netloc(urlsplit(url).netloc).split(":")[0].removeprefix("www.")


def trusted_domains(cfg: dict, items: list[dict]) -> set[str]:
    """Domains X links may introduce as new items: the configured allowlist plus
    every domain our RSS feeds already link to."""
    domains = {d.lower().removeprefix("www.") for d in cfg.get("trusted_domains", []) if d}
    domains |= {_host(i["url"]) for i in items if i.get("source_id") != "x"}
    return {d for d in domains if d}


def is_trusted(host: str, trusted: set[str], untrusted: set[str] | frozenset = frozenset()) -> bool:
    """host is a trusted domain or one of its subdomains, but not a user-content
    subdomain (community.*, forum.*, storage.*, ...) or a configured untrusted host."""
    host = safe_netloc(host).split(":")[0].removeprefix("www.")
    if not host:
        return False
    if any(host == u or host.endswith("." + u) for u in untrusted):
        return False
    if host in trusted:
        return True
    for d in trusted:
        if host.endswith("." + d):
            sub_labels = host[: -len(d) - 1].split(".")
            if not any(lbl in _UGC_LABELS for lbl in sub_labels):
                return True
    return False


def untrusted_hosts(cfg: dict) -> set[str]:
    return {h.lower().removeprefix("www.") for h in cfg.get("untrusted_hosts", []) if h}


def rename_sources(items: list[dict], display_names: dict | None = None) -> None:
    """X items get a readable source name (in place): the feed's name for sites we
    follow by RSS, else `x.display_names` from config (subdomains match too)."""
    names = {_host(i["url"]): i["source"] for i in items if i.get("source_id") != "x"}
    display = {k.lower().removeprefix("www."): v for k, v in (display_names or {}).items()}
    for i in items:
        if i.get("source_id") != "x":
            continue
        host = _host(i["url"])
        if host in names:
            i["source"] = names[host]
            continue
        match = next((d for d in sorted(display, key=len, reverse=True)
                      if host == d or host.endswith("." + d)), None)
        if match:
            i["source"] = display[match]


def prune_untrusted(items: list[dict], trusted: set[str],
                    untrusted: set[str] | frozenset = frozenset()) -> list[dict]:
    """Remove previously stored X-sourced items whose site isn't trusted (any more)."""
    return [i for i in items
            if i.get("source_id") != "x" or is_trusted(_host(i["url"]), trusted, untrusted)]


def merge_signals(items: list[dict], signals: list[dict], trusted: set[str] | None = None,
                  untrusted: set[str] | frozenset = frozenset()) -> list[dict]:
    """Raise x_mentions on known items; return new items for unknown links on trusted sites."""
    by_id = {i["id"]: i for i in items}
    # Links to a site we already follow by RSS keep that feed's name.
    names = {_host(i["url"]): i["source"] for i in items if i.get("source_id") != "x"}
    new: dict[str, dict] = {}
    now = iso(utcnow())
    for s in signals:
        iid = item_id(s["url"])
        target = by_id.get(iid) or new.get(iid)
        if target is not None:
            target["x_mentions"] = target.get("x_mentions", 0) + 1
            handles = target.setdefault("x_handles", [])
            if s["handle"] and s["handle"] not in handles:
                handles.append(s["handle"])
            continue
        if trusted is not None and not is_trusted(s["host"], trusted, untrusted):
            continue  # SEO pages, job boards, shops, unknown blogs: signal only
        # Title and excerpt come only from the linked page's own card (fetched by
        # X from the trusted site), never from the post text: anyone can post on X,
        # so post text must not become an OTASEC headline.
        title = s["title"]
        if not title:
            continue
        excerpt = s["description"]
        new[iid] = {
            "id": iid,
            "url": s["url"],
            "title": title,
            "excerpt": excerpt,
            "source_id": "x",
            "source": names.get(s["host"], s["host"]),
            "lang": "en",
            "kind": "news",
            "focus": "broad",
            "published": iso(parse_iso(s["created_at"]) or utcnow()),
            "fetched": now,
            "cves": extract_cves(title, excerpt),
            "x_mentions": 1,
            "x_handles": [s["handle"]] if s["handle"] else [],
            "cls": None,
        }
    return list(new.values())


def collect(bearer: str, cfg: dict, state: dict, items: list[dict],
            trusted: set[str] | None = None) -> tuple[list[dict], dict]:
    untrusted = untrusted_hosts(cfg)
    """Run all configured queries within budget. Returns (new_items, status)."""
    status = {"name": "X recent search", "checked": iso(utcnow())}
    if not cfg.get("enabled") or not bearer:
        status.update(ok=None, error="disabled or X_BEARER_TOKEN not set")
        return [], status
    if not due(cfg, state):
        status.update(ok=None, error="skipped (interval)", last=state.get("x_last_run"))
        return [], status

    queries = _queries(cfg)
    budget = int(cfg.get("max_posts_per_run", 50))
    per_query = max(10, budget // max(1, len(queries)))
    since = state.setdefault("x_since_id", {})
    signals, reads = [], 0
    try:
        for q in queries:
            payload = search(bearer, q["query"], since.get(q["id"]), per_query)
            reads += len(payload.get("data", []))
            newest = payload.get("meta", {}).get("newest_id")
            if newest:
                since[q["id"]] = newest
            signals.extend(posts_to_signals(payload))
    except httpx.HTTPStatusError as exc:
        status.update(ok=False, error=f"HTTP {exc.response.status_code}")
        return [], status
    except httpx.HTTPError as exc:
        status.update(ok=False, error=type(exc).__name__)
        return [], status

    state["x_last_run"] = iso(utcnow())
    new_items = merge_signals(items, signals, trusted, untrusted)
    status.update(ok=True, posts_read=reads, links=len(signals), new_items=len(new_items))
    log.info("X: %d posts read, %d links, %d new items", reads, len(signals), len(new_items))
    return new_items, status
