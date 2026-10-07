# ABOUTME: Tests for one full pull across all five sources, using injected fakes (no network).
# ABOUTME: Covers stale handling, empty-parse protection, tombstones and prune-failure safety.
import json
from datetime import datetime, timedelta, timezone

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
        "claude-code-releases": atom(
            ("v2.1.290", "https://github.com/c/v2.1.290", FRESH),
            ("v2.1.291+canary.1", "https://github.com/c/canary", FRESH),
            ("rc.35-v2.1.292", "https://github.com/c/rc35", FRESH),
            ("abandoned-rc.34-v2.1.292", "https://github.com/c/abandoned", FRESH),
        ),
        "openai-news": rss(("OpenAI post", "https://openai.com/index/p", RECENT)),
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
    assert summary["failed"] == {} and len(summary["ok"]) == 5
    found = urls(tmp_path)
    assert "https://github.com/c/v2.1.290" in found
    assert not found & {"https://github.com/c/canary", "https://github.com/c/rc35",
                        "https://github.com/c/abandoned"}
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
    assert "openai-news" in summary["failed"] and len(summary["ok"]) == 4


def test_a_layout_change_that_parses_zero_items_is_stale_and_keeps_old_items(tmp_path):
    run(tmp_path)
    next_day = NOW + timedelta(days=1)  # a paid source is requested once per UTC day
    summary = run(tmp_path, fetch_md=pages(**{"nous-blog": "<html>redesigned</html>"}), now=next_day)
    assert summary["failed"] == {"nous-blog": "parsed 0 items"}
    assert "https://nousresearch.com/lighthouse-attention" in urls(tmp_path)


def test_without_a_firecrawl_key_only_the_two_scraped_sources_go_stale(tmp_path):
    summary = run(tmp_path, fetch_md=None)
    assert set(summary["failed"]) == {"anthropic-news", "nous-blog"}
    assert summary["failed"]["nous-blog"] == "FIRECRAWL_API_KEY not set"
    assert len(summary["ok"]) == 3


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


GOOD_ITEM = {
    "id": "a", "lab": "openai", "kind": "news", "title": "t", "summary": "", "url": "https://x/a",
    "publishedAt": "2026-10-04T08:00:00Z", "source": "openai-news",
    "firstSeenAt": "2026-10-04T09:00:00Z",
}
GOOD_CATALOG = {"generatedAt": None, "sources": {}, "items": [GOOD_ITEM]}
GOOD_STATE = {"lastPull": None, "lastPrune": None, "tombstones": {"z": "2026-10-01T00:00:00Z"}}
BAD_CATALOGS = {
    "empty object": {},
    "array": [],
    "items not a list": {"sources": {}, "items": {}},
    "sources not a dict": {"sources": [], "items": []},
    "item missing firstSeenAt": {"sources": {}, "items": [{**GOOD_ITEM, "firstSeenAt": None}]},
    "item missing publishedAt": {
        "sources": {}, "items": [{k: v for k, v in GOOD_ITEM.items() if k != "publishedAt"}]},
    "item bad publishedAt": {"sources": {}, "items": [{**GOOD_ITEM, "publishedAt": "yesterday"}]},
    "source status not a dict": {"sources": {"s": "bad"}, "items": []},
    "source bad lastOk": {"sources": {"s": {"lastOk": "never"}}, "items": []},
}
BAD_STATES = {
    "empty object": {},
    "array": [],
    "tombstones not a dict": {"tombstones": []},
    "bad tombstone timestamp": {"tombstones": {"z": "soon"}},
    "null tombstone timestamp": {"tombstones": {"z": None}},
    "bad lastPull": {"lastPull": 5, "tombstones": {}},
}


def write_files(tmp_path, catalog, state):
    for name, content in (("items.json", catalog), ("state.json", state)):
        (tmp_path / name).write_text(json.dumps(content))
    return {name: (tmp_path / name).read_bytes() for name in ("items.json", "state.json")}


@pytest.mark.parametrize("operation", ["pull", "prune"])
@pytest.mark.parametrize("label", BAD_CATALOGS)
def test_a_misshapen_items_file_is_refused_and_both_files_stay_untouched(
    tmp_path, label, operation
):
    before = write_files(tmp_path, BAD_CATALOGS[label], GOOD_STATE)
    with pytest.raises(StoreError, match="items.json"):
        run(tmp_path) if operation == "pull" else run_prune(tmp_path, NOW)
    assert {n: (tmp_path / n).read_bytes() for n in before} == before


@pytest.mark.parametrize("operation", ["pull", "prune"])
@pytest.mark.parametrize("label", BAD_STATES)
def test_a_misshapen_state_file_is_refused_and_both_files_stay_untouched(
    tmp_path, label, operation
):
    before = write_files(tmp_path, GOOD_CATALOG, BAD_STATES[label])
    with pytest.raises(StoreError, match="state.json"):
        run(tmp_path) if operation == "pull" else run_prune(tmp_path, NOW)
    assert {n: (tmp_path / n).read_bytes() for n in before} == before


def test_unknown_fields_survive_a_pull_and_a_prune(tmp_path):
    catalog = {**GOOD_CATALOG, "futureCatalogKey": [1],
               "items": [{**GOOD_ITEM, "futureField": "kept"}]}
    state = {**GOOD_STATE, "futureStateKey": {"n": 1}}
    write_files(tmp_path, catalog, state)
    run(tmp_path)
    run_prune(tmp_path, NOW)
    saved_catalog = read_json(tmp_path / "items.json", {})
    saved_state = read_json(tmp_path / "state.json", {})
    assert saved_catalog["futureCatalogKey"] == [1]
    assert next(e for e in saved_catalog["items"] if e["id"] == "a")["futureField"] == "kept"
    assert saved_state["futureStateKey"] == {"n": 1}
    assert saved_state["tombstones"]["z"] == "2026-10-01T00:00:00Z"


def test_a_valid_catalog_and_state_round_trip_through_prune_unchanged(tmp_path):
    write_files(tmp_path, GOOD_CATALOG, GOOD_STATE)
    assert run_prune(tmp_path, NOW) == 0
    assert read_json(tmp_path / "items.json", {}) == GOOD_CATALOG
    expected_state = {**GOOD_STATE, "lastPrune": "2026-10-05T12:00:00Z"}
    assert read_json(tmp_path / "state.json", {}) == expected_state


def test_invalid_utf8_from_one_feed_stales_only_that_source(tmp_path):
    good = feeds()

    def fetch_xml(url):
        if url == URLS["openai-news"]:
            return b"\xff\xfe<rss>".decode("utf-8")  # what fetch_text does with a bad body
        return good(url)

    result = run(tmp_path, fetch_xml=fetch_xml)
    assert list(result["failed"]) == ["openai-news"]
    assert len(result["ok"]) == 4
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
