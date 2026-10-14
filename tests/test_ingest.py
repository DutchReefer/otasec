from conftest import FIXTURES, make_item

from otasec import xsource
from otasec.feeds import parse_feed
from otasec.normalize import canonical_url, clean_text, extract_cves, item_id, safe_url
from otasec.pipeline import merge_items

FEED = {"id": "ex", "name": "Example OT News", "lang": "en", "kind": "news", "focus": "ot"}


def test_canonical_url_strips_tracking_and_fragment():
    a = canonical_url("https://www.Example.com/news/plc-flaw/?utm_source=rss&id=7#comments")
    assert a == "https://example.com/news/plc-flaw?id=7"
    assert item_id("http://example.com/news/plc-flaw?id=7&utm_medium=x") == item_id(a)
    assert canonical_url("javascript:alert(1)") == ""


def test_clean_text_and_cves():
    assert clean_text("<p>Hi &amp; bye</p> The post X appeared first on Y.") == "Hi & bye"
    assert extract_cves("cve-2026-0001 and CVE-2026-12345, CVE-2026-0001") == ["CVE-2026-0001", "CVE-2026-12345"]
    assert safe_url("javascript:alert(1)") == ""
    assert safe_url("https://ok.example") == "https://ok.example"


def test_parse_rss():
    items = parse_feed((FIXTURES / "rss_sample.xml").read_bytes(), FEED)
    titles = [i["title"] for i in items]
    assert "Example: PLC firmware flaw patched" in titles
    assert "Bad scheme" not in titles  # javascript: link dropped
    assert all(i["url"].startswith("https://") for i in items)
    first = next(i for i in items if "PLC" in i["title"])
    assert first["cves"] == ["CVE-2026-12345", "CVE-2026-0001"]
    assert "appeared first" not in first["excerpt"]
    assert first["published"] == "2026-10-13T08:28:51Z"
    assert any(i["title"] == "Undated item" for i in items)  # gets fetch time


def test_parse_atom():
    items = parse_feed((FIXTURES / "atom_sample.xml").read_bytes(), FEED)
    assert len(items) == 1 and items[0]["url"] == "https://cert.example.com/ssa-000001.html"
    assert items[0]["cves"] == ["CVE-2026-22222"]


def test_merge_keeps_existing_classification():
    old = make_item(1)
    fresh = dict(old, cls=None, title="changed")
    merged, added = merge_items([old], [fresh, make_item(2)])
    assert added == 1
    assert next(i for i in merged if i["id"] == "id1")["cls"] is not None


def test_x_signals_merge():
    known = make_item(1, url="https://example.com/a/1", id=item_id("https://example.com/a/1"))
    payload = {
        "data": [
            {"id": "100", "author_id": "u1", "text": "Big ICS story https://t.co/x",
             "created_at": "2026-10-14T08:00:00.000Z", "public_metrics": {"like_count": 3, "retweet_count": 1},
             "entities": {"urls": [{"expanded_url": "https://example.com/a/1?utm_source=x"}]}},
            {"id": "101", "author_id": "u2", "text": "New SCADA research",
             "created_at": "2026-10-14T09:00:00.000Z",
             "entities": {"urls": [
                 {"expanded_url": "https://research.example.org/scada", "title": "SCADA research", "description": "desc"},
                 {"expanded_url": "https://x.com/someone/status/1"}]}},
        ],
        "includes": {"users": [{"id": "u1", "username": "alice"}, {"id": "u2", "username": "bob"}]},
    }
    signals = xsource.posts_to_signals(payload)
    assert len(signals) == 2  # x.com link skipped
    new = xsource.merge_signals([known], signals)
    assert known["x_mentions"] == 1 and known["x_handles"] == ["alice"]
    assert len(new) == 1 and new[0]["source"] == "research.example.org" and new[0]["x_handles"] == ["bob"]
    assert new[0]["cls"] is None


def test_x_collect_respects_missing_token():
    items, status = xsource.collect("", {"enabled": True}, {}, [])
    assert items == [] and status["ok"] is None
