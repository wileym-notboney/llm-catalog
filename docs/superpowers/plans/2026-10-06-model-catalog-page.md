# Model catalog page (`#/models`) — plan

Date: 2026-10-06. Status: in progress.
Design decisions approved by panda master in-session (see "Decisions" below).

## Goal

A second page on the dashboard: a curated catalog of current LLM models with their
strengths and weaknesses, covering **Anthropic**, **OpenAI** and **Ollama** (local,
open-weight) providers. The feed page keeps working exactly as it does now.

## Decisions (approved, with the rejected option and why)

| #   | Decision                                                                                                                                                                                                                                                                                           | Rejected alternative                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Bundled JSON.** `app/src/models.json` is the single source of truth, imported into the Parcel bundle and therefore inlined into the committed `app/dist/index.html`. No fetch, no loading/error state, **`serve.py` unchanged**. Updating the catalog = edit the JSON, re-run `pnpm run bundle`. | A runtime-fetched `/models.json` route: adds a served path (new 404 assertions against the "only `app/dist` and `/items.json`" invariant) and fetch/error handling, for data that changes monthly.  |
| 2   | **Hand-curated, web-researched.** Strengths/weaknesses are editorial judgement no API returns. Each entry carries a `docs` link; the catalog carries `reviewedAt` so staleness is visible.                                                                                                         | Wiring provider model-list endpoints into `feed/`: needs `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, a new pipeline module, and a second source of truth to reconcile against the hand-written judgement. |
| 3   | **Hash routes + masthead nav.** `#/` feed, `#/models` catalog. ~10 lines of `hashchange` handling, no router dependency, works from the single static file, back button and bookmarks work.                                                                                                        | A `useState` tab toggle: not linkable, back button dead.                                                                                                                                            |

## Invariants this must not break

- Runtime stays stdlib-only Python; **no new runtime dependency** and no new npm dependency
  (hash routing is hand-rolled precisely so no router is added).
- `serve.py` and its tests are untouched: only `app/dist` and `/items.json` are served.
- Only http(s) links reach the page — enforced for catalog `docs` links by the new test,
  the same rule `feed/items.py` applies to feed URLs.
- `app/dist/index.html` stays a committed, self-contained build with no external assets.

## Data shape (`app/src/models.json`)

```json
{
  "reviewedAt": "2026-10-06",
  "models": [
    {
      "id": "claude-opus-5-5",
      "name": "Claude Opus 5.5",
      "provider": "anthropic",
      "role": "Long-running agentic coding and knowledge work",
      "context": "1M tokens",
      "price": "$4 / $20 per MTok",
      "size": null,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "docs": "https://platform.claude.com/docs/en/models/opus-5-5/overview"
    }
  ]
}
```

`price` applies to hosted models, `size` to local ones; each is `null` where it does not
apply, and the UI simply omits what is missing. Providers are `anthropic`, `openai`,
`ollama`.

## Sources consulted (2026-10-06)

- `platform.claude.com/docs/en/models/overview` — Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 4.5.
- `developers.openai.com/api/docs/models` — GPT-6 Astra, GPT-6.1 Sol, GPT-6 Luna.
- `ollama.com/library?sort=popular` — roster and capability tags for the local entries.

Only models confirmed on a provider's own page are listed. Third-party "best Ollama
models" listicles disagreed with each other and with the official library, so no
benchmark numbers from them appear in the catalog.

## Milestones

Each milestone ends green before the next starts.

### M1 — data and its validation (Python)

- `app/src/models.json` with the curated entries.
- `tests/test_models_catalog.py`: required fields present and non-empty; `provider` in the
  allowed set; ids unique; `strengths`/`weaknesses` non-empty lists of non-empty strings;
  every `docs` link `https://`; `reviewedAt` a real ISO date.
- Validation: `.venv/bin/python -m pytest tests/test_models_catalog.py`.

### M2 — routing shell

- `app/src/lib/route.ts`: `readRoute()` / `useRoute()` over `location.hash` (`#/` → feed,
  `#/models` → models, anything else → feed).
- Extract the current feed body from `App.tsx` into `app/src/Feed.tsx` unchanged;
  `App.tsx` becomes the shell (crest, masthead, nav, route switch).
- `resolveJsonModule: true` added to `tsconfig.app.json` so `tsc -b` accepts the import.
- Validation: `pnpm run lint` and `pnpm exec tsc -b`; feed page renders as before.

### M3 — the catalog page

- `app/src/lib/models.ts`: types mirroring the JSON, plus the pure display helpers
  (provider filter, catalog ordering) — React-free, like `lib/feed.ts`.
- `app/src/Models.tsx`: provider chips reusing the existing `.chips`/`.chip` styles, one
  card per model with role, specs, strengths and weaknesses, and the `reviewedAt` date.
- Theme additions in `theme.css` only where the feed's classes do not already cover it.
- Validation: `pnpm run lint`, `pnpm exec tsc -b`, visual check at `#/models`.

### M4 — build, docs, full pass

- `cd app && pnpm run bundle` to rewrite `app/dist/index.html`.
- README (a "Pages" note and how to update the catalog), `AGENTS.md` (layout + the
  catalog-update step), `CHANGELOG.md` line.
- Validation: full `.venv/bin/python -m pytest` (130 existing + the new catalog tests),
  and `python3 serve.py` serving both routes from the committed build.

## Out of scope

- Auto-refreshing the roster from provider APIs (decision 2).
- Benchmark tables or scores — the catalog is qualitative on purpose.
- Any change to the feed pipeline, `serve.py`, or the paid-attempt accounting.
