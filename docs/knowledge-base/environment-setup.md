---
title: Environment setup
updated: 2026-10-24
---

# Environment setup

[← Index](README.md)

The daily refresh runs in a **cloud environment**: a reusable set of settings on claude.ai (network
access, secrets, setup script) that every cloud session starts from. Two settings decide how many
of the five sources work. Only you can change them.

Where: open the cloud environment menu in the session's title bar, then **Edit**. Official steps:
<https://code.claude.com/docs/en/cloud-environments#network-access>.

## 1. Allow `github.com` (free; fixes Claude Code releases)

The Claude Code releases source is a GitHub feed. The environment's network policy currently
refuses `github.com`, so that source fails with **HTTP 403** and shows as stale.

Fix: under **Network access**, either choose a broader access level, or add `github.com` under
**Allowed domains**, leaving **Allow package managers** ticked.

## 2. Add the Firecrawl key (paid; adds Anthropic news and the Nous blog)

These two sources are web pages read through Firecrawl, which needs your API key. Without it they
show as stale with `FIRECRAWL_API_KEY not set`. That is the expected, safe behaviour.

Fix: add a secret named exactly `FIRECRAWL_API_KEY` with your key as the value in the environment's
settings.

Rules (from `AGENTS.md`):

- The key lives **only** in the environment. Never put it in a file, a commit, a chat message, a log
  or `data/`.
- Each pull spends 1 credit per paid source, so about **60 credits a month** at one run a day.
- Paid calls are never retried.

## Check it worked

The next run's report lists the sources that were OK. On the site, the stale banner on the
**News feed** tab disappears for each fixed source.

Related: [Daily refresh](daily-refresh.md), [Troubleshooting](troubleshooting.md).
