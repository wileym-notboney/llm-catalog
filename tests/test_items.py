# ABOUTME: Tests for item construction and the text/date helpers.
# ABOUTME: Pins the 280-char summary cap, markup stripping and stable ids.
from datetime import datetime, timezone

from feed.items import clean_text, item_id, iso, make_item, parse_iso


def test_clean_text_strips_markup_and_unescapes():
    assert clean_text("<ul><li>We&apos;ve added a <code>line</code> field.</li></ul>") == (
        "We've added a line field."
    )


def test_clean_text_separates_block_tags_with_a_space():
    assert clean_text("<p>one</p><p>two</p>") == "one two"


def test_clean_text_truncates_with_an_ellipsis_at_the_limit():
    out = clean_text("word " * 100)
    assert len(out) == 280 and out.endswith("…")


def test_make_item_is_stable_and_undated_when_source_has_no_date():
    a = make_item(lab="nous", kind="news", source="nous-blog", title="T", url="https://x/y")
    b = make_item(lab="nous", kind="news", source="nous-blog", title="T", url="https://x/y")
    assert a["id"] == b["id"] == item_id("https://x/y")
    assert a["publishedAt"] is None and a["firstSeenAt"] is None


def test_iso_round_trips_in_utc():
    moment = datetime(2026, 10, 5, 12, 30, tzinfo=timezone.utc)
    assert iso(moment) == "2026-10-05T12:30:00Z"
    assert parse_iso(iso(moment)) == moment
