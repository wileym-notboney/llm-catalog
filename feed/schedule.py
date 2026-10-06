# ABOUTME: Decides when the daily pull is due and runs one scheduler step with failure backoff.
# ABOUTME: Pure time logic, so the catch-up and retry rules are testable without sleeping.
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

from feed.items import parse_iso
from feed.store import WriterBusy, read_json, validate_state

log = logging.getLogger("feed")

TICK_SECONDS = 60
BACKOFF_SECONDS = 3600
CATCH_UP_AFTER = timedelta(hours=24)


def parse_pull_at(value: str) -> time:
    """Parse 'HH:MM' (UTC). Raises ValueError on anything else."""
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def pull_due(last_pull: datetime | None, now: datetime, pull_at: time) -> bool:
    """Due if never pulled, if today's slot has passed unserved, or if over 24h stale."""
    if last_pull is None or now - last_pull > CATCH_UP_AFTER:
        return True
    slot = datetime.combine(now.date(), pull_at, tzinfo=timezone.utc)
    return now >= slot and last_pull < slot


def step(
    data_dir: Path, now: datetime, pull_at: time, pull: Callable[[Path, datetime], dict]
) -> int:
    """Run the pull if due. Returns seconds to wait before the next step.

    An exception backs off for an hour: a crash after a paid scrape must not re-scrape
    every minute and burn credits.
    """
    try:
        state = read_json(data_dir / "state.json", {}, validate_state)
        last = parse_iso(state["lastPull"]) if state.get("lastPull") else None
        if pull_due(last, now, pull_at):
            summary = pull(data_dir, now)
            log.info("pull finished: ok=%s failed=%s", summary["ok"], list(summary["failed"]))
        return TICK_SECONDS
    except WriterBusy:  # before the blanket handler: nothing crashed, so no backoff
        log.warning("another writer owns the data directory; skipping this pull")
        return TICK_SECONDS
    except Exception:
        log.exception("scheduled pull crashed; backing off %ss", BACKOFF_SECONDS)
        return BACKOFF_SECONDS
