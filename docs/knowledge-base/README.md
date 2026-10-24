---
title: Knowledge base index
updated: 2026-10-24
---

# LLM Feed knowledge base

The one place for how this project works, why it was built this way, and how to run and fix it.
Start here; every page links back to this index.

Think of the project as a small newspaper. The **pipeline** is the reporter that collects stories
each morning, the **dashboard** is the copy printed for your desk at home, and the **site** is the
same paper pinned to a public noticeboard that a helper re-pins every day.

## Pages

| Page | Read it when you want to… |
| --- | --- |
| [How the pieces fit](how-the-pieces-fit.md) | understand the parts (pipeline, dashboard, site, daily refresh) and how data flows between them |
| [The site](site.md) | know what the published site shows, how it is built, and what each file does |
| [Daily refresh](daily-refresh.md) | understand, check, pause or change the scheduled task that keeps the site current |
| [Environment setup](environment-setup.md) | allow `github.com` or add the Firecrawl key so all five sources work |
| [Design decisions](design-decisions.md) | know why the site looks the way it does: colours, contrast, layout, with sources |
| [Troubleshooting](troubleshooting.md) | fix a stale source, a failed build, a page that looks out of date |
| [Glossary](glossary.md) | look up a term (artifact, pull, tombstone, scheduled task…) |

## Key facts at a glance

- **Live site:** <https://claude.ai/artifact/XBtWYqy8mpKe1HvfcRucDb> (private until shared from its Share menu).
- **Refreshes:** daily at 05:40 UTC by the scheduled task "LLM Feed daily refresh".
- **Source code for the site:** `site/` in this repo; rebuilt with `python3 site/build.py`.
- **Local dashboard:** `python3 serve.py` → <http://127.0.0.1:8787>, refreshes itself daily at 06:00 UTC.
- **Rules that must not break:** `AGENTS.md` → "Invariants".

## Other project documents

- `AGENTS.md`: instructions and invariants for anyone (human or agent) changing the code.
- `README.md` (repo root): how to run the dashboard.
- `CHANGELOG.md`: what changed and when.
- `docs/superpowers/specs/2026-10-05-llm-feed-dashboard-design.md`: the original dashboard design.
