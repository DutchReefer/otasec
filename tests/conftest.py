import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).parent / "fixtures"

from otasec.config import load_config  # noqa: E402
from otasec.store import Store, iso, utcnow  # noqa: E402


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    c = load_config(data_dir=tmp_path / "data", dist_dir=tmp_path / "dist")
    c.anthropic_key = ""
    c.x_bearer = ""
    return c


@pytest.fixture
def store(cfg):
    return Store(cfg.data_dir)


def make_item(n, **kw):
    base = {
        "id": f"id{n}",
        "url": f"https://example.com/a/{n}",
        "title": f"Example item {n}",
        "excerpt": "Example excerpt.",
        "source_id": "industrialcyber",
        "source": f"Source {n % 3}",
        "lang": "en",
        "kind": "news",
        "focus": "ot",
        "published": iso(utcnow()),
        "fetched": iso(utcnow()),
        "cves": [],
        "x_mentions": 0,
        "cls": {"relevant": True, "score": 50, "category": "advisory", "sectors": ["energy"],
                "vendors": ["ExampleVendor"], "summary": {"en": "EN summary.", "nl": "NL samenvatting."},
                "model": "test", "at": iso(utcnow())},
    }
    base.update(kw)
    return base
