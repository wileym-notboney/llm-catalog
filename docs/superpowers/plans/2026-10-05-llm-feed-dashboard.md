# LLM Feed Dashboard Implementation Plan

> **Status (2026-10-05): implemented.** The code in every task below was prototyped first and
> then committed on `feature/llm-feed-dashboard` as 8 commits, one per task (Task 0 is a
> Hindsight record, not a commit). All 51 tests pass from a fresh clone. This document is now
> the reference for what each file does and why. Treat the checkboxes as already done, with one
> exception: the paid Firecrawl check in Task 8, Step 2, which was completed on 2026-10-06
> (2 credits, panda master's key; see the hardening plan, H6). The scrapers were verified
> against live pages. 130 tests pass after the hardening increment.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A self-contained dashboard that shows one merged feed of Anthropic, OpenAI and Nous Research news and changelogs, refreshes itself daily at ≤2 Firecrawl credits and 0 Claude tokens, and is styled with the Mythological Punk theme.

**Architecture:** One stdlib-only Python process (`serve.py`) serves the committed React build (`app/dist/index.html`) plus `data/items.json`, and runs a scheduler thread that pulls six sources daily (four via `urllib`, two via the Firecrawl REST API), merges them into `items.json`, then prunes. All retention and parsing rules are pure functions in the `feed/` package, tested without a network.

**Tech Stack:** Python 3.10+ stdlib; pytest (dev only); React + Vite + Tailwind scaffold from the `web-artifacts-builder` skill, bundled to one HTML file with Parcel and html-inline.

**Spec:** `docs/superpowers/specs/2026-10-05-llm-feed-dashboard-design.md` (read it first; it holds the reasoning behind every constraint below).

## Global Constraints

- Python 3.10+; runtime is stdlib only. No new runtime dependency, ever, without asking panda master. Dev-only: `pytest`.
- Node is needed only to rebuild the UI. `app/dist/index.html` is committed so a fresh clone runs with only Python.
- Runtime data is `data/items.json` (items plus per-source status) and `data/state.json` (`lastPull`, `lastPrune`, `tombstones`). `data/` is git-ignored. Source status lives only in `items.json`.
- Retention: prune items older than **10 days** by `publishedAt`, else `firstSeenAt`; always keep the **3 newest per lab**; tombstone pruned ids for **90 days**.
- Daily pull at `PULL_AT` (default `06:00` UTC) plus a catch-up pull on start when the last pull is over 24h old. Prune runs inside the pull as a separate guarded step.
- Scrapes: `POST https://api.firecrawl.dev/v2/scrape`, body `{"url", "formats": ["markdown"], "onlyMainContent": true, "maxAge": 0}`, header `Authorization: Bearer $FIRECRAWL_API_KEY`. 1 credit each (cache hits are still billed). No JSON-extract.
- Secrets: `FIRECRAWL_API_KEY` comes from the environment only. Never write it to a file in the repo, a log line, an error message, or `data/`. Panda master creates any env file; Claude never edits `.env` files (a hook blocks it).
- Server binds `127.0.0.1` by default on port `8787`. Only `app/dist` and `/items.json` are served; `state.json` must 404.
- Theme: Mythological Punk. Dark only, system fonts only, no external requests, no PNG textures (the marble is 2.6 MB).
- Every hand-written source file starts with a 2-line `ABOUTME:` comment. Match the existing style; functions under ~30 lines.
- Git: work on `feature/llm-feed-dashboard`. Commit messages are `type(scope): description` and end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. A pre-commit hook blocks any commit unless `CHANGELOG.md` is staged, so every commit step stages it. Commit steps run only once panda master has approved executing this plan.

## Review Focus

Failure modes the spec implies that most likely bite a real user. Each is pinned by a named test in the owning task.

1. **A site redesign makes a scraper parse zero items.** Expected: that source goes stale and keeps its old items; the feed never empties. Pinned by `test_a_layout_change_that_parses_zero_items_is_stale_and_keeps_old_items` (Task 5).
2. **`items.json` is corrupt or truncated.** Expected: refuse to overwrite it, exit non-zero with a clear message, never silently start from empty. Pinned by `test_read_json_refuses_a_corrupt_file_instead_of_treating_it_as_empty` (Task 4) and `test_a_corrupt_items_file_aborts_without_overwriting_it` (Task 5).
3. **The pull crashes after a paid scrape.** Expected: back off an hour; never re-scrape every minute and burn credits. Pinned by `test_a_crashing_pull_backs_off_an_hour_instead_of_retrying_every_minute` (Task 6).
4. **A source still lists items we pruned (OpenAI's RSS holds ~1,250).** Expected: they stay gone and never reappear flagged "new". Pinned by `test_pruned_items_are_not_reingested_by_the_next_pull` (Task 5).
5. **A feed entry carries a non-web link (`javascript:`).** Expected: it is dropped before it can reach an `href`. Pinned by `test_links_that_are_not_http_are_dropped_in_rss_and_atom` (Task 2).

Also pinned: GitHub pipeline tags (`canary`, `nightly`, `rc.N`, `abandoned-rc.N`) never enter the feed (`test_a_clean_pull_ingests_every_source_and_hides_canaries`); scraped pages that include a date in a category-prefixed form (`AnnouncementsSep 28, 2026`) still parse (`test_anthropic_news_parses_hero_and_list_and_dedupes_by_url`).

## Deviations from the spec (all small; flag to panda master)

- The crest SVG (553 B) is drawn inline in `App.tsx`. The marble PNG texture is dropped (2.6 MB, far over "one small texture"); the scanlines, clipped-corner cards and gunmetal gradient carry the theme.
- Per-source status (`lastOk`, `lastError`) lives in `items.json`, not `state.json`, so the page can read it and there is one source of truth.
- The spec's "20 newest per lab" floor became **3** (a 20-item floor defeats a 10-day window).
- Added a DTD/entity guard for XML (stdlib stand-in for `defusedxml`, which would be a new dependency) and the http(s)-only link rule.
- The first run creates about 1,400 tombstones (`state.json` ≈ 100 KB) because OpenAI's RSS is long. That is expected, not a bug.

## File Structure

| File                                                    | Responsibility                                                |
| ------------------------------------------------------- | ------------------------------------------------------------- |
| `feed/items.py`                                         | Item shape, text cleaning, ISO helpers, `is_web_url`          |
| `feed/xml_feeds.py`                                     | RSS and Atom parsers, DTD guard, prerelease filter            |
| `feed/scrape_pages.py`                                  | Firecrawl REST client; Anthropic and Nous markdown parsers    |
| `feed/store.py`                                         | Atomic JSON files; `merge`, `prune`, tombstones               |
| `feed/pull.py`                                          | Source table; `run_pull`, `run_prune`; fetchers               |
| `feed/schedule.py`                                      | `pull_due`, `step` with backoff                               |
| `feed/__main__.py`                                      | `python3 -m feed pull                                         | prune` |
| `serve.py`                                              | HTTP server and scheduler thread                              |
| `app/`                                                  | React UI source; `app/dist/index.html` is the committed build |
| `tests/`                                                | One test module per feed module, plus shared `fixtures.py`    |
| `README.md`, `CHANGELOG.md`, `.gitignore`, `pytest.ini` | Docs and repo hygiene                                         |

---

### Task 0: Record the initiative

- [ ] **Step 1:** Call `hindsight_capture_initiative` with title `LLM feed dashboard (self-contained, metal-first)` and a 3-sentence summary of the Goal and Architecture above. Do this once, before writing any code.

---

### Task 1: Repo scaffolding and item helpers

**Files:**

- Create: `.gitignore`, `pytest.ini`, `CHANGELOG.md`, `feed/__init__.py`, `feed/items.py`, `tests/__init__.py` (empty), `tests/test_items.py`
- Existing, to be committed with this task: `docs/superpowers/specs/2026-10-05-llm-feed-dashboard-design.md`, `docs/superpowers/plans/2026-10-05-llm-feed-dashboard.md`

**Interfaces:**

- Produces: `clean_text(raw, limit=280) -> str`, `iso(datetime) -> str`, `parse_iso(str) -> datetime`, `is_web_url(str) -> bool`, `item_id(url) -> str`, `make_item(*, lab, kind, source, title, url, summary="", published_at=None) -> dict` (with `firstSeenAt: None`).

- [ ] **Step 1: Branch and create the dev environment**

```bash
cd /Users/skeletor/projects/llm-catalog
git checkout -b feature/llm-feed-dashboard
python3 -m venv .venv && .venv/bin/pip install pytest
```

- [ ] **Step 2: Create `.gitignore`, `pytest.ini`, `CHANGELOG.md`, and the empty `tests/__init__.py`**

`.gitignore`:

```
data/
__pycache__/
.pytest_cache/
.venv/
.DS_Store
```

`pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

`CHANGELOG.md`:

```markdown
# Changelog

## Unreleased

- Project scaffolding, design spec and implementation plan.
```

Then `touch tests/__init__.py`.

- [ ] **Step 3: Write the failing test** — `tests/test_items.py`

```python
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
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_items.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'feed'`.

- [ ] **Step 5: Implement** — `feed/__init__.py` and `feed/items.py`

```python
# ABOUTME: Feed package: pulls AI-lab news and changelogs into one normalized items.json.
# ABOUTME: Run by hand with `python3 -m feed pull|prune`, or on a schedule by serve.py.
```

```python
# ABOUTME: Normalized feed item construction plus the text and date helpers every parser shares.
# ABOUTME: One item shape for all labs; field meanings are defined in the design spec.
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

SUMMARY_MAX = 280
TITLE_MAX = 200

_BLOCK_TAGS = re.compile(r"</?(?:p|li|ul|ol|br|div|h[1-6])\b[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def clean_text(raw: str, limit: int = SUMMARY_MAX) -> str:
    """Strip markup, unescape entities, collapse whitespace, truncate with an ellipsis."""
    text = _BLOCK_TAGS.sub(" ", raw or "")
    text = html.unescape(_TAGS.sub("", text))
    text = _SPACE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_web_url(url: str) -> bool:
    """Only http(s) links are kept; a `javascript:` href from a feed must never reach the page."""
    return url.lower().startswith(("https://", "http://"))


def item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def make_item(
    *,
    lab: str,
    kind: str,
    source: str,
    title: str,
    url: str,
    summary: str = "",
    published_at: datetime | None = None,
) -> dict:
    """Build one item. `firstSeenAt` stays None until the store merges it."""
    return {
        "id": item_id(url),
        "lab": lab,
        "kind": kind,
        "title": clean_text(title, TITLE_MAX),
        "summary": clean_text(summary),
        "url": url,
        "publishedAt": iso(published_at) if published_at else None,
        "source": source,
        "firstSeenAt": None,
    }
```

- [ ] **Step 6: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_items.py -q`
Expected: `5 passed`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore pytest.ini CHANGELOG.md feed tests docs
git commit -m "chore(feed): scaffold project, spec, plan and item helpers" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: RSS and Atom parsers

**Files:**

- Create: `tests/fixtures.py`, `tests/test_xml_feeds.py`, `feed/xml_feeds.py`
- Modify: `CHANGELOG.md`

**Interfaces:**

- Consumes: `make_item`, `is_web_url`, `parse_iso` from `feed/items.py`.
- Produces: `parse_rss(xml_text, *, lab, kind, source) -> list[dict]`; `parse_atom(xml_text, *, lab, kind, source, skip_title=None) -> list[dict]` (both raise `ValueError` for a DTD/entity declaration and `xml.etree.ElementTree.ParseError` for malformed XML); test helpers `rss(*entries)`, `atom(*entries)`, constants `ANTHROPIC_MD`, `NOUS_MD` in `tests/fixtures.py` (the two markdown fixtures are used by Task 3 and Task 5; shapes captured live on 2026-10-05).

- [ ] **Step 1: Write the shared fixtures and the failing tests**

`tests/fixtures.py`:

```python
# ABOUTME: Shared test data: realistic RSS/Atom builders and trimmed copies of the scraped pages.
# ABOUTME: Shapes were captured from the live sources on 2026-10-05.
from __future__ import annotations

BS = "\\\\"  # the two backslashes Firecrawl emits before a hard line break


def rss(*entries: tuple[str, str, str]) -> str:
    """entries are (title, link, pubDate)."""
    body = "".join(
        f"<item><title><![CDATA[{title}]]></title><link>{link}</link>"
        f"<description><![CDATA[About {title}]]></description><pubDate>{date}</pubDate></item>"
        for title, link, date in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{body}</channel></rss>'


def atom(*entries: tuple[str, str, str]) -> str:
    """entries are (title, href, updated)."""
    body = "".join(
        f'<entry><updated>{updated}</updated><link rel="alternate" type="text/html" href="{href}"/>'
        f"<title>{title}</title><content type=\"html\">&lt;p&gt;Notes for {title}&lt;/p&gt;</content></entry>"
        for title, href, updated in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


ANTHROPIC_MD = (
    "# Newsroom\n\n- Press inquiries [press@anthropic.com](mailto:press@anthropic.com)\n\n"
    "![Video thumbnail](https://www.anthropic.com/_next/image?url=x)\n\n"
    f"[**Introducing Claude Sonnet 5.5** {BS}\n{BS}\nAnnouncementsSep 28, 2026{BS}\n{BS}\n"
    "A clear upgrade over Sonnet 5.](https://www.anthropic.com/claude-sonnet-5-5)\n\n"
    f"[AnnouncementsSep 22, 2026{BS}\n**Introducing Claude Opus 5.5** {BS}\n"
    "Opus 5.5 performs at the level of Fable 5.1.](https://www.anthropic.com/claude-opus-5-5)\n\n"
    "## News\n\nDateCategoryTitle\n\n"
    f"- [Oct 2, 2026Announcements{BS}\nAnthropic invests $100 million to train engineers]"
    "(https://www.anthropic.com/news/claude-frontier-academy)\n"
    f"- [Sep 22, 2026Announcements{BS}\nIntroducing Claude Opus 5.5]"
    "(https://www.anthropic.com/claude-opus-5-5)\n\n"
    "[See more](https://www.anthropic.com/news#)"
)

NOUS_MD = """[![](https://x/banner.webp)](https://nousresearch.com/refactoring-hermes-with-1393-agents)

ByTeknium

## [Refactoring Hermes with 1,393 agents](https://nousresearch.com/refactoring-hermes-with-1393-agents)

Hermes Agent autonomously plowed through a million lines of cleanup....

ByNightwing

## [Lighthouse Attention](https://nousresearch.com/lighthouse-attention)

A selection-based hierarchical attention ~17x faster than standard attention....

## Archive

### [Field Notes on Scaling MoE Expert Parallelism](https://nousresearch.com/moe-scaling-field-notes)

Documenting the journey of scaling expert parallelism....

## Hermes AgentHermes Agent

The self-improving AI agent built by Nous Research.
"""
```

`tests/test_xml_feeds.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_xml_feeds.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'feed.xml_feeds'`.

- [ ] **Step 3: Implement** — `feed/xml_feeds.py`

```python
# ABOUTME: Parsers for RSS 2.0 and Atom feeds into normalized items, using only the stdlib.
# ABOUTME: Atom entries can be filtered by title so noisy canary/nightly releases never land.
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from feed.items import is_web_url, make_item, parse_iso

ATOM = "{http://www.w3.org/2005/Atom}"


def _safe_root(xml_text: str) -> ET.Element:
    """Refuse DTDs and entity declarations, the vector for billion-laughs style bombs.

    The sources are fixed HTTPS feeds, so this stdlib guard stands in for defusedxml.
    """
    if re.search(r"<!(?:DOCTYPE|ENTITY)", xml_text, re.I):
        raise ValueError("feed declares a DTD or entity")
    return ET.fromstring(xml_text)


def _rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _iso_or_none(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_iso(value.strip()).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_rss(xml_text: str, *, lab: str, kind: str, source: str) -> list[dict]:
    items = []
    for node in _safe_root(xml_text).iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not is_web_url(link):
            continue
        items.append(
            make_item(
                lab=lab,
                kind=kind,
                source=source,
                title=title,
                url=link,
                summary=node.findtext("description") or "",
                published_at=_rfc822(node.findtext("pubDate")),
            )
        )
    return items


def parse_atom(
    xml_text: str, *, lab: str, kind: str, source: str, skip_title: str | None = None
) -> list[dict]:
    items = []
    for entry in _safe_root(xml_text).iter(f"{ATOM}entry"):
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        href = next(
            (
                link.get("href")
                for link in entry.findall(f"{ATOM}link")
                if link.get("rel", "alternate") == "alternate"
            ),
            None,
        )
        if not title or not href or not is_web_url(href):
            continue
        if skip_title and re.search(skip_title, title, re.I):
            continue
        items.append(
            make_item(
                lab=lab,
                kind=kind,
                source=source,
                title=title,
                url=href,
                summary=entry.findtext(f"{ATOM}content") or "",
                published_at=_iso_or_none(entry.findtext(f"{ATOM}updated")),
            )
        )
    return items
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_xml_feeds.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Commit** (add under `## Unreleased` in `CHANGELOG.md`: `- RSS and Atom parsers with a DTD guard and http(s)-only links.`)

```bash
git add feed tests CHANGELOG.md
git commit -m "feat(feed): parse RSS and Atom feeds into normalized items" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Firecrawl client and the two page parsers

**Files:**

- Create: `tests/test_scrape_pages.py`, `feed/scrape_pages.py`
- Modify: `CHANGELOG.md`

**Interfaces:**

- Consumes: `make_item`; fixtures `ANTHROPIC_MD`, `NOUS_MD` from Task 2.
- Produces: `FetchError(Exception)`; `firecrawl_markdown(url, api_key, timeout=90) -> str`; `parse_anthropic_news(markdown, *, source="anthropic-news") -> list[dict]`; `parse_nous_blog(markdown, *, source="nous-blog") -> list[dict]`. Nous items are undated by design.

- [ ] **Step 1: Write the failing tests** — `tests/test_scrape_pages.py`

```python
# ABOUTME: Tests for the Firecrawl client and the two markdown page parsers.
# ABOUTME: The client tests fake urlopen, so no credit is ever spent by the test suite.
import io
import json
import urllib.error

import pytest

from feed.scrape_pages import FetchError, firecrawl_markdown, parse_anthropic_news, parse_nous_blog
from tests.fixtures import ANTHROPIC_MD, NOUS_MD


def test_anthropic_news_parses_hero_and_list_and_dedupes_by_url():
    items = {item["url"]: item for item in parse_anthropic_news(ANTHROPIC_MD)}
    assert len(items) == 3
    sonnet = items["https://www.anthropic.com/claude-sonnet-5-5"]
    assert sonnet["title"] == "Introducing Claude Sonnet 5.5"
    assert sonnet["summary"] == "A clear upgrade over Sonnet 5."
    assert sonnet["publishedAt"] == "2026-09-28T00:00:00Z"
    opus = items["https://www.anthropic.com/claude-opus-5-5"]
    assert opus["title"] == "Introducing Claude Opus 5.5"
    assert opus["summary"].startswith("Opus 5.5 performs")
    academy = items["https://www.anthropic.com/news/claude-frontier-academy"]
    assert academy["title"].startswith("Anthropic invests $100 million")
    assert academy["publishedAt"] == "2026-10-02T00:00:00Z"
    assert all(item["lab"] == "anthropic" and item["kind"] == "news" for item in items.values())


def test_anthropic_news_ignores_links_without_a_date():
    assert parse_anthropic_news("[See more](https://www.anthropic.com/news#)") == []


def test_nous_blog_takes_featured_posts_only_and_leaves_them_undated():
    items = parse_nous_blog(NOUS_MD)
    assert [item["title"] for item in items] == [
        "Refactoring Hermes with 1,393 agents",
        "Lighthouse Attention",
    ]
    assert items[0]["summary"].startswith("Hermes Agent autonomously")
    assert all(item["publishedAt"] is None and item["lab"] == "nous" for item in items)


def test_parsers_return_nothing_for_an_unrecognised_layout():
    assert parse_anthropic_news("<html>redesigned</html>") == []
    assert parse_nous_blog("<html>redesigned</html>") == []


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_firecrawl_markdown_posts_the_documented_request(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data)
        return _Response(json.dumps({"success": True, "data": {"markdown": "# hi"}}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert firecrawl_markdown("https://example.com", "fc-key") == "# hi"
    assert seen["url"] == "https://api.firecrawl.dev/v2/scrape"
    assert seen["auth"] == "Bearer fc-key"
    assert seen["body"] == {
        "url": "https://example.com",
        "formats": ["markdown"],
        "onlyMainContent": True,
        "maxAge": 0,
    }


def test_firecrawl_errors_never_leak_the_api_key(monkeypatch):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 402, "Payment Required", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(FetchError) as caught:
        firecrawl_markdown("https://example.com", "fc-secret")
    assert str(caught.value) == "Firecrawl HTTP 402"
    assert "fc-secret" not in repr(caught.value)


def test_firecrawl_rejects_an_empty_result(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _Response(json.dumps({"success": True, "data": {}}).encode()),
    )
    with pytest.raises(FetchError, match="no markdown"):
        firecrawl_markdown("https://example.com", "k")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scrape_pages.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'feed.scrape_pages'`.

- [ ] **Step 3: Implement** — `feed/scrape_pages.py`

Note the comment above `_DATE`: the category runs straight into the month (`AnnouncementsSep 28, 2026`), so a `\b` there silently drops Anthropic's featured launch posts. Do not "tidy" it in.

```python
# ABOUTME: Firecrawl REST client plus markdown parsers for the two sources with no RSS feed.
# ABOUTME: Anthropic's newsroom carries dates; Nous's blog does not, so its items stay undated.
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from feed.items import make_item

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


class FetchError(Exception):
    """A source could not be fetched or parsed. The message is safe to store and show."""


def firecrawl_markdown(url: str, api_key: str, timeout: int = 90) -> str:
    """Scrape one page to markdown. maxAge=0 forces a live fetch instead of the 2-day cache."""
    body = json.dumps(
        {"url": url, "formats": ["markdown"], "onlyMainContent": True, "maxAge": 0}
    ).encode("utf-8")
    request = urllib.request.Request(
        FIRECRAWL_SCRAPE_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise FetchError(f"Firecrawl HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise FetchError(f"Firecrawl request failed: {type(error).__name__}") from None
    markdown = (payload.get("data") or {}).get("markdown")
    if not payload.get("success") or not markdown:
        raise FetchError("Firecrawl returned no markdown")
    return markdown


_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
# No leading \b: the category runs straight into the month ("AnnouncementsSep 28, 2026").
_DATE = re.compile(rf"({_MONTHS}) (\d{{1,2}}), (\d{{4}})")
_DATE_PART = re.compile(rf"^[A-Za-z &]*({_MONTHS}) \d{{1,2}}, \d{{4}}[A-Za-z &]*$")
_LINK = re.compile(r"\[([^\[\]]+)\]\((https://[^)\s]+)\)")
_BREAK = re.compile(r"\\{1,2}[ \t]*\n|\n")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def parse_anthropic_news(markdown: str, *, source: str = "anthropic-news") -> list[dict]:
    """Every link whose text carries a date is an article; the newsroom lists some twice."""
    items, seen = [], set()
    for text, url in _LINK.findall(markdown):
        date = _DATE.search(text)
        if not date or url in seen:
            continue
        seen.add(url)
        parts = [part.strip() for part in _BREAK.split(text) if part.strip()]
        content = [part for part in parts if not _DATE_PART.match(part)]
        bold = _BOLD.search(text)
        title = bold.group(1).strip() if bold else (content[0] if content else "")
        summary = " ".join(part for part in content if "**" not in part and part != title)
        published = datetime.strptime(" ".join(date.groups()), "%b %d %Y").replace(
            tzinfo=timezone.utc
        )
        items.append(
            make_item(
                lab="anthropic",
                kind="news",
                source=source,
                title=title,
                url=url,
                summary=summary,
                published_at=published,
            )
        )
    return items


_NOUS_POST = re.compile(
    r"^## \[(?P<title>[^\]]+)\]\((?P<url>https://nousresearch\.com/[^)\s]+)\)\s*\n+(?P<summary>[^\n]+)",
    re.M,
)


def parse_nous_blog(markdown: str, *, source: str = "nous-blog") -> list[dict]:
    """Featured posts are `## [Title](url)` headings. The `###` archive is old and is skipped."""
    return [
        make_item(
            lab="nous",
            kind="news",
            source=source,
            title=match["title"],
            url=match["url"],
            summary=match["summary"],
        )
        for match in _NOUS_POST.finditer(markdown)
    ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_scrape_pages.py -q`
Expected: `7 passed`. No credit is spent: the tests fake `urlopen`.

- [ ] **Step 5: Commit** (CHANGELOG line: `- Firecrawl scrape client and parsers for Anthropic news and the Nous blog.`)

```bash
git add feed tests CHANGELOG.md
git commit -m "feat(feed): scrape Anthropic news and Nous blog via Firecrawl" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Store, merge, prune and tombstones

**Files:**

- Create: `tests/test_store.py`, `feed/store.py`
- Modify: `CHANGELOG.md`

**Interfaces:**

- Consumes: `iso`, `parse_iso` from `feed/items.py`.
- Produces: `StoreError`; `read_json(path, default) -> dict`; `write_json(path, data)` (atomic); `item_time(item) -> datetime`; `merge(items, incoming, tombstones, now) -> list[dict]` (newest first; sets `firstSeenAt`); `prune(items, tombstones, now) -> (kept, tombstones)`; constants `RETENTION`, `FLOOR_PER_LAB`, `TOMBSTONE_TTL`.

- [ ] **Step 1: Write the failing tests** — `tests/test_store.py`

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'feed.store'`.

- [ ] **Step 3: Implement** — `feed/store.py`

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_store.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Commit** (CHANGELOG line: `- Item store with 10-day retention, per-lab floor and tombstones.`)

```bash
git add feed tests CHANGELOG.md
git commit -m "feat(feed): add merge, prune and tombstone retention rules" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Pull orchestration and CLI

**Files:**

- Create: `tests/test_pull.py`, `feed/pull.py`, `feed/__main__.py`
- Modify: `CHANGELOG.md`

**Interfaces:**

- Consumes: Tasks 1-4. Fetch seams: `fetch_xml: Callable[[str], str]`, `fetch_md: Callable[[str], str] | None` (None means no API key).
- Produces: `SOURCES` (6 dicts with `id`, `via`, `url`); `fetch_text(url, timeout=30) -> str`; `markdown_fetcher() -> Callable | None`; `collect(source, fetch_xml, fetch_md) -> list[dict]`; `run_pull(data_dir, now, fetch_xml, fetch_md) -> {"ok": [ids], "failed": {id: reason}}`; `run_prune(data_dir, now) -> int`; CLI `python3 -m feed [--data DIR] pull|prune` (exit 1 only if every source failed, 2 on a corrupt store).

- [ ] **Step 1: Write the failing tests** — `tests/test_pull.py`

```python
# ABOUTME: Tests for one full pull across all six sources, using injected fakes (no network).
# ABOUTME: Covers stale handling, empty-parse protection, tombstones and prune-failure safety.
from datetime import datetime, timezone

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
        "claude-code-releases": atom(("v2.1.290", "https://github.com/c/v2.1.290", FRESH)),
        "openai-news": rss(("OpenAI post", "https://openai.com/index/p", RECENT)),
        "hermes-agent-releases": atom(
            ("v0.21.4+canary.1", "https://github.com/h/canary", FRESH),
            ("rc.35-v0.21.5", "https://github.com/h/rc35", FRESH),
            ("abandoned-rc.34-v0.21.5", "https://github.com/h/abandoned", FRESH),
            ("v0.21.3", "https://github.com/h/v0.21.3", FRESH),
        ),
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
    assert summary["failed"] == {} and len(summary["ok"]) == 6
    found = urls(tmp_path)
    assert "https://github.com/h/v0.21.3" in found
    assert not found & {"https://github.com/h/canary", "https://github.com/h/rc35",
                        "https://github.com/h/abandoned"}
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
    assert "openai-news" in summary["failed"] and len(summary["ok"]) == 5


def test_a_layout_change_that_parses_zero_items_is_stale_and_keeps_old_items(tmp_path):
    run(tmp_path)
    summary = run(tmp_path, fetch_md=pages(**{"nous-blog": "<html>redesigned</html>"}))
    assert summary["failed"] == {"nous-blog": "parsed 0 items"}
    assert "https://nousresearch.com/lighthouse-attention" in urls(tmp_path)


def test_without_a_firecrawl_key_only_the_two_scraped_sources_go_stale(tmp_path):
    summary = run(tmp_path, fetch_md=None)
    assert set(summary["failed"]) == {"anthropic-news", "nous-blog"}
    assert summary["failed"]["nous-blog"] == "FIRECRAWL_API_KEY not set"
    assert len(summary["ok"]) == 4


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pull.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'feed.pull'`.

- [ ] **Step 3: Implement** — `feed/pull.py` and `feed/__main__.py`

Why a source that parses zero items is a failure, not "everything was removed": a redesign would otherwise look like an empty source. The prune step is wrapped so that a prune bug can never cost the freshly merged items.

```python
# ABOUTME: Orchestrates one pull: fetch every source, merge into items.json, then prune.
# ABOUTME: A failing source keeps its old items and is marked stale; it never empties the feed.
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Callable

from feed.items import iso
from feed.scrape_pages import FetchError, firecrawl_markdown, parse_anthropic_news, parse_nous_blog
from feed.store import merge, prune, read_json, write_json
from feed.xml_feeds import parse_atom, parse_rss

log = logging.getLogger("feed")

# Pipeline tags that would flood the feed: hermes-agent publishes a canary daily plus
# rc.N / abandoned-rc.N tags whose bodies are JSON, not release notes.
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
    {"id": "hermes-agent-releases", "via": "atom", "lab": "nous", "kind": "release",
     "url": "https://github.com/NousResearch/hermes-agent/releases.atom"},
)

EMPTY_CATALOG = {"generatedAt": None, "sources": {}, "items": []}
EMPTY_STATE = {"lastPull": None, "lastPrune": None, "tombstones": {}}

FetchText = Callable[[str], str]
FetchMarkdown = Callable[[str], str]


def fetch_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "llm-catalog/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
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


def run_pull(
    data_dir: Path, now: datetime, fetch_xml: FetchText, fetch_md: FetchMarkdown | None
) -> dict:
    """Pull every source once. Returns {"ok": [source ids], "failed": {source id: reason}}."""
    catalog = read_json(data_dir / "items.json", dict(EMPTY_CATALOG))
    state = read_json(data_dir / "state.json", dict(EMPTY_STATE))
    incoming, ok, failed = [], [], {}
    for source in SOURCES:
        status = catalog["sources"].setdefault(source["id"], {"lastOk": None, "lastError": None})
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
    return {"ok": ok, "failed": failed}


def run_prune(data_dir: Path, now: datetime) -> int:
    """Prune stored data without fetching anything. Returns how many items were dropped."""
    catalog = read_json(data_dir / "items.json", dict(EMPTY_CATALOG))
    state = read_json(data_dir / "state.json", dict(EMPTY_STATE))
    before = len(catalog["items"])
    catalog["items"], state["tombstones"] = prune(catalog["items"], state["tombstones"], now)
    state["lastPrune"] = iso(now)
    write_json(data_dir / "items.json", catalog)
    write_json(data_dir / "state.json", state)
    return before - len(catalog["items"])
```

```python
# ABOUTME: Command line for the feed package: `python3 -m feed pull` and `python3 -m feed prune`.
# ABOUTME: `pull` costs up to 2 Firecrawl credits; it exits 1 only if every source failed.
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from feed.pull import fetch_text, markdown_fetcher, run_prune, run_pull
from feed.store import StoreError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m feed",
        description="Pull AI-lab news and changelogs into data/items.json.",
        epilog="Set FIRECRAWL_API_KEY to also scrape Anthropic news and the Nous blog "
        "(1 credit each). Without it those two sources are marked stale.",
    )
    parser.add_argument("--data", default=os.environ.get("DATA_DIR", "data"),
                        help="data directory (default: $DATA_DIR or ./data)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pull", help="fetch all sources, merge, then prune")
    commands.add_parser("prune", help="prune stored items only; no network")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    data_dir, now = Path(args.data), datetime.now(timezone.utc)
    try:
        if args.command == "prune":
            print(f"pruned {run_prune(data_dir, now)} items")
            return 0
        summary = run_pull(data_dir, now, fetch_text, markdown_fetcher())
    except StoreError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"ok: {', '.join(summary['ok']) or 'none'}")
    for source_id, reason in summary["failed"].items():
        print(f"failed: {source_id}: {reason}", file=sys.stderr)
    return 1 if summary["failed"] and not summary["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `39 passed` (all modules so far).

- [ ] **Step 5: Live check on the free feeds (0 credits)**

```bash
env -u FIRECRAWL_API_KEY .venv/bin/python -m feed --data /tmp/llm-feed-check pull; echo "exit=$?"
```

Expected: prints `ok:` with the four free sources, a `failed:` line for `anthropic-news` and `nous-blog` ("FIRECRAWL_API_KEY not set"), and `exit=0`. `/tmp/llm-feed-check/items.json` holds ~30 items, none titled `canary`, `rc.N` or `abandoned`. Then `rm -rf /tmp/llm-feed-check`.

- [ ] **Step 6: Commit** (CHANGELOG line: `- \`python3 -m feed pull|prune\`: one pull across six sources, stale handling, guarded prune.`)

```bash
git add feed tests CHANGELOG.md
git commit -m "feat(feed): orchestrate a six-source pull with stale handling" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Scheduler and server

**Files:**

- Create: `tests/test_schedule.py`, `tests/test_serve.py`, `feed/schedule.py`, `serve.py`
- Modify: `CHANGELOG.md`

**Interfaces:**

- Consumes: `run_pull`, `fetch_text`, `markdown_fetcher` (Task 5); `read_json`, `parse_iso`.
- Produces: `parse_pull_at("HH:MM") -> datetime.time`; `pull_due(last_pull, now, pull_at) -> bool`; `step(data_dir, now, pull_at, pull) -> int` (seconds to wait: 60 normally, 3600 after a crash); `make_server(dist_dir, data_dir, host, port) -> ThreadingHTTPServer`; `serve.py` CLI (`--host`, `--port`; env `PULL_AT`, `DATA_DIR`, `FIRECRAWL_API_KEY`).

- [ ] **Step 1: Write the failing tests**

`tests/test_schedule.py`:

```python
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
```

`tests/test_serve.py`:

```python
# ABOUTME: Tests that serve.py exposes the built page and items.json, and nothing else.
# ABOUTME: Starts a real server on an ephemeral localhost port.
import threading
import urllib.error
import urllib.request

import pytest

from serve import make_server


@pytest.fixture
def base_url(tmp_path):
    dist, data = tmp_path / "dist", tmp_path / "data"
    dist.mkdir()
    data.mkdir()
    (dist / "index.html").write_text("<html>dashboard</html>")
    (data / "items.json").write_text('{"items": []}')
    (data / "state.json").write_text('{"tombstones": {}}')
    server = make_server(dist, data, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, response.headers, response.read().decode()


def test_serves_the_built_page(base_url):
    status, _, body = get(base_url + "/")
    assert status == 200 and "dashboard" in body


def test_serves_items_json_from_the_data_directory_without_caching(base_url):
    status, headers, body = get(base_url + "/items.json")
    assert status == 200 and body == '{"items": []}'
    assert headers["Cache-Control"] == "no-cache"


def test_does_not_expose_state_json_or_traversal(base_url):
    for path in ("/state.json", "/../data/state.json", "/data/state.json"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            get(base_url + path)
        assert caught.value.code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_schedule.py tests/test_serve.py -q`
Expected: FAIL with `ModuleNotFoundError` for `feed.schedule` and `serve`.

- [ ] **Step 3: Implement** — `feed/schedule.py` and `serve.py`

`step` backs off an hour on any exception because a crash after a paid scrape (disk full, say) would otherwise re-scrape every 60 seconds. `/items.json` is mapped explicitly and everything else is resolved inside `app/dist`, so `state.json` and path traversal both 404.

```python
# ABOUTME: Decides when the daily pull is due and runs one scheduler step with failure backoff.
# ABOUTME: Pure time logic, so the catch-up and retry rules are testable without sleeping.
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

from feed.items import parse_iso
from feed.store import read_json

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
        state = read_json(data_dir / "state.json", {})
        last = parse_iso(state["lastPull"]) if state.get("lastPull") else None
        if pull_due(last, now, pull_at):
            summary = pull(data_dir, now)
            log.info("pull finished: ok=%s failed=%s", summary["ok"], list(summary["failed"]))
        return TICK_SECONDS
    except Exception:
        log.exception("scheduled pull crashed; backing off %ss", BACKOFF_SECONDS)
        return BACKOFF_SECONDS
```

```python
#!/usr/bin/env python3
# ABOUTME: Serves the dashboard (app/dist) and data/items.json, and runs the daily pull scheduler.
# ABOUTME: One stdlib-only process: `FIRECRAWL_API_KEY=... python3 serve.py [--port N]`.
from __future__ import annotations

import argparse
import functools
import logging
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from feed.pull import fetch_text, markdown_fetcher, run_pull
from feed.schedule import parse_pull_at, step

ROOT = Path(__file__).resolve().parent


class DashboardHandler(SimpleHTTPRequestHandler):
    """Static files from app/dist, plus /items.json from the data directory (nothing else)."""

    data_dir: Path

    def translate_path(self, path: str) -> str:
        if urlsplit(path).path == "/items.json":
            return str(self.data_dir / "items.json")
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def make_server(dist_dir: Path, data_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (DashboardHandler,), {"data_dir": data_dir})
    return ThreadingHTTPServer((host, port), functools.partial(handler, directory=str(dist_dir)))


def scheduler_loop(data_dir: Path, pull_at, stop: threading.Event) -> None:
    def pull(directory: Path, now: datetime) -> dict:
        return run_pull(directory, now, fetch_text, markdown_fetcher())

    while not stop.is_set():
        stop.wait(step(data_dir, datetime.now(timezone.utc), pull_at, pull))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve the LLM feed dashboard and refresh it daily.",
        epilog="Environment: FIRECRAWL_API_KEY (optional; enables the 2 scraped sources), "
        "PULL_AT=HH:MM UTC (default 06:00), DATA_DIR (default ./data).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="port (default 8787)")
    args = parser.parse_args()
    try:
        pull_at = parse_pull_at(os.environ.get("PULL_AT", "06:00"))
    except ValueError:
        parser.error("PULL_AT must look like HH:MM, for example 06:00")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    stop = threading.Event()
    threading.Thread(target=scheduler_loop, args=(data_dir, pull_at, stop), daemon=True).start()
    server = make_server(ROOT / "app" / "dist", data_dir, args.host, args.port)
    logging.info("serving on http://%s:%s (pull daily at %s UTC)", args.host, args.port, pull_at)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `51 passed`.

- [ ] **Step 5: Commit** (CHANGELOG line: `- serve.py: static server plus daily scheduler with catch-up and crash backoff.`)

```bash
git add feed serve.py tests CHANGELOG.md
git commit -m "feat(serve): serve the dashboard and run the daily pull scheduler" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The dashboard UI and the committed build

**Files:**

- Create: `app/` (scaffold), `app/src/lib/feed.ts`, `app/src/theme.css`, `app/dist/index.html` (generated)
- Modify: `app/src/App.tsx`, `app/index.html`, `app/tsconfig.app.json`, `app/package.json`, `app/.gitignore`, `CHANGELOG.md`

**Interfaces:**

- Consumes: `GET ./items.json` shaped `{generatedAt, sources: {id: {lastOk, lastError}}, items: [...]}`.
- Produces: `pnpm run bundle` in `app/` rewrites the single-file `app/dist/index.html`.

The UI has no unit tests: the repo has no JS test runner, and adding one is a new dependency to ask about. Its rules live in `lib/feed.ts` as pure functions; Step 8 is a checklist instead.

- [ ] **Step 1: Scaffold with the skill** (run from the repo root; needs Node 18+ and pnpm)

```bash
SKILL=/Users/skeletor/.claude/skills/synced/c800c3e6-8b6c-42e9-bb23-3063cbab19f7_c7b71f63-4ca8-4abf-8944-f30c3e563e6c/web-artifacts-builder
bash "$SKILL/scripts/init-artifact.sh" app
```

Expected: ends with "To start developing". The script leaves a stray file named `index.html''`; delete it.

- [ ] **Step 2: Remove what the dashboard does not use**

```bash
cd app
rm -rf "index.html''" README.md components.json src/App.css src/components src/hooks src/assets src/lib/utils.ts public/vite.svg
grep -rn "components/\|hooks/\|lib/utils\|assets/" src || echo "no dangling imports"
```

(`src/App.tsx` and `src/main.tsx` are rewritten or unaffected in the next steps.)

- [ ] **Step 3: Fix the page title, drop the missing favicon link, silence the scaffold's TypeScript deprecation**

In `app/index.html`: change `<title>app</title>` to `<title>LLM Feed</title>` and delete the `<link rel="icon" ... href="/favicon.svg" />` line.

In `app/tsconfig.app.json`, directly after `"baseUrl": ".",` add `"ignoreDeprecations": "6.0",`.

- [ ] **Step 4: Write the UI** — `app/src/lib/feed.ts`, `app/src/theme.css`, `app/src/App.tsx`

`app/src/lib/feed.ts`:

```ts
// ABOUTME: Feed types plus the pure helpers (filtering, "new" badge, dates) the dashboard uses.
// ABOUTME: Kept free of React so the display rules stay readable on their own.

export type Lab = "anthropic" | "openai" | "nous";
export type Kind = "news" | "changelog" | "release";

export interface Item {
  id: string;
  lab: Lab;
  kind: Kind;
  title: string;
  summary: string;
  url: string;
  publishedAt: string | null;
  source: string;
  firstSeenAt: string;
}

export interface SourceStatus {
  lastOk: string | null;
  lastError: string | null;
}

export interface Catalog {
  generatedAt: string | null;
  sources: Record<string, SourceStatus>;
  items: Item[];
}

export const LABS: Lab[] = ["anthropic", "openai", "nous"];
export const KINDS: Kind[] = ["news", "changelog", "release"];
export const LAB_NAMES: Record<Lab, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  nous: "Nous",
};

const VISIT_KEY = "llm-feed:lastVisit";

/** Sources never date some posts, so those fall back to when we first saw them. */
export function itemDate(item: Item): string {
  return item.publishedAt ?? item.firstSeenAt;
}

export function filterItems(
  items: Item[],
  lab: Lab | "all",
  kind: Kind | "all",
): Item[] {
  return items.filter(
    (item) =>
      (lab === "all" || item.lab === lab) &&
      (kind === "all" || item.kind === kind),
  );
}

export function staleSources(catalog: Catalog): string[] {
  return Object.entries(catalog.sources)
    .filter(([, status]) => status.lastError)
    .map(([id]) => id);
}

/** ISO-8601 UTC strings compare correctly as text. A first visit marks nothing as new. */
export function isNew(item: Item, lastVisit: string | null): boolean {
  return lastVisit !== null && item.firstSeenAt > lastVisit;
}

export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const minutes = Math.max(
    0,
    Math.round((now - new Date(iso).getTime()) / 60000),
  );
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`;
}

export function readLastVisit(): string | null {
  try {
    return localStorage.getItem(VISIT_KEY);
  } catch {
    return null;
  }
}

export function markVisit(): void {
  try {
    localStorage.setItem(
      VISIT_KEY,
      new Date().toISOString().replace(/\.\d+Z$/, "Z"),
    );
  } catch {
    // Private mode or blocked storage: the "new" badge just stays off.
  }
}
```

`app/src/theme.css`:

```css
/* ABOUTME: Mythological Punk theme for the feed dashboard: gunmetal, cobalt and brass.
   ABOUTME: Tokens mirror mythological-punk.yaml; system fonts only, dark only, no external assets. */
:root {
  --bg: #080d16;
  --text: #d9e8f7;
  --muted: #8ea3b8;
  --primary: #4aa8ff;
  --accent: #d3a849;
  --success: #61c6a5;
  --destructive: #db6572;
  --line: rgba(74, 168, 255, 0.28);
  --radius: 0.35rem;
  color-scheme: dark;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font:
    15px/1.5 ui-sans-serif,
    system-ui,
    sans-serif;
  letter-spacing: 0.012em;
}

/* faint scanlines, as in the cockpit layout */
body::after {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 100;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 3px,
    rgba(91, 177, 255, 0.025) 4px
  );
}

.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 16px 64px;
}

.masthead {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.masthead h1 {
  margin: 0;
  font-size: 1.5rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.masthead p {
  margin: 2px 0 0;
}
.crest {
  width: 48px;
  height: 48px;
  flex: none;
}

.muted {
  color: var(--muted);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin: 16px 0;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  padding: 4px 12px;
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font: inherit;
  font-size: 0.85rem;
  text-transform: capitalize;
  cursor: pointer;
  clip-path: polygon(7px 0, 100% 0, calc(100% - 7px) 100%, 0 100%);
}
.chip[aria-pressed="true"] {
  background: rgba(35, 102, 166, 0.28);
  color: var(--text);
  border-color: var(--primary);
}
.chip:focus-visible,
.card a:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.banner {
  margin: 12px 0;
  padding: 8px 12px;
  border-left: 3px solid var(--accent);
  background: rgba(211, 168, 73, 0.1);
}
.banner.error {
  border-left-color: var(--destructive);
  background: rgba(219, 101, 114, 0.1);
}

.feed {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}
.card {
  padding: 14px 18px;
  background: linear-gradient(
    145deg,
    rgba(13, 22, 36, 0.93),
    rgba(5, 9, 16, 0.96)
  );
  box-shadow:
    inset 0 0 0 1px rgba(74, 168, 255, 0.2),
    0 12px 30px rgba(0, 0, 0, 0.22);
  clip-path: polygon(
    10px 0,
    100% 0,
    100% calc(100% - 10px),
    calc(100% - 10px) 100%,
    0 100%,
    0 10px
  );
  border-left: 3px solid var(--lab, var(--primary));
}
.lab-anthropic {
  --lab: var(--accent);
}
.lab-openai {
  --lab: var(--success);
}
.lab-nous {
  --lab: var(--primary);
}

.meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  font-size: 0.8rem;
}
.tag {
  color: var(--lab);
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.new {
  padding: 0 8px;
  background: var(--accent);
  color: #111923;
  font-weight: 700;
  text-transform: uppercase;
  font-size: 0.7rem;
  border-radius: var(--radius);
}
.card h2 {
  margin: 6px 0 4px;
  font-size: 1.05rem;
  line-height: 1.35;
}
.card a {
  color: var(--text);
  text-decoration: none;
}
.card a:hover {
  color: var(--primary);
  text-decoration: underline;
}
.summary {
  margin: 0;
  color: var(--muted);
  font-size: 0.9rem;
}
code {
  font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
}

@media (max-width: 480px) {
  .masthead h1 {
    font-size: 1.2rem;
  }
}
```

`app/src/App.tsx` (replaces the scaffold's file):

```tsx
// ABOUTME: The LLM feed dashboard page: fetches items.json and shows one merged, filterable feed.
// ABOUTME: Styled by theme.css (Mythological Punk); all display rules live in lib/feed.ts.
import { useEffect, useMemo, useState } from "react";
import "./theme.css";
import {
  KINDS,
  LABS,
  LAB_NAMES,
  filterItems,
  formatDay,
  isNew,
  itemDate,
  markVisit,
  readLastVisit,
  staleSources,
  timeAgo,
  type Catalog,
  type Kind,
  type Lab,
} from "./lib/feed";

function Crest() {
  return (
    <svg className="crest" viewBox="0 0 64 64" role="img" aria-label="Crest">
      <defs>
        <linearGradient id="brass" x1="0" x2="1" y1="0" y2="1">
          <stop stopColor="#d0a85e" />
          <stop offset="1" stopColor="#8c622e" />
        </linearGradient>
      </defs>
      <circle
        cx="32"
        cy="32"
        r="28"
        fill="#12161a"
        stroke="url(#brass)"
        strokeWidth="3"
      />
      <path
        d="M16 42h32M20 39h24M23 39V27h18v12M20 27h24l-12-9z"
        fill="none"
        stroke="#e7e2d8"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <path d="m33 12-5 13h5l-3 11 9-15h-5l4-9z" fill="#38a7ff" />
    </svg>
  );
}

function Chips<T extends string>(props: {
  label: string;
  options: readonly T[];
  value: T | "all";
  names?: Record<string, string>;
  onChange: (value: T | "all") => void;
}) {
  return (
    <div className="chips" role="group" aria-label={props.label}>
      {(["all", ...props.options] as const).map((option) => (
        <button
          key={option}
          type="button"
          className="chip"
          aria-pressed={props.value === option}
          onClick={() => props.onChange(option)}
        >
          {option === "all" ? "All" : (props.names?.[option] ?? option)}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lab, setLab] = useState<Lab | "all">("all");
  const [kind, setKind] = useState<Kind | "all">("all");
  // Read once, before markVisit() overwrites it, so "new" means new since the previous visit.
  const [lastVisit] = useState(readLastVisit);

  useEffect(() => {
    fetch("./items.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok)
          throw new Error(`items.json returned ${response.status}`);
        return response.json() as Promise<Catalog>;
      })
      .then(setCatalog)
      .catch((reason: Error) => setError(reason.message));
    markVisit();
  }, []);

  const shown = useMemo(
    () => (catalog ? filterItems(catalog.items, lab, kind) : []),
    [catalog, lab, kind],
  );
  const stale = catalog ? staleSources(catalog) : [];

  return (
    <main className="page">
      <header className="masthead">
        <Crest />
        <div>
          <h1>LLM Feed</h1>
          <p className="muted">
            Anthropic · OpenAI · Nous Research
            {catalog?.generatedAt &&
              ` · updated ${timeAgo(catalog.generatedAt)}`}
          </p>
        </div>
      </header>

      {stale.length > 0 && (
        <p className="banner" role="status">
          Stale: {stale.join(", ")}. Showing the last good items for these.
        </p>
      )}

      <div className="filters">
        <Chips
          label="Lab"
          options={LABS}
          value={lab}
          names={LAB_NAMES}
          onChange={setLab}
        />
        <Chips label="Kind" options={KINDS} value={kind} onChange={setKind} />
      </div>

      {error && (
        <p className="banner error" role="alert">
          Could not load the feed ({error}). Run{" "}
          <code>python3 -m feed pull</code> once.
        </p>
      )}
      {!catalog && !error && <p className="muted">Loading…</p>}
      {catalog && shown.length === 0 && (
        <p className="muted">Nothing matches these filters.</p>
      )}

      <ol className="feed">
        {shown.map((item) => (
          <li key={item.id} className={`card lab-${item.lab}`}>
            <div className="meta">
              <span className="tag">{LAB_NAMES[item.lab]}</span>
              <span className="muted">{item.kind}</span>
              <span className="muted">
                {formatDay(itemDate(item))}
                {item.publishedAt === null && " (first seen)"}
              </span>
              {isNew(item, lastVisit) && <span className="new">new</span>}
            </div>
            <h2>
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.title}
              </a>
            </h2>
            {item.summary && <p className="summary">{item.summary}</p>}
          </li>
        ))}
      </ol>
    </main>
  );
}
```

- [ ] **Step 5: Typecheck**

Run (in `app/`): `pnpm exec tsc -b`
Expected: no output, exit 0.

- [ ] **Step 6: Add the portable bundle script**

Run the skill's bundler once; it installs the Parcel toolchain into `app/package.json` and writes `.parcelrc`:

```bash
bash "$SKILL/scripts/bundle-artifact.sh"
```

Then add this script to `app/package.json` under `"scripts"` (keeps the rebuild independent of the skill):

```json
"bundle": "rm -rf .bundle && parcel build index.html --dist-dir .bundle --no-source-maps && mkdir -p dist && html-inline .bundle/index.html > dist/index.html && rm -rf .bundle"
```

In `app/.gitignore`: delete the line `dist` (we commit it) and append `.bundle`, `.parcel-cache` and `bundle.html`.

- [ ] **Step 7: Build and verify the single file**

```bash
pnpm run bundle && rm -f bundle.html && ls -l dist/index.html
```

Expected: one file, roughly 230 KB. `grep -c "items.json" dist/index.html` prints `1`.

- [ ] **Step 8: Acceptance check from the repo root** (0 credits)

```bash
cd ..
env -u FIRECRAWL_API_KEY DATA_DIR=/tmp/llm-feed-check .venv/bin/python serve.py --port 8799 &
sleep 8
curl -s -o /dev/null -w "index %{http_code}\n" localhost:8799/          # 200
curl -s localhost:8799/items.json | head -c 120                        # JSON with sources
curl -s -o /dev/null -w "state %{http_code}\n" localhost:8799/state.json   # 404
```

Then open <http://127.0.0.1:8799> and confirm: gunmetal background with scanlines; clipped-corner cards with a left accent bar (brass Anthropic, teal OpenAI, cobalt Nous); the "Stale: anthropic-news, nous-blog" banner; the Lab and Kind chips filter the list; titles open in a new tab; reloading once shows no "new" badge on a first visit. Stop the server (`kill %1`) and `rm -rf /tmp/llm-feed-check`.

- [ ] **Step 9: Commit** (CHANGELOG line: `- Dashboard UI in the Mythological Punk theme, committed as app/dist/index.html.`)

```bash
git add app CHANGELOG.md
git commit -m "feat(app): add the themed feed dashboard and committed build" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: README and the one paid check

**Files:**

- Create: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# LLM Feed Dashboard

One merged, chronological feed of news and changelogs from Anthropic, OpenAI and
Nous Research, in the Mythological Punk theme. One stdlib-only Python process serves
the page and refreshes the data itself every day. No Docker, no cron, no Node at
runtime.

## Run

Needs Python 3.10+ and nothing else.

```sh
python3 serve.py                              # four free feeds only
FIRECRAWL_API_KEY=fc-... python3 serve.py     # also scrapes Anthropic news + Nous blog
```

Open <http://127.0.0.1:8787>. On start it pulls immediately if the last pull is
over 24 hours old, then once a day at `PULL_AT`.

| Setting             | Default              | Meaning                                                                                                                             |
| ------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `FIRECRAWL_API_KEY` | unset                | Enables the two scraped sources (1 credit each per pull, about 60 credits a month). Without it they show as stale. Never commit it. |
| `PULL_AT`           | `06:00`              | Daily pull time, `HH:MM` in UTC                                                                                                     |
| `DATA_DIR`          | `./data`             | Where `items.json` and `state.json` live                                                                                            |
| `--host` / `--port` | `127.0.0.1` / `8787` | Bind address. Bind to `0.0.0.0` only on a network you trust: there is no auth.                                                      |

By hand: `python3 -m feed pull` (fetch, merge, prune) and `python3 -m feed prune`
(prune only, no network).

## What it keeps

- Items older than **10 days** are pruned daily, except the 3 newest per lab.
- Pruned ids are remembered for 90 days (`data/state.json`) so a source that still
  lists them cannot bring them back.
- A source that fails keeps its last good items and shows a "stale" banner.
- Nous's blog has no dates, so its posts show "first seen" and age out 10 days after
  they first appear. The first run therefore shows its current featured posts as new.

## Keep it running

`serve.py` does not daemonize. Supervise it with the host's tool.

macOS, `~/Library/LaunchAgents/com.llm-feed.plist` (mode 600 if it holds the key),
then `launchctl load ~/Library/LaunchAgents/com.llm-feed.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.llm-feed</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>/path/to/llm-catalog/serve.py</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/llm-catalog</string>
  <key>EnvironmentVariables</key><dict>
    <key>FIRECRAWL_API_KEY</key><string>fc-...</string>
  </dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>
```

Linux, `/etc/systemd/system/llm-feed.service` with `/etc/llm-feed.env` (mode 600)
holding `FIRECRAWL_API_KEY=fc-...`:

```ini
[Unit]
Description=LLM feed dashboard
After=network-online.target

[Service]
WorkingDirectory=/path/to/llm-catalog
EnvironmentFile=/etc/llm-feed.env
ExecStart=/usr/bin/python3 /path/to/llm-catalog/serve.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Develop

```sh
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest
```

The UI source is in `app/` (React + Vite + Tailwind). `app/dist/index.html` is the
committed build, so a fresh clone runs without Node. After changing the UI:

```sh
cd app && pnpm install && pnpm run bundle   # rewrites app/dist/index.html
```

Theme tokens come from `~/.hermes/desktop-plugins/mythological-punk/mythological-punk.yaml`
and live in `app/src/theme.css`. Dark only, system fonts, no external assets.
````

- [ ] **Step 2: Hand off the one paid check to panda master** (2 credits). Do not run this yourself and do not create an env file.

Ask panda master to run, with their own key:

```bash
FIRECRAWL_API_KEY=fc-... .venv/bin/python -m feed --data /tmp/llm-feed-paid pull
```

Expected: `ok:` lists all six sources; `/tmp/llm-feed-paid/items.json` contains Anthropic news (including "Introducing Claude Sonnet 5.5") and Nous blog posts with `publishedAt: null`.

If a scraped source reports `parsed 0 items`, the live markdown differs from the fixtures. Have panda master run this and paste the first ~40 lines, then adjust the parser **and its fixture** in Task 3's files:

```bash
FIRECRAWL_API_KEY=fc-... .venv/bin/python -c "import os; from feed.scrape_pages import firecrawl_markdown as f; print(f('https://nousresearch.com/blog', os.environ['FIRECRAWL_API_KEY'])[:1500])"
```

- [ ] **Step 3: Final verification and commit**

Run: `.venv/bin/python -m pytest -q` → `51 passed`.
Confirm `git status` is clean apart from ignored paths (`data/`, `.venv/`).

CHANGELOG line: `- README with run, configuration and supervision instructions.`

```bash
git add README.md CHANGELOG.md
git commit -m "docs: add README with run and supervision instructions" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
