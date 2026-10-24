---
title: The site
updated: 2026-10-24
---

# The site

[← Index](README.md)

**Live:** <https://claude.ai/artifact/XBtWYqy8mpKe1HvfcRucDb>. It is a claude.ai *artifact* (a web page
hosted by claude.ai), private by default. To let someone else see it, use the page's **Share** menu.

## What it shows

**News feed tab** (opens first). Every story from the last pull, newest first, using the same rules
as the dashboard's feed page (`app/src/Feed.tsx`, `app/src/lib/feed.ts`):

- Filters by lab (Anthropic, OpenAI, Nous) and by kind (news, changelog, release).
- "Updated … ago" with the exact time of the last pull.
- A banner naming any source that did not refresh, with the reason (for example
  `FIRECRAWL_API_KEY not set`). Those sources keep their last good stories.
- "(first seen)" next to the date when a source gives no publish date (the Nous blog does this).
- A "new" badge on stories that arrived since your last visit (remembered in your browser only).

**Models tab.** The hand-curated catalog from `app/src/models.json`, one section per provider
(Anthropic, OpenAI, Ollama). Each card shows role, context window, price or sizes, strengths and
weaknesses, and a docs link.

- **+ Compare** on any card adds it to a tray at the bottom. Pick 2 to 4 models, press **Compare**,
  and they appear side by side in one table. **← All models** goes back. Picks are remembered in your
  browser only.

## Files

| File | What it is |
| --- | --- |
| `site/template.html` | The page source: layout, styles, behaviour. Has two placeholders, `__CATALOG__` and `__FEED__`. |
| `site/build.py` | Fills the placeholders with `app/src/models.json` and `data/items.json`, writes `site/index.html`. Python standard library only. |
| `site/index.html` | The built page, ready to publish. Committed as a snapshot; the daily refresh rebuilds it but does not commit it. |
| `site/README.md` | Short summary of the folder; this knowledge base is the full version. |

## How the build protects the page

`site/build.py` checks `items.json` with the same rules as the dashboard before using it:

- A missing `items.json` means no pull has run: the page shows an empty feed with a note.
- A corrupt or wrongly shaped `items.json` **stops the build**. It is never treated as empty, so a bad
  file can never wipe the published feed.
- Only `http://` and `https://` links are accepted.
- Text is inserted so it can never break out of the page's data block (`</` is escaped).

Only `items.json` is embedded. `state.json` and `attempts.json` (internal bookkeeping) never leave
`data/`, matching the dashboard's rule that they are never served.

## Rebuild and publish by hand

You rarely need this, because the [daily refresh](daily-refresh.md) does it. To do it yourself:

```sh
python3 -m feed pull        # optional: fetch fresh stories into data/items.json
python3 site/build.py       # writes site/index.html
```

Then ask Claude to publish `site/index.html` to the site's URL. Publishing to the **same URL** keeps
the link; a new URL would create a separate page.

After editing `app/src/models.json`, also run `cd app && pnpm run bundle` so the dashboard picks it up,
and `.venv/bin/python -m pytest tests/test_models_catalog.py` to validate the catalog.

Related: [Design decisions](design-decisions.md), [Troubleshooting](troubleshooting.md).
