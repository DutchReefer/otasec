"""Text/URL normalisation, ids, CVE extraction and the offline keyword filter."""
from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "s", "cmpid",
}


def clean_text(raw: str | None, limit: int = 600) -> str:
    if not raw:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", raw))
    text = _WS_RE.sub(" ", text).strip()
    # Feed boilerplate such as "The post X appeared first on Y."
    text = re.sub(r"\s*The post .{0,200}? appeared first on .{0,80}?\.?$", "", text)
    return truncate(text, limit)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:.- ") + "…"


def canonical_url(url: str) -> str:
    """Strip tracking params and fragments so the same article from two feeds dedupes."""
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in _TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower().removeprefix("www."), path, urlencode(query), ""))


def item_id(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:12]


def extract_cves(*texts: str) -> list[str]:
    found: dict[str, None] = {}
    for t in texts:
        for m in CVE_RE.findall(t or ""):
            found[m.upper()] = None
    return list(found)


def safe_url(url: str) -> str:
    """Only http(s) links ever reach the HTML."""
    url = (url or "").strip()
    return url if urlsplit(url).scheme in ("http", "https") else ""


# Offline relevance heuristic, used only when no ANTHROPIC_API_KEY is set.
_OT_KEYWORDS = re.compile(
    r"\b(ICS|SCADA|OT|PLC|PLCs|HMI|DCS|RTU|IEC[\s-]?62443|NIS2|Modbus|DNP3|OPC[\s-]?UA|PROFINET|"
    r"BACnet|industrial control|operational technology|critical infrastructure|"
    r"Siemens|Schneider Electric|Rockwell|Honeywell|ABB|Emerson|Yokogawa|Mitsubishi Electric|"
    r"water utilit\w*|power grid|substation|pipeline|refiner\w*|manufactur\w*|"
    r"vitale infrastructuur|industriële|industriele|procesautomatisering)\b",
    re.IGNORECASE,
)


def keyword_relevant(title: str, summary: str) -> bool:
    return bool(_OT_KEYWORDS.search(f"{title} {summary}"))
