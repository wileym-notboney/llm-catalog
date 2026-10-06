# ABOUTME: Persistence and retention rules: atomic JSON files, merge by id, prune with tombstones.
# ABOUTME: Pure functions over plain dicts so the rules are testable without touching a network.
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from feed.items import iso, parse_iso

RETENTION = timedelta(days=10)
FLOOR_PER_LAB = 3
TOMBSTONE_TTL = timedelta(days=90)


class StoreError(Exception):
    """A data file exists but cannot be trusted. We refuse to overwrite it."""


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as error:
        raise StoreError(f"{path} is not valid JSON ({error}); fix or remove it") from None


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
