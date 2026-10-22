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


# Characters that are invalid in XML 1.0 (they would break rss.xml/news.xml) or
# that can disguise text: C0/C1 controls, bidi overrides and isolates
# ("Trojan Source"-style spoofing), zero-width joiners/spaces, BOM, noncharacters.
_UNSAFE_CHARS_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁠-⁩"
    "﻿￾￿\ud800-\udfff]"
)
_LINK_RE = re.compile(r"(?:\bhttps?://|\bwww\.)\S+", re.IGNORECASE)


def strip_unsafe_chars(text: str) -> str:
    return _UNSAFE_CHARS_RE.sub("", text or "")


def clean_text(raw: str | None, limit: int = 600) -> str:
    if not raw:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", strip_unsafe_chars(raw)))
    text = _WS_RE.sub(" ", strip_unsafe_chars(text)).strip()
    # Feed boilerplate such as "The post X appeared first on Y."
    text = re.sub(r"\s*The post .{0,200}? appeared first on .{0,80}?\.?$", "", text)
    return truncate(text, limit)


def scrub_model_text(raw: str | None, limit: int) -> str:
    """Text written by Claude, before it is stored and published.

    The model reads untrusted feed titles/excerpts, so a prompt-injected item
    could try to make it write a link or a very long text. Links on the site
    only ever come from fetched items (by id), so any URL in generated prose is
    removed, unsafe characters are stripped and the length is capped.
    """
    text = strip_unsafe_chars(raw or "")
    text = _LINK_RE.sub("", text)
    text = _WS_RE.sub(" ", text).strip()
    return truncate(text, limit)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:.- ") + "…"


def clean_url(url: str) -> str:
    """The link we publish: tracking params and fragment removed, host kept as-is
    (some sites don't serve the bare domain without www.)."""
    url = (url or "").strip()
    if not url or _UNSAFE_CHARS_RE.search(url) or any(c in url for c in " \t\r\n\\"):
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    netloc = safe_netloc(parts.netloc)
    if parts.scheme.lower() not in ("http", "https") or not netloc:
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in _TRACKING_PARAMS]
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, urlencode(query), ""))


_HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_PORT_RE = re.compile(r"^\d{1,5}$")


def safe_netloc(netloc: str) -> str:
    """Lower-cased host[:port] if it is a plain DNS name, else "".

    Rejects user-info (`a@b`), backslashes, percent-encoding, IP literals and
    other forms that browsers and Python parse differently. Example: Python
    reads the host of `https://evil.com\\.cisa.gov/` as `evil.com\\.cisa.gov`
    (which ends in `.cisa.gov`), while a browser goes to evil.com.
    """
    netloc = (netloc or "").lower()
    if not netloc or "@" in netloc:
        return ""
    host, _, port = netloc.partition(":")
    if port and not _PORT_RE.match(port):
        return ""
    try:
        host = host.encode("idna").decode("ascii")   # IDN -> punycode
    except UnicodeError:
        return ""
    if not _HOST_RE.match(host):
        return ""
    return f"{host}:{port}" if port else host


def canonical_url(url: str) -> str:
    """Dedupe key: also ignores http/https, www. and trailing slashes. Used for ids, not links."""
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
    """Only well-formed http(s) links to a plain DNS host ever reach the HTML
    (also re-checks items stored before clean_url was strict)."""
    url = (url or "").strip()
    if not url or _UNSAFE_CHARS_RE.search(url) or any(c in url for c in " \t\r\n\\"):
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not safe_netloc(parts.netloc):
        return ""
    return url


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
