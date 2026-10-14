"""Load configuration from config/*.yaml and environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
DIST_DIR = ROOT / "dist"


def _load_env_file(path: Path) -> None:
    """Minimal .env loader for local runs (KEY=VALUE, # comments). Never overrides real env."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass
class Config:
    site: dict
    sources: dict
    data_dir: Path = DATA_DIR
    dist_dir: Path = DIST_DIR
    anthropic_key: str = ""
    x_bearer: str = ""
    models: dict = field(default_factory=dict)

    @property
    def languages(self) -> list[str]:
        return list(self.site["languages"].keys())

    @property
    def feeds(self) -> list[dict]:
        return self.sources.get("feeds", [])

    def feed_by_id(self, source_id: str) -> dict | None:
        return next((f for f in self.feeds if f["id"] == source_id), None)


def load_config(data_dir: Path | None = None, dist_dir: Path | None = None) -> Config:
    _load_env_file(ROOT / ".env")
    site = yaml.safe_load((CONFIG_DIR / "site.yaml").read_text(encoding="utf-8"))
    sources = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))
    models = dict(site.get("models", {}))
    models["classify"] = os.environ.get("OTASEC_CLASSIFY_MODEL") or models.get("classify")
    models["briefing"] = os.environ.get("OTASEC_BRIEFING_MODEL") or models.get("briefing")
    return Config(
        site=site,
        sources=sources,
        data_dir=data_dir or DATA_DIR,
        dist_dir=dist_dir or DIST_DIR,
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        x_bearer=os.environ.get("X_BEARER_TOKEN", "").strip(),
        models=models,
    )
