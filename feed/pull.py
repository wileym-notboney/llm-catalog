# ABOUTME: Orchestrates one pull: fetch every source, merge into items.json, then prune.
# ABOUTME: A failing source keeps its old items and is marked stale; it never empties the feed.
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from feed.items import iso
from feed.scrape_pages import (
    MAX_XML_BYTES,
    FetchError,
    firecrawl_markdown,
    parse_anthropic_news,
    parse_nous_blog,
    read_capped,
)
from feed.store import (
    merge,
    prune,
    prune_attempts,
    read_json,
    validate_attempts,
    validate_catalog,
    validate_state,
    write_json,
    writer_lock,
)
from feed.xml_feeds import parse_atom, parse_rss

log = logging.getLogger("feed")

# Pipeline tags that would flood the feed. Applied to every Atom release feed: a repo can
# publish canary/nightly builds and rc.N / abandoned-rc.N tags whose bodies are JSON, not
# release notes. A feed of nothing but these legitimately yields no items.
SKIP_PRERELEASE = r"canary|nightly|abandoned|\brc[.-]?\d"

SOURCES = (
    {"id": "anthropic-news", "via": "firecrawl", "url": "https://www.anthropic.com/news",
     "parse": parse_anthropic_news},
    {"id": "anthropic-api-notes", "via": "rss", "lab": "anthropic", "kind": "changelog",
     "url": "https://platform.claude.com/docs/en/release-notes/feed.xml"},
    {"id": "claude-code-releases", "via": "atom", "lab": "anthropic", "kind": "release",
     "url": "https://github.com/anthropics/claude-code/releases.atom"},
    {"id": "openai-news", "via": "rss", "lab": "openai", "kind": "news",
     "url": "https://openai.com/news/rss.xml"},
    {"id": "nous-blog", "via": "firecrawl", "url": "https://nousresearch.com/blog",
     "parse": parse_nous_blog},
)

def _empty_catalog() -> dict:
    """A fresh catalog per call: its nested containers get mutated, so they must never be shared."""
    return {"generatedAt": None, "sources": {}, "items": []}


def _empty_state() -> dict:
    return {"lastPull": None, "lastPrune": None, "tombstones": {}}

FetchText = Callable[[str], str]
FetchMarkdown = Callable[[str], str]


def fetch_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "llm-catalog/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return read_capped(response, MAX_XML_BYTES).decode("utf-8")
    except urllib.error.HTTPError as error:
        raise FetchError(f"HTTP {error.code}") from None


def markdown_fetcher() -> FetchMarkdown | None:
    """A Firecrawl fetcher built from FIRECRAWL_API_KEY, or None when no key is set."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None
    return lambda url: firecrawl_markdown(url, api_key)


def collect(source: dict, fetch_xml: FetchText, fetch_md: FetchMarkdown | None) -> list[dict]:
    """Fetch and parse one source into normalized items."""
    if source["via"] == "firecrawl":
        if fetch_md is None:
            raise FetchError("FIRECRAWL_API_KEY not set")
        return source["parse"](fetch_md(source["url"]), source=source["id"])
    labels = {"lab": source["lab"], "kind": source["kind"], "source": source["id"]}
    xml_text = fetch_xml(source["url"])
    if source["via"] == "rss":
        return parse_rss(xml_text, **labels)
    return parse_atom(xml_text, skip_title=SKIP_PRERELEASE, **labels)


def read_attempts(data_dir: Path) -> dict:
    """Paid-attempt records. An unreadable file raises StoreError: guessing "none" could double-charge."""
    return read_json(data_dir / "attempts.json", {"attempts": {}}, validate_attempts)


def attempted_today(attempts: dict, source_id: str, now: datetime) -> bool:
    record = attempts["attempts"].get(source_id)
    if record is None:
        return False
    day = date.fromisoformat(record["date"])
    if day > now.date():
        log.warning("source %s has an attempt record dated %s, in the future; fix or remove "
                    "it in attempts.json or the source stays deferred", source_id, day)
    return day >= now.date()


def save_pruned_attempts(data_dir: Path, attempts: dict, now: datetime) -> None:
    """Write attempts.json without yesterday's records, but only if something changed."""
    pruned = prune_attempts(attempts, now)
    if pruned != attempts:
        write_json(data_dir / "attempts.json", pruned)


def run_pull(
    data_dir: Path, now: datetime, fetch_xml: FetchText, fetch_md: FetchMarkdown | None
) -> dict:
    """Pull every source once, as the data directory's only writer (raises WriterBusy otherwise).

    Returns {"ok": [ids], "failed": {id: reason}, "deferred": [ids]}. A paid source gets at most
    one request per UTC day: the attempt is saved to attempts.json BEFORE the request and counts
    whether the request succeeds, fails or the process dies. Deferred sources are not failures.
    """
    with writer_lock(data_dir):
        return _pull_locked(data_dir, now, fetch_xml, fetch_md)


def _pull_locked(
    data_dir: Path, now: datetime, fetch_xml: FetchText, fetch_md: FetchMarkdown | None
) -> dict:
    catalog = read_json(data_dir / "items.json", _empty_catalog(), validate_catalog)
    state = read_json(data_dir / "state.json", _empty_state(), validate_state)
    attempts = read_attempts(data_dir)
    incoming, ok, failed, deferred = [], [], {}, []
    for source in SOURCES:
        status = catalog["sources"].setdefault(source["id"], {"lastOk": None, "lastError": None})
        if source["via"] == "firecrawl" and fetch_md is not None:
            if attempted_today(attempts, source["id"], now):
                # lastError is what the UI reads as "stale"; the prefix says why.
                status["lastError"] = "deferred: paid source already requested today (UTC)"
                deferred.append(source["id"])
                log.info("source %s deferred until the next UTC day", source["id"])
                continue
            attempts["attempts"][source["id"]] = {"date": now.date().isoformat(), "at": iso(now)}
            write_json(data_dir / "attempts.json", attempts)
        try:
            found = collect(source, fetch_xml, fetch_md)
            if not found:
                raise FetchError("parsed 0 items")
        except (FetchError, OSError, ET.ParseError, ValueError) as error:
            status["lastError"] = str(error)[:200]
            failed[source["id"]] = status["lastError"]
            log.warning("source %s failed: %s", source["id"], status["lastError"])
            continue
        status.update(lastOk=iso(now), lastError=None)
        incoming.extend(found)
        ok.append(source["id"])
    items = merge(catalog["items"], incoming, state["tombstones"], now)
    try:
        items, state["tombstones"] = prune(items, state["tombstones"], now)
        state["lastPrune"] = iso(now)
    except Exception:  # prune must never cost us the freshly merged items
        log.exception("prune failed; keeping unpruned items")
    state["lastPull"] = iso(now)
    catalog.update(generatedAt=iso(now), items=items)
    write_json(data_dir / "items.json", catalog)
    write_json(data_dir / "state.json", state)
    save_pruned_attempts(data_dir, attempts, now)
    return {"ok": ok, "failed": failed, "deferred": deferred}


def run_prune(data_dir: Path, now: datetime) -> int:
    """Prune stored data without fetching anything, as the only writer (raises WriterBusy otherwise).

    Returns how many items were dropped.
    """
    with writer_lock(data_dir):
        return _prune_locked(data_dir, now)


def _prune_locked(data_dir: Path, now: datetime) -> int:
    catalog = read_json(data_dir / "items.json", _empty_catalog(), validate_catalog)
    state = read_json(data_dir / "state.json", _empty_state(), validate_state)
    attempts = read_attempts(data_dir)
    before = len(catalog["items"])
    catalog["items"], state["tombstones"] = prune(catalog["items"], state["tombstones"], now)
    state["lastPrune"] = iso(now)
    write_json(data_dir / "items.json", catalog)
    write_json(data_dir / "state.json", state)
    save_pruned_attempts(data_dir, attempts, now)
    return before - len(catalog["items"])
