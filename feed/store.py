# ABOUTME: Persistence and retention rules: atomic JSON files, merge by id, prune with tombstones.
# ABOUTME: Pure functions over plain dicts so the rules are testable without touching a network.
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from feed.items import iso, parse_iso

RETENTION = timedelta(days=10)
FLOOR_PER_LAB = 3
TOMBSTONE_TTL = timedelta(days=90)


class StoreError(Exception):
    """A data file exists but cannot be trusted. We refuse to overwrite it."""


def _check_iso(value: object, where: str, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    try:
        if parse_iso(value).tzinfo is None:  # a naive time cannot be compared with `now`
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise ValueError(
            f"{where} must be a timezone-aware ISO-8601 timestamp, got {value!r}"
        ) from None


def _check_type(value: object, kind: type, where: str) -> None:
    if not isinstance(value, kind):
        raise ValueError(f"{where} must be a {kind.__name__}")


# Validators check only what merge/prune/the UI read. Unknown top-level keys and unknown
# item fields are deliberately accepted and never stripped: later hardening tickets add
# fields to these files, and an older build must not reject or discard them.
def validate_catalog(data: object) -> None:
    """Raise ValueError if `data` is not a usable items.json catalog."""
    _check_type(data, dict, "catalog")
    _check_type(data.get("sources"), dict, "'sources'")
    _check_type(data.get("items"), list, "'items'")
    _check_iso(data.get("generatedAt"), "'generatedAt'", nullable=True)
    for source_id, status in data["sources"].items():
        _check_type(status, dict, f"source {source_id!r}")
        _check_iso(status.get("lastOk"), f"source {source_id!r} lastOk", nullable=True)
    for position, entry in enumerate(data["items"]):
        where = f"item #{position}"
        _check_type(entry, dict, where)
        for key in ("id", "lab"):
            _check_type(entry.get(key), str, f"{where} '{key}'")
        _check_iso(entry.get("firstSeenAt"), f"{where} firstSeenAt")
        if "publishedAt" not in entry:
            raise ValueError(f"{where} is missing 'publishedAt'")
        _check_iso(entry["publishedAt"], f"{where} publishedAt", nullable=True)


def validate_state(data: object) -> None:
    """Raise ValueError if `data` is not a usable state.json."""
    _check_type(data, dict, "state")
    _check_type(data.get("tombstones"), dict, "'tombstones'")
    for key in ("lastPull", "lastPrune"):
        _check_iso(data.get(key), f"'{key}'", nullable=True)
    for item_id, stamp in data["tombstones"].items():
        _check_iso(stamp, f"tombstone {item_id!r}")


def read_json(path: Path, default: dict, validate: Callable[[object], None] | None = None) -> dict:
    """Read a data file. Anything unreadable or misshapen raises StoreError naming `path`."""
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as error:
        raise StoreError(f"{path} is not valid JSON ({error}); fix or remove it") from None
    if validate:
        try:
            validate(data)
        except ValueError as error:
            raise StoreError(f"{path} has an invalid shape: {error}; fix or remove it") from None
    return data


def write_json(path: Path, data: dict) -> None:
    """Write to a temp file then rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
    os.replace(temp, path)


def item_time(item: dict) -> datetime:
    """Publication time, or first-seen time for items the source never dated."""
    return parse_iso(item["publishedAt"] or item["firstSeenAt"])


def merge(items: list[dict], incoming: list[dict], tombstones: dict, now: datetime) -> list[dict]:
    """Add or refresh items by id. Tombstoned ids are skipped; firstSeenAt never changes."""
    by_id = {item["id"]: item for item in items}
    for new in incoming:
        if new["id"] in tombstones:
            continue
        previous = by_id.get(new["id"])
        new["firstSeenAt"] = previous["firstSeenAt"] if previous else iso(now)
        by_id[new["id"]] = new
    return sorted(by_id.values(), key=item_time, reverse=True)


def prune(items: list[dict], tombstones: dict, now: datetime) -> tuple[list[dict], dict]:
    """Drop items past RETENTION, but always keep the newest FLOOR_PER_LAB of each lab.

    Dropped ids become tombstones so the next pull cannot re-ingest them from a source
    that still lists them. Tombstones older than TOMBSTONE_TTL expire.
    """
    cutoff = now - RETENTION
    protected: set[str] = set()
    for lab in {item["lab"] for item in items}:
        newest = sorted(
            (item for item in items if item["lab"] == lab), key=item_time, reverse=True
        )
        protected.update(item["id"] for item in newest[:FLOOR_PER_LAB])
    kept, dropped = [], []
    for item in items:
        (kept if item["id"] in protected or item_time(item) >= cutoff else dropped).append(item)
    fresh = {
        item_id: stamp
        for item_id, stamp in tombstones.items()
        if parse_iso(stamp) >= now - TOMBSTONE_TTL
    }
    fresh.update({item["id"]: iso(now) for item in dropped})
    return kept, fresh
