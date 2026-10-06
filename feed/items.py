# ABOUTME: Normalized feed item construction plus the text and date helpers every parser shares.
# ABOUTME: One item shape for all labs; field meanings are defined in the design spec.
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

SUMMARY_MAX = 280
TITLE_MAX = 200

_BLOCK_TAGS = re.compile(r"</?(?:p|li|ul|ol|br|div|h[1-6])\b[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def clean_text(raw: str, limit: int = SUMMARY_MAX) -> str:
    """Strip markup, unescape entities, collapse whitespace, truncate with an ellipsis."""
    text = _BLOCK_TAGS.sub(" ", raw or "")
    text = html.unescape(_TAGS.sub("", text))
    text = _SPACE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_web_url(url: str) -> bool:
    """Only http(s) links are kept; a `javascript:` href from a feed must never reach the page."""
    return url.lower().startswith(("https://", "http://"))


def item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def make_item(
    *,
    lab: str,
    kind: str,
    source: str,
    title: str,
    url: str,
    summary: str = "",
    published_at: datetime | None = None,
) -> dict:
    """Build one item. `firstSeenAt` stays None until the store merges it."""
    return {
        "id": item_id(url),
        "lab": lab,
        "kind": kind,
        "title": clean_text(title, TITLE_MAX),
        "summary": clean_text(summary),
        "url": url,
        "publishedAt": iso(published_at) if published_at else None,
        "source": source,
        "firstSeenAt": None,
    }
