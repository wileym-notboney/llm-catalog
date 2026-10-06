# ABOUTME: Tests for the RSS and Atom parsers, including the prerelease filter and the DTD guard.
# ABOUTME: Feed shapes mirror OpenAI RSS, Anthropic release-notes RSS and GitHub release atom.
import pytest

from feed.xml_feeds import parse_atom, parse_rss
from tests.fixtures import atom, rss

RECENT_RFC822 = "Mon, 05 Oct 2026 15:00:00 GMT"
LABELS = {"lab": "openai", "kind": "news", "source": "openai-news"}


def test_parse_rss_maps_fields_and_dates():
    xml = rss(("Our approach", "https://openai.com/index/eu", "Mon, 05 Oct 2026 15:00:00 GMT"))
    (item,) = parse_rss(xml, **LABELS)
    assert item["title"] == "Our approach"
    assert item["url"] == "https://openai.com/index/eu"
    assert item["summary"] == "About Our approach"
    assert item["publishedAt"] == "2026-10-05T15:00:00Z"
    assert item["lab"] == "openai" and item["source"] == "openai-news"


def test_parse_rss_skips_entries_without_a_link_and_tolerates_a_bad_date():
    xml = (
        '<rss version="2.0"><channel>'
        "<item><title>No link</title></item>"
        "<item><title>Bad date</title><link>https://x/1</link><pubDate>soon</pubDate></item>"
        "</channel></rss>"
    )
    (item,) = parse_rss(xml, **LABELS)
    assert item["title"] == "Bad date" and item["publishedAt"] is None


def test_links_that_are_not_http_are_dropped_in_rss_and_atom():
    bad_rss = rss(("Script", "javascript:alert(1)", RECENT_RFC822), ("Fine", "https://x/ok", RECENT_RFC822))
    assert [i["title"] for i in parse_rss(bad_rss, **LABELS)] == ["Fine"]
    bad_atom = atom(("Script", "javascript:alert(1)", "2026-10-05T07:00:00Z"))
    assert parse_atom(bad_atom, lab="nous", kind="release", source="s") == []


def test_parse_rss_unwraps_escaped_html_descriptions():
    xml = (
        '<rss version="2.0"><channel><item><title>Notes</title><link>https://x/n</link>'
        "<description>&lt;ul&gt;&lt;li&gt;We&amp;apos;ve added a &lt;code&gt;line&lt;/code&gt; field&lt;/li&gt;&lt;/ul&gt;"
        "</description></item></channel></rss>"
    )
    (item,) = parse_rss(xml, **LABELS)
    assert item["summary"] == "We've added a line field"


def test_parse_atom_uses_alternate_link_and_updated_date():
    xml = atom(("v2.1.290", "https://github.com/a/b/releases/tag/v2.1.290", "2026-10-05T07:19:01Z"))
    (item,) = parse_atom(xml, lab="anthropic", kind="release", source="claude-code-releases")
    assert item["url"].endswith("v2.1.290")
    assert item["publishedAt"] == "2026-10-05T07:19:01Z"
    assert item["summary"] == "Notes for v2.1.290"


def test_parse_atom_filters_canary_releases():
    xml = atom(
        ("v0.21.4+canary.20261005T071900Z", "https://g/c", "2026-10-05T07:19:01Z"),
        ("v0.21.3", "https://g/s", "2026-10-01T07:19:01Z"),
    )
    items = parse_atom(
        xml, lab="nous", kind="release", source="hermes-agent-releases", skip_title=r"canary|nightly"
    )
    assert [item["title"] for item in items] == ["v0.21.3"]


def test_parsers_reject_documents_that_declare_a_dtd():
    bomb = '<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "aaaa">]><rss><channel/></rss>'
    with pytest.raises(ValueError, match="DTD"):
        parse_rss(bomb, **LABELS)
