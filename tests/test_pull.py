# ABOUTME: Tests for one full pull across all six sources, using injected fakes (no network).
# ABOUTME: Covers stale handling, empty-parse protection, tombstones and prune-failure safety.
from datetime import datetime, timezone

import pytest

import feed.pull as pull_module
from feed.pull import SOURCES, run_prune, run_pull
from feed.scrape_pages import FetchError
from feed.store import StoreError, read_json
from tests.fixtures import ANTHROPIC_MD, NOUS_MD, atom, rss

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
URLS = {source["id"]: source["url"] for source in SOURCES}
RECENT = "Mon, 05 Oct 2026 08:00:00 GMT"
FRESH = "2026-10-05T07:00:00Z"


def feeds(**overrides):
    base = {
        "anthropic-api-notes": rss(("API notes", "https://platform.claude.com/n#1", RECENT)),
        "claude-code-releases": atom(("v2.1.290", "https://github.com/c/v2.1.290", FRESH)),
        "openai-news": rss(("OpenAI post", "https://openai.com/index/p", RECENT)),
        "hermes-agent-releases": atom(
            ("v0.21.4+canary.1", "https://github.com/h/canary", FRESH),
            ("rc.35-v0.21.5", "https://github.com/h/rc35", FRESH),
            ("abandoned-rc.34-v0.21.5", "https://github.com/h/abandoned", FRESH),
            ("v0.21.3", "https://github.com/h/v0.21.3", FRESH),
        ),
    }
    base.update(overrides)
    by_url = {URLS[key]: value for key, value in base.items()}

    def fetch_xml(url):
        value = by_url[url]
        if isinstance(value, Exception):
            raise value
        return value

    return fetch_xml


def pages(**overrides):
    base = {"anthropic-news": ANTHROPIC_MD, "nous-blog": NOUS_MD}
    base.update(overrides)
    by_url = {URLS[key]: value for key, value in base.items()}
    return lambda url: by_url[url]


def run(tmp_path, fetch_xml=None, fetch_md="default", now=NOW):
    return run_pull(
        tmp_path, now, fetch_xml or feeds(), pages() if fetch_md == "default" else fetch_md
    )


def urls(tmp_path):
    return {entry["url"] for entry in read_json(tmp_path / "items.json", {})["items"]}


def test_a_clean_pull_ingests_every_source_and_hides_canaries(tmp_path):
    summary = run(tmp_path)
    assert summary["failed"] == {} and len(summary["ok"]) == 6
    found = urls(tmp_path)
    assert "https://github.com/h/v0.21.3" in found
    assert not found & {"https://github.com/h/canary", "https://github.com/h/rc35",
                        "https://github.com/h/abandoned"}
    assert "https://nousresearch.com/lighthouse-attention" in found
    catalog = read_json(tmp_path / "items.json", {})
    assert catalog["sources"]["openai-news"] == {"lastOk": "2026-10-05T12:00:00Z", "lastError": None}
    assert read_json(tmp_path / "state.json", {})["lastPull"] == "2026-10-05T12:00:00Z"


def test_a_failing_source_keeps_its_old_items_and_is_marked_stale(tmp_path):
    run(tmp_path)
    broken = feeds(**{"openai-news": FetchError("HTTP 503")})
    summary = run(tmp_path, broken)
    assert summary["failed"] == {"openai-news": "HTTP 503"}
    assert "https://openai.com/index/p" in urls(tmp_path)
    assert read_json(tmp_path / "items.json", {})["sources"]["openai-news"]["lastError"] == "HTTP 503"


def test_malformed_xml_is_a_stale_source_not_a_crash(tmp_path):
    summary = run(tmp_path, feeds(**{"openai-news": "<rss><channel>"}))
    assert "openai-news" in summary["failed"] and len(summary["ok"]) == 5


def test_a_layout_change_that_parses_zero_items_is_stale_and_keeps_old_items(tmp_path):
    run(tmp_path)
    summary = run(tmp_path, fetch_md=pages(**{"nous-blog": "<html>redesigned</html>"}))
    assert summary["failed"] == {"nous-blog": "parsed 0 items"}
    assert "https://nousresearch.com/lighthouse-attention" in urls(tmp_path)


def test_without_a_firecrawl_key_only_the_two_scraped_sources_go_stale(tmp_path):
    summary = run(tmp_path, fetch_md=None)
    assert set(summary["failed"]) == {"anthropic-news", "nous-blog"}
    assert summary["failed"]["nous-blog"] == "FIRECRAWL_API_KEY not set"
    assert len(summary["ok"]) == 4


def test_pruned_items_are_not_reingested_by_the_next_pull(tmp_path):
    many = rss(*[(f"Old {n}", f"https://openai.com/old/{n}", "Mon, 01 Jun 2026 08:00:00 GMT")
                 for n in range(5)])
    run(tmp_path, feeds(**{"openai-news": many}))
    first = urls(tmp_path)
    run(tmp_path, feeds(**{"openai-news": many}))
    assert urls(tmp_path) == first
    assert sum(url.startswith("https://openai.com/old/") for url in first) == 3
    assert len(read_json(tmp_path / "state.json", {})["tombstones"]) >= 2


def test_undated_items_get_first_seen_and_are_not_pruned_on_day_one(tmp_path):
    run(tmp_path)
    nous = [e for e in read_json(tmp_path / "items.json", {})["items"] if e["source"] == "nous-blog"]
    assert len(nous) == 2
    assert all(e["publishedAt"] is None and e["firstSeenAt"] == "2026-10-05T12:00:00Z" for e in nous)


def test_a_prune_crash_still_saves_the_merged_items(tmp_path, monkeypatch):
    monkeypatch.setattr(pull_module, "prune", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    run(tmp_path)
    assert "https://openai.com/index/p" in urls(tmp_path)


def test_a_corrupt_items_file_aborts_without_overwriting_it(tmp_path):
    (tmp_path / "items.json").write_text("{oops")
    with pytest.raises(StoreError):
        run(tmp_path)
    assert (tmp_path / "items.json").read_text() == "{oops"


def test_run_prune_works_offline_on_stored_data(tmp_path):
    many = rss(*[(f"Old {n}", f"https://openai.com/old/{n}", "Mon, 01 Jun 2026 08:00:00 GMT")
                 for n in range(5)])
    run(tmp_path, feeds(**{"openai-news": many}))
    assert run_prune(tmp_path, NOW) == 0


def test_invalid_utf8_from_one_feed_stales_only_that_source(tmp_path):
    good = feeds()

    def fetch_xml(url):
        if url == URLS["openai-news"]:
            return b"\xff\xfe<rss>".decode("utf-8")  # what fetch_text does with a bad body
        return good(url)

    result = run(tmp_path, fetch_xml=fetch_xml)
    assert list(result["failed"]) == ["openai-news"]
    assert len(result["ok"]) == 5
    assert "https://openai.com/index/p" not in urls(tmp_path)
    assert "https://platform.claude.com/n#1" in urls(tmp_path)


def test_fetch_text_rejects_an_over_limit_feed_without_reading_it_all(monkeypatch):
    class Endless:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        sizes = []

        def read(self, size=-1):
            assert size > 0, "unbounded read"
            self.sizes.append(size)
            return b"x" * size

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Endless())
    with pytest.raises(FetchError, match="16 MiB"):
        pull_module.fetch_text("https://example.com/feed.xml")
    assert max(Endless.sizes) <= 16 * 1024 * 1024 + 1
