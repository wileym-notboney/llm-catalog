# ABOUTME: Firecrawl REST client plus markdown parsers for the two sources with no RSS feed.
# ABOUTME: Anthropic's newsroom carries dates; Nous's blog does not, so its items stay undated.
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from http.client import HTTPException
from datetime import datetime, timezone

from feed.items import make_item

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"

# Byte caps bound memory on a hostile or runaway response. OpenAI's RSS alone holds ~1,250
# items, so the XML cap needs headroom; one scraped markdown page is far smaller.
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_PAGE_BYTES = 8 * 1024 * 1024


class FetchError(Exception):
    """A source could not be fetched or parsed. The message is safe to store and show."""


def read_capped(response, limit: int) -> bytes:
    """Read a body, refusing anything over `limit` bytes without buffering more than limit+1.

    `response` is any object with `read(size)`, which is what urlopen returns.
    """
    body = response.read(limit + 1)
    if len(body) > limit:
        raise FetchError(f"response exceeds the {limit // (1024 * 1024)} MiB limit")
    return body


def firecrawl_markdown(url: str, api_key: str, timeout: int = 90) -> str:
    """Scrape one page to markdown. maxAge=0 forces a live fetch instead of the 2-day cache."""
    body = json.dumps(
        {"url": url, "formats": ["markdown"], "onlyMainContent": True, "maxAge": 0}
    ).encode("utf-8")
    request = urllib.request.Request(
        FIRECRAWL_SCRAPE_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(read_capped(response, MAX_PAGE_BYTES))
    except urllib.error.HTTPError as error:
        raise FetchError(f"Firecrawl HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, HTTPException, ValueError) as error:
        raise FetchError(f"Firecrawl request failed: {type(error).__name__}") from None
    data = payload.get("data") if isinstance(payload, dict) else None
    markdown = data.get("markdown") if isinstance(data, dict) else None
    if not markdown or not isinstance(markdown, str) or not payload.get("success"):
        raise FetchError("Firecrawl returned no markdown")
    return markdown


_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
# No leading \b: the category runs straight into the month ("AnnouncementsSep 28, 2026").
_DATE = re.compile(rf"({_MONTHS}) (\d{{1,2}}), (\d{{4}})")
_DATE_PART = re.compile(rf"^[A-Za-z &]*({_MONTHS}) \d{{1,2}}, \d{{4}}[A-Za-z &]*$")
_LINK = re.compile(r"\[([^\[\]]+)\]\((https://[^)\s]+)\)")
_BREAK = re.compile(r"\\{1,2}[ \t]*\n|\n")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def parse_anthropic_news(markdown: str, *, source: str = "anthropic-news") -> list[dict]:
    """Every link whose text carries a date is an article; the newsroom lists some twice."""
    items, seen = [], set()
    for text, url in _LINK.findall(markdown):
        date = _DATE.search(text)
        if not date or url in seen:
            continue
        seen.add(url)
        parts = [part.strip() for part in _BREAK.split(text) if part.strip()]
        content = [part for part in parts if not _DATE_PART.match(part)]
        bold = _BOLD.search(text)
        title = bold.group(1).strip() if bold else (content[0] if content else "")
        summary = " ".join(part for part in content if "**" not in part and part != title)
        published = datetime.strptime(" ".join(date.groups()), "%b %d %Y").replace(
            tzinfo=timezone.utc
        )
        items.append(
            make_item(
                lab="anthropic",
                kind="news",
                source=source,
                title=title,
                url=url,
                summary=summary,
                published_at=published,
            )
        )
    return items


_NOUS_POST = re.compile(
    r"^## \[(?P<title>[^\]]+)\]\((?P<url>https://nousresearch\.com/[^)\s]+)\)\s*\n+(?P<summary>[^\n]+)",
    re.M,
)


def parse_nous_blog(markdown: str, *, source: str = "nous-blog") -> list[dict]:
    """Featured posts are `## [Title](url)` headings. The `###` archive is old and is skipped."""
    return [
        make_item(
            lab="nous",
            kind="news",
            source=source,
            title=match["title"],
            url=match["url"],
            summary=match["summary"],
        )
        for match in _NOUS_POST.finditer(markdown)
    ]
