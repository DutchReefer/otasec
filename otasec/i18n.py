"""UI strings and locale-aware date formatting (EN / NL)."""
from __future__ import annotations

from datetime import datetime

STRINGS = {
    "en": {
        "tagline": "OT & ICS security news, filtered for asset owners",
        "nav_home": "Live feed",
        "nav_briefings": "Briefings",
        "nav_about": "About",
        "todays_briefing": "Today's briefing",
        "latest_briefing": "Latest briefing",
        "read_briefing": "Read the full briefing",
        "no_briefing": "The first daily briefing hasn't been published yet.",
        "live_feed": "Live feed",
        "live_feed_sub": "Every OT/ICS-relevant story from {n} sources, updated hourly.",
        "filter_all": "All",
        "filter_search": "Search titles, vendors, CVEs…",
        "filter_sector": "All sectors",
        "filter_source": "All sources",
        "no_items": "No items match these filters.",
        "load_more": "Show more",
        "sources": "Sources",
        "source_count": {"one": "{n} source", "other": "{n} sources"},
        "x_mentions": {"one": "shared {n}× on X", "other": "shared {n}× on X"},
        "takeaway": "For asset owners",
        "briefing_archive": "Briefing archive",
        "briefing_archive_sub": "One briefing per morning: the day's most-covered OT/ICS stories, in English and Dutch.",
        "stories": {"one": "{n} story", "other": "{n} stories"},
        "updated": "Updated",
        "about_title": "About OTASEC",
        "source_status": "Source status",
        "status_ok": "OK",
        "status_fail": "Unavailable",
        "status_off": "Off",
        "last_checked": "last checked",
        "footer_note": "Summaries are machine-generated from the original sources; always follow the link and verify before acting.",
        "rss": "RSS",
        "rss_briefings": "Daily briefings (RSS)",
        "rss_news": "Live feed (RSS)",
        "not_found": "Page not found",
        "not_found_body": "That page doesn't exist (anymore).",
        "back_home": "Back to the live feed",
        "previous": "Previous",
        "next": "Next",
        "skip": "Skip to content",
        "group_title": "{n} advisories from {source}",
        "group_show": "Show all {n}",
        "categories": {
            "advisory": "Advisory", "incident": "Incident", "threat": "Threat intel",
            "regulation": "Regulation", "research": "Research", "industry": "Industry",
            "guidance": "Guidance",
        },
        "sectors": {
            "energy": "Energy", "water": "Water", "manufacturing": "Manufacturing",
            "oil_gas": "Oil & gas", "chemical": "Chemical", "transport": "Transport",
            "healthcare": "Healthcare", "building": "Building automation", "food": "Food",
            "government": "Government", "cross_sector": "Cross-sector",
        },
    },
    "nl": {
        "tagline": "OT- en ICS-securitynieuws, gefilterd voor asset owners",
        "nav_home": "Live feed",
        "nav_briefings": "Briefings",
        "nav_about": "Over",
        "todays_briefing": "Briefing van vandaag",
        "latest_briefing": "Laatste briefing",
        "read_briefing": "Lees de volledige briefing",
        "no_briefing": "De eerste dagelijkse briefing is nog niet gepubliceerd.",
        "live_feed": "Live feed",
        "live_feed_sub": "Elk OT/ICS-relevant bericht uit {n} bronnen, elk uur bijgewerkt.",
        "filter_all": "Alles",
        "filter_search": "Zoek op titel, leverancier, CVE…",
        "filter_sector": "Alle sectoren",
        "filter_source": "Alle bronnen",
        "no_items": "Geen berichten voor deze filters.",
        "load_more": "Meer tonen",
        "sources": "Bronnen",
        "source_count": {"one": "{n} bron", "other": "{n} bronnen"},
        "x_mentions": {"one": "{n}× gedeeld op X", "other": "{n}× gedeeld op X"},
        "takeaway": "Voor asset owners",
        "briefing_archive": "Briefing-archief",
        "briefing_archive_sub": "Elke ochtend één briefing: de meest besproken OT/ICS-verhalen van de dag, in het Nederlands en Engels.",
        "stories": {"one": "{n} verhaal", "other": "{n} verhalen"},
        "updated": "Bijgewerkt",
        "about_title": "Over OTASEC",
        "source_status": "Status van bronnen",
        "status_ok": "OK",
        "status_fail": "Niet bereikbaar",
        "status_off": "Uit",
        "last_checked": "laatst gecontroleerd",
        "footer_note": "Samenvattingen worden automatisch gegenereerd uit de oorspronkelijke bronnen; volg altijd de link en verifieer voordat je handelt.",
        "rss": "RSS",
        "rss_briefings": "Dagelijkse briefings (RSS)",
        "rss_news": "Live feed (RSS)",
        "not_found": "Pagina niet gevonden",
        "not_found_body": "Deze pagina bestaat niet (meer).",
        "back_home": "Terug naar de live feed",
        "previous": "Vorige",
        "next": "Volgende",
        "skip": "Naar de inhoud",
        "group_title": "{n} advisories van {source}",
        "group_show": "Toon alle {n}",
        "categories": {
            "advisory": "Advisory", "incident": "Incident", "threat": "Dreiging",
            "regulation": "Regelgeving", "research": "Onderzoek", "industry": "Markt",
            "guidance": "Richtlijn",
        },
        "sectors": {
            "energy": "Energie", "water": "Water", "manufacturing": "Maakindustrie",
            "oil_gas": "Olie & gas", "chemical": "Chemie", "transport": "Transport",
            "healthcare": "Zorg", "building": "Gebouwautomatisering", "food": "Voedsel",
            "government": "Overheid", "cross_sector": "Sectoroverstijgend",
        },
    },
}

_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "nl": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
}
_MONTHS_LONG = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"],
}
_WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "nl": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"],
}


def plural(lang: str, key: str, n: int) -> str:
    forms = STRINGS[lang][key]
    return (forms["one"] if n == 1 else forms["other"]).format(n=n)


def fmt_short(dt: datetime, lang: str) -> str:
    """'14 Oct, 09:12' / '14 okt, 09:12'."""
    return f"{dt.day} {_MONTHS[lang][dt.month - 1]}, {dt:%H:%M}"


def fmt_day(dt: datetime, lang: str) -> str:
    """'14 Oct' / '14 okt'."""
    return f"{dt.day} {_MONTHS[lang][dt.month - 1]}"


def fmt_long_date(dt: datetime, lang: str) -> str:
    """'Wednesday 14 October 2026' / 'woensdag 14 oktober 2026'."""
    return f"{_WEEKDAYS[lang][dt.weekday()]} {dt.day} {_MONTHS_LONG[lang][dt.month - 1]} {dt.year}"
