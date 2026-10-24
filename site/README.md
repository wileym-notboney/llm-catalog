# Site

A single-file page published as a claude.ai Artifact
(<https://claude.ai/artifact/XBtWYqy8mpKe1HvfcRucDb>) with two tabs: the **news feed** built from
the repo's own pull (`data/items.json`) and the **model catalog** (`app/src/models.json`) with a
side-by-side compare. It is not served by `serve.py`, so it adds no new served path.

```sh
python3 site/build.py      # inlines models.json + data/items.json into template.html -> index.html
```

A daily scheduled task pulls, builds and republishes it at 05:40 UTC.

Full documentation: [`docs/knowledge-base/`](../docs/knowledge-base/README.md), starting with
[The site](../docs/knowledge-base/site.md) and [Daily refresh](../docs/knowledge-base/daily-refresh.md).
