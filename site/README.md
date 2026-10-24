# Model codex site

A standalone, single-file page that shows the model catalog (`app/src/models.json`) on its
own, outside the dashboard. It is published as a claude.ai Artifact; it is **not** served by
`serve.py`, so it adds no new served path.

## What it shows

- One full-width band per provider in that provider's brand colours: Anthropic orange,
  OpenAI white, Ollama black. Every model card is the same neutral dark card, so models are
  compared on equal terms; a strip across the top of each card carries the brand.
- A provider filter, and **+ Compare** on each card: pick 2 to 4 models, then **Compare**
  shows them side by side in one table.

## Files

| File           | What it is                                                         |
| -------------- | ------------------------------------------------------------------ |
| `template.html`| The page source, with `__CATALOG__` where the catalog JSON goes    |
| `build.py`     | Inlines `app/src/models.json` into the template (stdlib only)      |
| `index.html`   | The built page. Committed, like `app/dist/index.html`              |

## Rebuild after editing the catalog or the template

```sh
python3 site/build.py      # rewrites site/index.html
```

Like the dashboard, the page is a snapshot: editing `models.json` changes nothing here until
you rebuild and republish.

## Colour and accessibility notes

- Brand colours: Anthropic from its brand guidelines (`#d97757`, `#141413`, `#faf9f5`);
  OpenAI and Ollama are black and white brands, so one is inverted to tell them apart.
- No navy or blue-tinted colours anywhere: the page ground is neutral graphite (`#262626`).
- Card text is 7:1 contrast or better (WCAG 2.2 AA asks for 4.5:1). Links are underlined and
  selected cards say "✓ Comparing", so nothing relies on colour alone.
