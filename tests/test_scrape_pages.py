# ABOUTME: Tests for the Firecrawl client and the two markdown page parsers.
# ABOUTME: The client tests fake urlopen, so no credit is ever spent by the test suite.
import io
import json
import urllib.error

import pytest

from feed.scrape_pages import FetchError, firecrawl_markdown, parse_anthropic_news, parse_nous_blog
from tests.fixtures import ANTHROPIC_MD, NOUS_MD


def test_anthropic_news_parses_hero_and_list_and_dedupes_by_url():
    items = {item["url"]: item for item in parse_anthropic_news(ANTHROPIC_MD)}
    assert len(items) == 3
    sonnet = items["https://www.anthropic.com/claude-sonnet-5-5"]
    assert sonnet["title"] == "Introducing Claude Sonnet 5.5"
    assert sonnet["summary"] == "A clear upgrade over Sonnet 5."
    assert sonnet["publishedAt"] == "2026-09-28T00:00:00Z"
    opus = items["https://www.anthropic.com/claude-opus-5-5"]
    assert opus["title"] == "Introducing Claude Opus 5.5"
    assert opus["summary"].startswith("Opus 5.5 performs")
    academy = items["https://www.anthropic.com/news/claude-frontier-academy"]
    assert academy["title"].startswith("Anthropic invests $100 million")
    assert academy["publishedAt"] == "2026-10-02T00:00:00Z"
    assert all(item["lab"] == "anthropic" and item["kind"] == "news" for item in items.values())


def test_anthropic_news_ignores_links_without_a_date():
    assert parse_anthropic_news("[See more](https://www.anthropic.com/news#)") == []


def test_nous_blog_takes_featured_posts_only_and_leaves_them_undated():
    items = parse_nous_blog(NOUS_MD)
    assert [item["title"] for item in items] == [
        "Refactoring Hermes with 1,393 agents",
        "Lighthouse Attention",
    ]
    assert items[0]["summary"].startswith("Hermes Agent autonomously")
    assert all(item["publishedAt"] is None and item["lab"] == "nous" for item in items)


def test_parsers_return_nothing_for_an_unrecognised_layout():
    assert parse_anthropic_news("<html>redesigned</html>") == []
    assert parse_nous_blog("<html>redesigned</html>") == []


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_firecrawl_markdown_posts_the_documented_request(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data)
        return _Response(json.dumps({"success": True, "data": {"markdown": "# hi"}}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert firecrawl_markdown("https://example.com", "fc-key") == "# hi"
    assert seen["url"] == "https://api.firecrawl.dev/v2/scrape"
    assert seen["auth"] == "Bearer fc-key"
    assert seen["body"] == {
        "url": "https://example.com",
        "formats": ["markdown"],
        "onlyMainContent": True,
        "maxAge": 0,
    }


def test_firecrawl_errors_never_leak_the_api_key(monkeypatch):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 402, "Payment Required", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(FetchError) as caught:
        firecrawl_markdown("https://example.com", "fc-secret")
    assert str(caught.value) == "Firecrawl HTTP 402"
    assert "fc-secret" not in repr(caught.value)


def test_firecrawl_rejects_an_empty_result(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _Response(json.dumps({"success": True, "data": {}}).encode()),
    )
    with pytest.raises(FetchError, match="no markdown"):
        firecrawl_markdown("https://example.com", "k")


SENTINEL_KEY = "fc-SENTINEL-not-a-real-key"


@pytest.mark.parametrize(
    "raw",
    [b"\x80\x81 not utf-8", b"[1, 2]", b'"text"', b'{"success": true, "data": "x"}',
     b'{"success": true, "data": {"markdown": 5}}'],
)
def test_firecrawl_bad_payloads_are_safe_fetch_errors(monkeypatch, raw):
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: _Response(raw))
    with pytest.raises(FetchError) as caught:
        firecrawl_markdown("https://example.com", SENTINEL_KEY)
    message = str(caught.value)
    assert SENTINEL_KEY not in message
    assert "Authorization" not in message and "Bearer" not in message


def test_firecrawl_rejects_an_over_limit_body_without_reading_it_all(monkeypatch):
    class Endless(_Response):
        read_sizes = []

        def read(self, size=-1):
            assert size > 0, "unbounded read"
            self.read_sizes.append(size)
            return b"x" * size

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Endless())
    with pytest.raises(FetchError, match="8 MiB") as caught:
        firecrawl_markdown("https://example.com", SENTINEL_KEY)
    assert SENTINEL_KEY not in str(caught.value)
    assert max(Endless.read_sizes) <= 8 * 1024 * 1024 + 1
