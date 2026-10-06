# ABOUTME: Tests for when the daily pull is due and for the scheduler's failure backoff.
# ABOUTME: Includes the catch-up rule that lets a machine that was off still pull on start.
from datetime import datetime, time, timezone

import pytest

from feed.schedule import BACKOFF_SECONDS, TICK_SECONDS, parse_pull_at, pull_due, step
from feed.store import write_json

SLOT = time(6, 0)


def at(day, hour, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=timezone.utc)


def test_never_pulled_is_due():
    assert pull_due(None, at(5, 3), SLOT)


def test_not_due_before_todays_slot_when_yesterdays_pull_is_recent():
    assert not pull_due(at(4, 6, 1), at(5, 5, 59), SLOT)


def test_due_once_todays_slot_passes():
    assert pull_due(at(4, 6, 1), at(5, 6, 0), SLOT)


def test_not_due_again_after_todays_slot_was_served():
    assert not pull_due(at(5, 6, 0, 30), at(5, 6, 10), SLOT)


def test_catch_up_pull_when_the_machine_was_off_over_a_day():
    assert pull_due(at(3, 12), at(5, 3), SLOT)  # 39h stale, still before today's slot


def test_parse_pull_at():
    assert parse_pull_at("06:00") == time(6, 0)
    for bad in ("25:00", "6", "noon"):
        with pytest.raises(ValueError):
            parse_pull_at(bad)


def test_step_pulls_when_due_and_waits_a_tick(tmp_path):
    calls = []
    wait = step(tmp_path, at(5, 7), SLOT, lambda d, n: calls.append(n) or {"ok": [], "failed": {}})
    assert wait == TICK_SECONDS and calls == [at(5, 7)]


def test_step_skips_when_not_due(tmp_path):
    write_json(tmp_path / "state.json", {"lastPull": "2026-10-05T06:00:30Z"})
    calls = []
    assert step(tmp_path, at(5, 7), SLOT, lambda d, n: calls.append(n)) == TICK_SECONDS
    assert calls == []


def test_a_crashing_pull_backs_off_an_hour_instead_of_retrying_every_minute(tmp_path):
    def crash(directory, now):
        raise RuntimeError("disk full after a paid scrape")

    assert step(tmp_path, at(5, 7), SLOT, crash) == BACKOFF_SECONDS
