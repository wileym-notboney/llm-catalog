# 0003 — Runtime dependencies trimmed to react + react-dom

- Status: accepted
- Date: 2026-10-10

## Context

`app/package.json` declared ~40 runtime dependencies inherited from a UI-kit scaffold — all
26 `@radix-ui/*` packages plus `@hookform/resolvers`, `class-variance-authority`, `clsx`,
`cmdk`, `date-fns`, `embla-carousel-react`, `lucide-react`, `next-themes`,
`react-day-picker`, `react-hook-form`, `react-resizable-panels`, `sonner`, `tailwind-merge`,
`vaul`, and `zod`. A grep of `app/src` showed it imports **only** `react` and
`react-dom/client`; none of those packages are referenced. The unused `@/*` path alias (and
its `parcel-resolver-tspaths` resolver) was likewise dead. For a self-hosted dashboard, every
unused dependency is attack surface and a future `pnpm install` that can break the committed
build for no benefit.

## Decision

Runtime dependencies are **`react` and `react-dom` only.** Every never-imported package is
removed, along with the unused `@/*` alias and `parcel-resolver-tspaths`. Dev dependencies
keep just the Parcel/PostCSS/Tailwind/types/oxlint toolchain actually used by `bundle`,
`dev`, `test`, and `lint`.

## Consequences

- Smaller dependency tree → less supply-chain surface and fewer moving parts on install.
- The committed `app/dist/index.html` is unchanged (verified by rebuild + `git diff`):
  nothing removed was ever imported, so it cannot affect the bundle output.
- Re-introducing any UI library is a deliberate act with its own justification, not an
  accident of the scaffold. Adding a runtime dependency needs approval per `AGENTS.md`.

## Alternatives rejected

- **Leave the deps in place** — carries ~38 unused packages as live attack surface and
  install fragility purely to avoid editing one file.
