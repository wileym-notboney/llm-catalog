# UI source (`app/`)

The dashboard's frontend: React + TypeScript, styled with Tailwind, in the Mythological
Punk theme. Two hash-routed pages live here — the feed (`#/`) and the model catalog
(`#/models`) — assembled in `src/App.tsx`. See the repo root `AGENTS.md` for the source
layout and the invariants this UI must hold.

## The committed build

`dist/index.html` is a **single self-contained file** (JS, CSS and the model catalog all
inlined) and it is committed to the repo, so a fresh clone of the project runs with no Node
installed — `serve.py` just serves it. Regenerate it after any UI or `src/models.json`
change:

```sh
pnpm install          # once, or after dependency changes
pnpm run bundle        # Parcel builds, html-inline inlines -> rewrites dist/index.html
```

`pnpm run bundle` is the **only** thing that should ever write `dist/index.html`.

## Scripts

| Script            | What it does                                                                                                |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| `pnpm run dev`    | Parcel dev server with HMR on <http://localhost:1234>; output goes to a throwaway `.bundle/`, never `dist/` |
| `pnpm run bundle` | Production build → inlined `dist/index.html` (the committed artifact)                                       |
| `pnpm test`       | Offline regression checks via Node's built-in test runner (`tests/*.test.mjs`)                              |
| `pnpm run lint`   | oxlint                                                                                                      |

## Toolchain

Parcel is the single bundler (the `index.html` entry drives both `dev` and `bundle`);
`html-inline` collapses the Parcel output into one file. Tailwind runs through PostCSS
(`tailwind.config.js`, `postcss.config.js`). Runtime dependencies are deliberately just
`react` and `react-dom` — see `decisions/0002-single-bundler-parcel.md` and
`decisions/0003-dependency-trim.md` for why.

Theme tokens originate from the Mythological Punk plugin and live in `src/theme.css`.
Dark only, system fonts, no external assets.
