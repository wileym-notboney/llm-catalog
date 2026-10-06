# ABOUTME: Tests that each paid (Firecrawl) source is attempted at most once per UTC day.
# ABOUTME: Failures are simulated by raising inside a fake fetcher; calls are counted, not mocked.
import json
import logging
import sys
from datetime import datetime, timedelta, timezone

import pytest

from feed.pull import SOURCES, run_prune, run_pull
from feed.schedule import step
from feed.store import StoreError, read_json
from tests.fixtures import ANTHROPIC_MD, NOUS_MD
from tests.test_pull import NOW, feeds

URLS = {source["id"]: source["url"] for source in SOURCES}
SENTINEL_KEY = "fc-FAKE-SENTINEL-KEY"  # never a real key; must never reach any file or log
PAGES = {URLS["anthropic-news"]: ANTHROPIC_MD, URLS["nous-blog"]: NOUS_MD}


class ProcessDied(BaseException):
    """Stands in for SIGKILL/power loss: not an Exception, so no pull handler can catch it."""


class PaidFetcher:
    """Fake Firecrawl that counts calls per URL and can die on chosen URLs."""

    def __init__(self, die_on=()):
        self.calls: list[str] = []
        self.die_on = {URLS[source_id] for source_id in die_on}

    def __call__(self, url):
        self.calls.append(url)
        if url in self.die_on:
            raise ProcessDied
        return PAGES[url]

    def paid(self, source_id):
        return self.calls.count(URLS[source_id])


def pull(tmp_path, fetcher, now=NOW):
    return run_pull(tmp_path, now, feeds(), fetcher)


def attempts(tmp_path):
    return json.loads((tmp_path / "attempts.json").read_text())


def test_death_after_recording_but_before_the_request_never_retries_that_source(tmp_path):
    died = PaidFetcher(die_on=["anthropic-news"])
    with pytest.raises(ProcessDied):
        pull(tmp_path, died)
    assert died.paid("anthropic-news") == 1
    assert list(attempts(tmp_path)["attempts"]) == ["anthropic-news"]  # recorded before dying

    restarted = PaidFetcher()
    summary = pull(tmp_path, restarted)
    assert restarted.paid("anthropic-news") == 0
    assert restarted.paid("nous-blog") == 1  # the never-attempted paid source still gets its call
    assert summary["deferred"] == ["anthropic-news"]
    assert "anthropic-news" not in summary["failed"]


def test_death_during_the_second_paid_source_leaves_no_paid_retries(tmp_path):
    died = PaidFetcher(die_on=["nous-blog"])
    with pytest.raises(ProcessDied):
        pull(tmp_path, died)
    assert (died.paid("anthropic-news"), died.paid("nous-blog")) == (1, 1)
    restarted = PaidFetcher()
    pull(tmp_path, restarted)
    assert restarted.calls == []


def test_cli_pulls_and_scheduler_restarts_cannot_exceed_two_paid_calls_a_day(tmp_path):
    fetcher = PaidFetcher()
    pull(tmp_path, fetcher)
    pull(tmp_path, fetcher, NOW + timedelta(hours=1))
    for restart in range(3):  # a fresh scheduler step per "process start", catch-up always due
        due = NOW + timedelta(hours=2 + restart)
        step(tmp_path, due, datetime(2026, 10, 5, 0, 0).time(),
             lambda directory, moment: run_pull(directory, moment, feeds(), fetcher))
        (tmp_path / "state.json").unlink()  # force "never pulled" so every step really pulls
    assert len(fetcher.calls) == 2
    assert fetcher.paid("anthropic-news") == fetcher.paid("nous-blog") == 1


def test_the_next_utc_day_permits_one_new_attempt_per_source(tmp_path):
    fetcher = PaidFetcher()
    pull(tmp_path, fetcher, datetime(2026, 10, 5, 23, 59, tzinfo=timezone.utc))
    pull(tmp_path, fetcher, datetime(2026, 10, 5, 23, 59, 59, tzinfo=timezone.utc))
    assert len(fetcher.calls) == 2
    pull(tmp_path, fetcher, datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc))
    assert len(fetcher.calls) == 4


def test_a_deferred_source_keeps_its_items_and_renders_as_stale_but_not_failed(tmp_path):
    pull(tmp_path, PaidFetcher())
    before = {i["url"] for i in read_json(tmp_path / "items.json", {})["items"]}
    summary = pull(tmp_path, PaidFetcher(), NOW + timedelta(hours=1))
    catalog = read_json(tmp_path / "items.json", {})
    status = catalog["sources"]["anthropic-news"]
    assert status["lastError"].startswith("deferred:")  # UI marks stale on any lastError
    assert status["lastOk"] == "2026-10-05T12:00:00Z"  # last good pull is still reported
    assert before <= {i["url"] for i in catalog["items"]}
    assert set(summary["deferred"]) == {"anthropic-news", "nous-blog"}
    assert summary["failed"] == {}


def test_free_sources_still_refresh_while_paid_sources_are_deferred(tmp_path):
    pull(tmp_path, PaidFetcher())
    pull(tmp_path, PaidFetcher(), NOW + timedelta(hours=1))
    status = read_json(tmp_path / "items.json", {})["sources"]
    assert status["openai-news"] == {"lastOk": "2026-10-05T13:00:00Z", "lastError": None}


def test_attempts_file_has_exactly_source_date_and_time_and_leaks_nothing(tmp_path, caplog, monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", SENTINEL_KEY)
    caplog.set_level(logging.DEBUG)
    pull(tmp_path, PaidFetcher())
    pull(tmp_path, PaidFetcher(), NOW + timedelta(hours=1))
    assert attempts(tmp_path) == {"attempts": {
        source_id: {"date": "2026-10-05", "at": "2026-10-05T12:00:00Z"}
        for source_id in ("anthropic-news", "nous-blog")
    }}
    for name in ("items.json", "state.json"):
        text = (tmp_path / name).read_text()
        assert '"attempts"' not in text and SENTINEL_KEY not in text
    assert SENTINEL_KEY not in (tmp_path / "attempts.json").read_text()
    assert SENTINEL_KEY not in caplog.text


def test_no_api_key_records_no_attempt_because_nothing_was_spent(tmp_path):
    run_pull(tmp_path, NOW, feeds(), None)
    assert not (tmp_path / "attempts.json").exists()


BAD_ATTEMPTS = {
    "invalid json": "{oops",
    "top level list": "[]",
    "attempts is a list": '{"attempts": []}',
    "record is a string": '{"attempts": {"nous-blog": "today"}}',
    "bad date": '{"attempts": {"nous-blog": {"date": "yesterday", "at": "2026-10-05T12:00:00Z"}}}',
    "naive time": '{"attempts": {"nous-blog": {"date": "2026-10-05", "at": "2026-10-05T12:00:00"}}}',
}


@pytest.mark.parametrize("label", BAD_ATTEMPTS)
def test_an_untrustworthy_attempts_file_is_refused_not_read_as_no_attempts(tmp_path, label):
    (tmp_path / "attempts.json").write_text(BAD_ATTEMPTS[label])
    fetcher = PaidFetcher()
    with pytest.raises(StoreError, match="attempts.json"):
        pull(tmp_path, fetcher)
    assert fetcher.calls == []
    assert (tmp_path / "attempts.json").read_text() == BAD_ATTEMPTS[label]
    assert not (tmp_path / "items.json").exists()


def test_old_attempt_records_are_pruned_by_pull_and_by_prune(tmp_path):
    old = {"date": "2026-10-04", "at": "2026-10-04T12:00:00Z"}
    today = {"date": "2026-10-05", "at": "2026-10-05T01:00:00Z"}
    (tmp_path / "attempts.json").write_text(json.dumps({"attempts": {"a": old, "b": today}}))
    run_prune(tmp_path, NOW)
    assert attempts(tmp_path) == {"attempts": {"b": today}}
    (tmp_path / "attempts.json").write_text(json.dumps({"attempts": {"a": old, "b": today}}))
    pull(tmp_path, PaidFetcher())
    assert "a" not in attempts(tmp_path)["attempts"]


def write_record(tmp_path, source_id, day):
    record = {"date": day, "at": "2026-10-04T12:00:00Z"}
    (tmp_path / "attempts.json").write_text(json.dumps({"attempts": {source_id: record}}))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="compact ISO dates need 3.11+")
def test_a_compact_date_for_yesterday_is_not_mistaken_for_the_future(tmp_path):
    write_record(tmp_path, "anthropic-news", "20261004")  # yesterday; '1' > '-' as text
    fetcher = PaidFetcher()
    pull(tmp_path, fetcher)
    assert fetcher.paid("anthropic-news") == 1


def test_a_future_dated_record_defers_the_source_and_warns_by_name(tmp_path, caplog):
    write_record(tmp_path, "anthropic-news", "2026-10-06")
    fetcher = PaidFetcher()
    with caplog.at_level(logging.WARNING, logger="feed"):
        summary = pull(tmp_path, fetcher)
    assert fetcher.paid("anthropic-news") == 0
    assert "anthropic-news" in summary["deferred"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("anthropic-news" in r.getMessage() and "future" in r.getMessage() for r in warnings)
