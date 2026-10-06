# AGENTS.md — LLM Feed Dashboard

## Names (recorded once, don't make a ceremony of it)

- Agent: **Dr. Biz-Nasty the Third, Rad Dude of the Rodeo Rally**
- Panda master: **Harp-Dog "Turbo" McSlamjam**

## What this is

A self-contained dashboard: one merged, chronological feed of news and changelogs from
Anthropic, OpenAI and Nous Research, in the Mythological Punk theme. One stdlib-only
Python process (`serve.py`) serves the committed React build and refreshes the data
itself daily. No Docker, no host cron, no Proxmox, no Node at runtime.

Design: `docs/superpowers/specs/2026-10-05-llm-feed-dashboard-design.md`.
Plan (implemented): `docs/superpowers/plans/2026-10-05-llm-feed-dashboard.md`.

## Commands

```sh
.venv/bin/python -m pytest              # 51 tests, no network, no credits
python3 serve.py                        # http://127.0.0.1:8787, scheduler included
python3 -m feed pull                    # fetch, merge, prune by hand (--data DIR)
python3 -m feed prune                   # prune only, offline
cd app && pnpm run bundle               # rewrite app/dist/index.html after UI changes
```

Dev setup: `python3 -m venv .venv && .venv/bin/pip install pytest`. Python 3.10+.

## Layout

`feed/` is the pipeline (`items`, `xml_feeds`, `scrape_pages`, `store`, `pull`,
`schedule`, `__main__`); `serve.py` is the server and scheduler thread; `app/` is the UI
source and `app/dist/index.html` is its committed single-file build; `tests/` has one
module per feed module plus `fixtures.py`. `data/` is runtime state and git-ignored.

## Invariants — do not break these

- Runtime is stdlib only. Ask before adding any runtime dependency (`pytest` is dev only).
- `FIRECRAWL_API_KEY` comes from the environment only. Never write it to a file, a log
  line, an error message or `data/`. Claude never edits `.env` files.
- Scrapes cost 1 credit each (cache hits too) and the daily pull makes at most 2. Never
  add retries around a paid call. `step()` backs off an hour after a crash on purpose.
- Retention: 10 days, newest 3 per lab always kept, tombstones for 90 days. Tombstones are
  why pruned items don't come back from long source feeds; don't remove them.
- A source that fails, or parses 0 items, goes stale and keeps its old items. Never let it
  empty the feed. A corrupt `items.json` is refused, never treated as empty.
- Only `app/dist` and `/items.json` are served; `state.json` must 404. Bind 127.0.0.1.
- Only http(s) links reach the page. XML with a DTD/entity is rejected.
- Per-source status lives only in `items.json`; `state.json` holds `lastPull`, `lastPrune`,
  `tombstones`. One source of truth.

## Gotchas learned the hard way

- `_DATE` in `feed/scrape_pages.py` has no leading `\b` on purpose: Anthropic's category
  runs into the month (`AnnouncementsSep 28, 2026`). Adding one silently drops launch posts.
- The two scrapers are verified against fixtures captured from live pages, not yet against
  a paid live run. If one reports `parsed 0 items`, fetch the markdown, update the parser
  and its fixture together.
- GitHub release feeds contain pipeline noise (`canary`, `nightly`, `rc.N`, `abandoned-rc.N`
  with JSON bodies). The filter is `SKIP_PRERELEASE` in `feed/pull.py`.
- Nous's blog is undated, so its posts show "first seen" and age out 10 days later.
- The first pull creates ~1,400 tombstones (OpenAI's RSS is long); `state.json` ≈ 100 KB.
- Never inline the PNG textures from the theme plugin (the marble is 2.6 MB).

## Process notes

- Branch `feature/llm-feed-dashboard`; commits `type(scope): description`, one per task, with
  a `CHANGELOG.md` line.
- The global changelog pre-commit hook is **suspended** (2026-10-05, panda master's call) and
  due for reassessment; see `~/.claude/CLAUDE.md`. Keep the changelog current anyway.
- Never push or run the paid Firecrawl check without panda master: it uses their key.
