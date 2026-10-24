---
title: Glossary
updated: 2026-10-24
---

# Glossary

[← Index](README.md)

**Artifact.** A web page hosted by claude.ai. Private by default; shared from its Share menu. Each
publish to the same URL creates a new version and keeps the link.

**Build.** Turning `site/template.html` plus the data into the finished `site/index.html`, done by
`python3 site/build.py`.

**Cloud environment.** The saved settings (network access, secrets, setup) that cloud sessions start
from. See [Environment setup](environment-setup.md).

**Credit (Firecrawl).** Firecrawl's unit of payment. Each scrape of a paid source costs 1.

**Dashboard.** The original app, served on your own computer by `serve.py`.

**Firecrawl.** A paid service that reads web pages without a feed. Used for Anthropic news and the
Nous blog. Needs `FIRECRAWL_API_KEY`.

**Invariant.** A rule the code must never break, listed in `AGENTS.md`.

**Pull.** One run of the pipeline, `python3 -m feed pull`: fetch, merge, prune.

**RSS / Atom.** Standard machine-readable news feeds. Free to read.

**Scheduled task.** A stored instruction claude.ai runs on a timer in a fresh cloud session. See
[Daily refresh](daily-refresh.md).

**Stale source.** A source whose last fetch failed. It keeps its old stories and shows in the banner.

**Tombstone.** A note the pipeline keeps for 90 days about a pruned story, so it does not come back
from a long feed. Lives in `data/state.json`.

**WCAG.** Web Content Accessibility Guidelines, the standard for readable, usable web pages.
