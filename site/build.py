# ABOUTME: Builds the standalone model codex page: inlines app/src/models.json into site/template.html.
# ABOUTME: Stdlib only; writes site/index.html, which is committed like app/dist so it can be published as-is.
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "site" / "template.html"
CATALOG = ROOT / "app" / "src" / "models.json"
OUTPUT = ROOT / "site" / "index.html"
PLACEHOLDER = "__CATALOG__"


def build() -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f"error: {TEMPLATE.name} must contain {PLACEHOLDER} exactly once")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    # "</" is escaped so catalog text can never close the <script> block it is inlined into.
    blob = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, blob)


if __name__ == "__main__":
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
