---
title: Troubleshooting
updated: 2026-10-24
---

# Troubleshooting

[← Index](README.md)

Find the symptom, then follow the fix. Start with the cause listed first; it is the most likely.

## The feed shows a "Not refreshed on the last pull" banner

The banner names each source and the reason. The source keeps its last good stories; nothing is lost.

| Reason in the banner | Cause | Fix |
| --- | --- | --- |
| `FIRECRAWL_API_KEY not set` | No Firecrawl key in the environment | Expected without a key. To add one, see [Environment setup](environment-setup.md#2-add-the-firecrawl-key-paid-adds-anthropic-news-and-the-nous-blog) |
| `HTTP 403` on Claude Code releases | The cloud environment blocks `github.com` | [Allow `github.com`](environment-setup.md#1-allow-githubcom-free-fixes-claude-code-releases) |
| `parsed 0 items` | The source's page layout changed | Update its parser in `feed/scrape_pages.py` and its test fixture together (see `AGENTS.md` → Gotchas) |
| Other HTTP error | The source was down | Usually clears on the next day's run |

## The site looks out of date

1. **Old version in an open tab.** Close the tab and open the link again. Open tabs can lag behind a
   new version.
2. **"Updated … ago" is more than a day old.** The daily run did not publish. Check the run's report
   in the scheduled tasks list ([Daily refresh](daily-refresh.md#check-change-pause-delete)).
3. **The task was paused or deleted.** Ask Claude to list scheduled tasks.

## The build stops with "refusing to build"

`site/build.py` found a corrupt or wrongly shaped `data/items.json`. This is deliberate: a bad file
must never empty the published feed. The site keeps showing the last good version. Look at
`data/items.json`; delete it only after confirming it is broken, then run `python3 -m feed pull` to
recreate it.

## A model's details are wrong

The catalog is hand-written in `app/src/models.json`. Edit it, run
`.venv/bin/python -m pytest tests/test_models_catalog.py`, then rebuild the site
([The site](site.md#rebuild-and-publish-by-hand)) and the dashboard (`cd app && pnpm run bundle`).

## Something on the page is hard to read

Leave a comment on the exact spot in the artifact and send it to Claude; the comment carries the
location. Colour and contrast rules are in [Design decisions](design-decisions.md).

Related: [Glossary](glossary.md).
