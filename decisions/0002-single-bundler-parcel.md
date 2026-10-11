# 0002 — Parcel is the single bundler; Vite removed

- Status: accepted
- Date: 2026-10-10

## Context

The `app/` scaffold shipped with **two** bundlers. Vite provided the `dev`/`build`/`preview`
scripts and `vite.config.ts`; Parcel (`parcel build` + `html-inline`) provided the `bundle`
script. Only the Parcel path produces the committed artifact — the single, self-contained
`app/dist/index.html` that `serve.py` serves and that lets a fresh clone run without Node.
Vite never produced the shipped file. Maintaining two toolchains and two config sets, plus a
fork in how the app is built, bought nothing.

## Decision

**Parcel is the only bundler.** Vite and its config are removed:

- `dev` becomes `parcel index.html --port 1234 --dist-dir .bundle` (HMR; output to a
  git-ignored throwaway dir so the committed `app/dist` is never clobbered).
- `bundle` (Parcel build + `html-inline` → `app/dist/index.html`) is unchanged — still the
  only thing that writes the committed artifact.
- Deleted: `vite.config.ts`, `tsconfig.node.json` (existed only to type-check the Vite
  config), the `vite`/`@vitejs/plugin-react`/`@types/node` devDeps, the `vite/client` type
  reference, and the `build`/`preview` scripts.

## Consequences

- One toolchain, one build path, one config to reason about.
- `pnpm run dev` now listens on **1234** (Parcel), not 5173 (Vite); `.claude/launch.json`
  was repointed accordingly.
- The committed `app/dist/index.html` is byte-for-byte unchanged by this switch (verified by
  rebuild + `git diff`), because the `bundle` path was already the Parcel one.

## Alternatives rejected

- **Keep both bundlers** — two toolchains and a contributor-facing fork for no gain.
- **Keep Vite, drop Parcel** — the inlined single-file artifact comes from Parcel +
  `html-inline`; reproducing it on Vite would add plugins and rework the one file that must
  keep rendering.
