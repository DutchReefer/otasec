"""JSON file store: items, briefings and source health. No database.

data/items.json          rolling list of news items (newest first)
data/briefings/<date>.json  one daily briefing per file
data/health.json         per-source fetch status + pipeline state (X since_id etc.)
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data) -> None:
    """Atomic write: temp file + rename, so a half-written file is never published."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, path)


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.items_path = data_dir / "items.json"
        self.health_path = data_dir / "health.json"
        self.briefings_dir = data_dir / "briefings"

    # --- items -------------------------------------------------------------
    def load_items(self) -> list[dict]:
        return read_json(self.items_path, [])

    def save_items(self, items: list[dict], retention_days: int) -> list[dict]:
        cutoff = utcnow() - timedelta(days=retention_days)
        kept = [i for i in items if (parse_iso(i.get("published")) or utcnow()) >= cutoff]
        kept.sort(key=lambda i: i.get("published") or "", reverse=True)
        write_json(self.items_path, kept)
        return kept

    # --- health / state ------------------------------------------------------
    def load_health(self) -> dict:
        return read_json(self.health_path, {"sources": {}, "state": {}})

    def save_health(self, health: dict) -> None:
        write_json(self.health_path, health)

    # --- briefings -----------------------------------------------------------
    def briefing_path(self, date: str) -> Path:
        return self.briefings_dir / f"{date}.json"

    def has_briefing(self, date: str) -> bool:
        return self.briefing_path(date).is_file()

    def save_briefing(self, briefing: dict) -> None:
        write_json(self.briefing_path(briefing["date"]), briefing)

    def load_briefing(self, date: str) -> dict | None:
        b = read_json(self.briefing_path(date), None)
        return b if isinstance(b, dict) else None

    def load_briefings(self) -> list[dict]:
        """All briefings, newest first."""
        if not self.briefings_dir.is_dir():
            return []
        out = []
        for p in sorted(self.briefings_dir.glob("*.json"), reverse=True):
            b = read_json(p, None)
            if isinstance(b, dict) and b.get("date"):
                out.append(b)
        return out
