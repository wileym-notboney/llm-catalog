# ABOUTME: Tests for merge, prune, tombstones and the atomic JSON files.
# ABOUTME: Pins the retention rules: 10 days, 3-per-lab floor, 90-day tombstones.
from datetime import datetime, timedelta, timezone

import pytest

from feed.items import iso, make_item
from feed.store import StoreError, merge, prune, read_json, write_json

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def item(url, lab="openai", age_days=0, dated=True):
    built = make_item(
        lab=lab, kind="news", source="s", title=url, url=url,
        published_at=NOW - timedelta(days=age_days) if dated else None,
    )
    return built


def seen(items, now=NOW):
    return merge([], items, {}, now)


def test_merge_stamps_first_seen_and_keeps_it_on_refresh():
    first = seen([item("https://x/1")], NOW - timedelta(days=2))
    again = merge(first, [item("https://x/1")], {}, NOW)
    assert again[0]["firstSeenAt"] == iso(NOW - timedelta(days=2))


def test_merge_skips_tombstoned_ids():
    gone = item("https://x/old")
    assert merge([], [gone], {gone["id"]: iso(NOW)}, NOW) == []


def test_merge_sorts_newest_first_and_uses_first_seen_for_undated_items():
    merged = seen([item("https://x/a", age_days=3), item("https://x/b", dated=False)])
    assert [entry["url"] for entry in merged] == ["https://x/b", "https://x/a"]


def test_prune_drops_items_older_than_ten_days_but_keeps_three_newest_per_lab():
    items = seen([item(f"https://x/{n}", age_days=20 + n) for n in range(5)])
    kept, tombstones = prune(items, {}, NOW)
    assert len(kept) == 3 and len(tombstones) == 2
    assert {entry["url"] for entry in kept} == {"https://x/0", "https://x/1", "https://x/2"}


def test_prune_keeps_everything_inside_the_window():
    items = seen([item(f"https://x/{n}", age_days=n) for n in range(9)])
    kept, tombstones = prune(items, {}, NOW)
    assert len(kept) == 9 and tombstones == {}


def test_prune_floor_is_per_lab_so_a_quiet_lab_never_empties():
    items = seen(
        [item(f"https://o/{n}", "openai", age_days=n) for n in range(4)]
        + [item("https://n/1", "nous", age_days=60)]
    )
    kept, _ = prune(items, {}, NOW)
    assert "https://n/1" in {entry["url"] for entry in kept}


def test_prune_judges_undated_items_by_first_seen():
    stale = seen([item(f"https://x/{n}", dated=False) for n in range(5)], NOW - timedelta(days=30))
    kept, tombstones = prune(stale, {}, NOW)
    assert len(kept) == 3 and len(tombstones) == 2


def test_tombstones_expire_after_ninety_days_and_new_ones_are_stamped():
    old = {"a": iso(NOW - timedelta(days=91)), "b": iso(NOW - timedelta(days=5))}
    _, fresh = prune([], old, NOW)
    assert fresh == {"b": iso(NOW - timedelta(days=5))}


def test_write_json_is_atomic_and_read_json_defaults_when_missing(tmp_path):
    path = tmp_path / "data" / "items.json"
    assert read_json(path, {"items": []}) == {"items": []}
    write_json(path, {"items": [1]})
    assert read_json(path, {}) == {"items": [1]}
    assert not list(path.parent.glob("*.tmp"))


def test_read_json_refuses_a_corrupt_file_instead_of_treating_it_as_empty(tmp_path):
    path = tmp_path / "items.json"
    path.write_text("{truncated")
    with pytest.raises(StoreError, match="not valid JSON"):
        read_json(path, {})
