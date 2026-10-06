# LLM Feed Dashboard — Design

Date: 2026-10-05 · Status: draft, awaiting review

## Purpose

A personal dashboard showing one merged, chronological feed of news and changelog
items from Anthropic, OpenAI and Nous Research, styled with the Mythological Punk
Hermes theme. It updates itself daily at near-zero cost.

**Success criteria (verifiable):**

1. After the daily scheduled pull runs, new items from all four free feeds and both scraped
   pages appear on the page with no rebuild or republish.
2. A normal day costs at most 2 Firecrawl credits and 0 Claude tokens.
3. A failing source never empties or breaks the feed; it shows a "stale" marker.
4. `pytest` passes: feed-to-item mapping, de-dupe, and prune (including the
   per-lab floor and tombstones).

## Sources

| Lab       | Source                                             | Method                      | Credits/day |
| --------- | -------------------------------------------------- | --------------------------- | ----------- |
| Anthropic | anthropic.com/news                                 | Firecrawl scrape (markdown) | 1           |
| Anthropic | platform.claude.com/docs/en/release-notes/feed.xml | RSS via urllib              | 0           |
| Anthropic | github.com/anthropics/claude-code/releases.atom    | Atom via urllib             | 0           |
| OpenAI    | openai.com/news/rss.xml                            | RSS via urllib              | 0           |
| Nous      | nousresearch.com/blog                              | Firecrawl scrape (markdown) | 1           |
| Nous      | github.com/NousResearch/hermes-agent/releases.atom | Atom via urllib             | 0           |

Verified 2026-10-05: scrape = 1 credit (live `creditsUsed: 1`), JSON-extract = +4,
free plan = 1,000 credits/month. Daily cadence ≈ 60 credits/month.

## Normalized item

```json
{
  "id": "sha1(url)",
  "lab": "anthropic | openai | nous",
  "kind": "news | changelog | release",
  "title": "…",
  "summary": "plain text, ≤ 280 chars",
  "url": "…",
  "publishedAt": "ISO-8601 or null",
  "source": "anthropic-news | anthropic-api-notes | claude-code-releases | openai-news | nous-blog | hermes-agent-releases",
  "firstSeenAt": "ISO-8601"
}
```

`id` is the de-dupe key. `firstSeenAt` drives the "new since last visit" badge and
the sort order for undated items.

## Architecture

One self-contained, portable unit: **one plain `python3 serve.py` process that
serves the page and runs its own scheduler.** No Docker, no host cron, no Proxmox
dependency, no Node at runtime. Clone it, set the key, run it, on any machine with
Python 3. The built frontend (`app/dist`) is committed, so a fresh clone runs with
nothing to install or build.

```
serve.py (one stdlib-only Python process)
  ├─ HTTP thread   : serves app/dist + data/items.json (read-only)
  └─ scheduler thread
       daily  @ PULL_AT (default 06:00 UTC) : pull
       daily, right after the pull          : prune (10-day retention)
       on start, if last pull > 24h ago     : catch-up pull
  writes data/items.json + data/state.json  (./data, git-ignored)
```

Components, each independently testable:

| Unit | Job | Depends on |
| --- | --- | --- |
| `feed/` package (`items`, `xml_feeds`, `scrape_pages`, `store`, `pull`, `schedule`) | `pull` fetches the 4 feeds (stdlib `urllib`, `xml.etree`) and the 2 pages (Firecrawl REST via `urllib`), merges, then prunes as a separate guarded step. Also runnable by hand: `python3 -m feed pull\|prune` | stdlib only; `FIRECRAWL_API_KEY` env |
| `serve.py` | Static server plus scheduler thread; reads `state.json` to decide what is due | feed package |
| `data/items.json`, `data/state.json` | `items.json`: items plus per-source `lastOk` / `lastError` (the page reads it for the stale marker). `state.json`: `lastPull`, `lastPrune`, `tombstones` | none |
| `app/` (React + Vite) | Fetches `./items.json` at load. Merged feed, lab/kind filters, "new" badge, "stale" marker | theme tokens |
| `README.md` | Run instructions, plus copy-paste launchd and systemd examples to keep `serve.py` alive across reboots (documented, not shipped as files) | n/a |
| `tests/` | Fixtures for each feed shape; mapping, de-dupe, prune, scheduler due-logic | feed package |

## Schedule

- **Daily pull:** fetches all six sources; scrapes use `maxAge: 0` (the default
  cache served pages up to ~1 day old). Runs at `PULL_AT`, or at startup if the
  last pull is over 24h old, so a machine that was off still catches up.
- **Daily prune (right after the pull, separate step):** drops items older than
  **10 days** (~1.5 weeks; by `publishedAt`, else `firstSeenAt`) but always keeps
  the **3 newest per lab**, so a quiet lab (Nous posts rarely) never empties.
  Daily rather than weekly, because a weekly prune would let items live up to 17
  days. A separate step, so a prune bug cannot break ingestion.
- **Tombstones:** pruned ids go into `state.json` for 90 days, and `pull` skips
  any id on the list. Without this, the next pull re-ingests old entries that are
  still in the source feeds (OpenAI's RSS alone holds ~1,250 items), and they
  reappear flagged "new" with a fresh `firstSeenAt`. Ids older than 90 days expire.

## Firecrawl key handling (security)

The key is read from the `FIRECRAWL_API_KEY` environment variable, set by the
caller (`FIRECRAWL_API_KEY=… python3 serve.py`, or the `EnvironmentFile` / plist
entry in the README's supervision examples). The repo contains no key and no
`.env` file; the README documents the variable. The key is never committed, logged, or written
to `data/`; errors log the HTTP status, not request headers. Without a key, `pull`
still ingests the four free feeds and marks the two scraped sources stale.

## Error handling

- Feed fetch fails: keep that source's existing items, set `last_error`, UI shows
  "stale". `pull` exits non-zero only if every source failed, and the
  scheduler logs it, so a failure line means something.
- Scrape fails or is blocked: costs 0 credits, no retry; same stale handling.
- Writes go to a temp file then atomic rename, so the page never reads half a file.
- Undated items sort by `firstSeenAt`.

## Theme

Tokens from `~/.hermes/desktop-plugins/mythological-punk/mythological-punk.yaml`:
background `#080d16`, text `#d9e8f7`, primary `#4aa8ff`, accent `#d3a849`, radius
0.35rem, clipped-corner cards and scanline overlays, system fonts only. The crest SVG
is drawn inline; the PNG textures (the marble alone is 2.6 MB) are excluded.

## Known risks

- **Markdown parsing of the two scraped pages is the brittle part.** Anthropic's
  `/news` list is not strictly date-ordered, so items are sorted by parsed date.
  If the page layout changes and parsing breaks, the fallback is Firecrawl
  JSON-extract (+4 credits each, ~300 credits/month, still inside the free plan).
- The Firecrawl REST endpoint and request shape must be checked against current
  docs at plan time. This spec does not assume a version.
- `maxAge: 0` credit cost is unverified.

## Out of scope

Per-item AI summaries, search, auth, notifications, extra sources, a database,
JSON-extract by default, any Claude-run refresh path, and Docker (deferred until a
host that needs it; the stdlib-only runtime makes a container low value).

## Persistent files created

`feed/` package, `serve.py`, `tests/`, `data/` (git-ignored), `app/` (source plus
the committed `app/dist` build output; rebuild with `npm run build` when the UI
changes), `README.md`, `.gitignore`.
