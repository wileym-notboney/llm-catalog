# ABOUTME: Builds the standalone site: inlines app/src/models.json and the pulled data/items.json into
# ABOUTME: site/template.html. Stdlib only; writes site/index.html, which is published as an Artifact.
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "site" / "template.html"
CATALOG = ROOT / "app" / "src" / "models.json"
OUTPUT = ROOT / "site" / "index.html"

LABS = {"anthropic", "openai", "nous"}
KINDS = {"news", "changelog", "release"}
TIMESTAMP = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$", re.IGNORECASE)
EMPTY_FEED = {"generatedAt": None, "sources": {}, "items": []}


def _is_timestamp(value: object) -> bool:
    return isinstance(value, str) and bool(TIMESTAMP.search(value))


def validate_feed(feed: object) -> dict:
    """The same shape check the dashboard runs in app/src/lib/feed.ts, so a bad file never reaches the page."""
    def invalid() -> None:
        raise SystemExit("error: items.json has an invalid catalog shape; refusing to build")

    if not isinstance(feed, dict) or not isinstance(feed.get("sources"), dict) or not isinstance(feed.get("items"), list):
        invalid()
    if feed.get("generatedAt") is not None and not _is_timestamp(feed["generatedAt"]):
        invalid()
    for status in feed["sources"].values():
        if not isinstance(status, dict):
            invalid()
        if status.get("lastOk") is not None and not _is_timestamp(status["lastOk"]):
            invalid()
        if status.get("lastError") is not None and not isinstance(status["lastError"], str):
            invalid()
    for item in feed["items"]:
        if not isinstance(item, dict):
            invalid()
        if not all(isinstance(item.get(key), str) for key in ("id", "lab", "kind", "title", "summary", "url", "source")):
            invalid()
        if item["lab"] not in LABS or item["kind"] not in KINDS:
            invalid()
        if not re.match(r"^https?://", item["url"], re.IGNORECASE):
            invalid()
        if not _is_timestamp(item.get("firstSeenAt")):
            invalid()
        if item.get("publishedAt") is not None and not _is_timestamp(item["publishedAt"]):
            invalid()
    return feed


def load_feed(data_dir: Path) -> dict:
    """No items.json yet means no pull has run: show an empty feed. A corrupt one is refused, never emptied."""
    path = data_dir / "items.json"
    if not path.exists():
        return EMPTY_FEED
    try:
        feed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: {path} is not valid JSON ({exc}); refusing to build") from exc
    return validate_feed(feed)


def inline(value: object) -> str:
    # "</" is escaped so catalog text can never close the <script> block it is inlined into.
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def build(data_dir: Path) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    for placeholder in ("__CATALOG__", "__FEED__"):
        if template.count(placeholder) != 1:
            raise SystemExit(f"error: {TEMPLATE.name} must contain {placeholder} exactly once")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    return (template
            .replace("__CATALOG__", inline(catalog))
            .replace("__FEED__", inline(load_feed(data_dir))))


if __name__ == "__main__":
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    OUTPUT.write_text(build(data_dir), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
