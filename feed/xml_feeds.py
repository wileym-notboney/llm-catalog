# ABOUTME: Parsers for RSS 2.0 and Atom feeds into normalized items, using only the stdlib.
# ABOUTME: Atom entries can be filtered by title so noisy canary/nightly releases never land.
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from feed.items import is_web_url, make_item, parse_iso

ATOM = "{http://www.w3.org/2005/Atom}"


def _safe_root(xml_text: str) -> ET.Element:
    """Refuse DTDs and entity declarations, the vector for billion-laughs style bombs.

    The sources are fixed HTTPS feeds, so this stdlib guard stands in for defusedxml.
    """
    if re.search(r"<!(?:DOCTYPE|ENTITY)", xml_text, re.I):
        raise ValueError("feed declares a DTD or entity")
    return ET.fromstring(xml_text)


def _rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _iso_or_none(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_iso(value.strip()).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_rss(xml_text: str, *, lab: str, kind: str, source: str) -> list[dict]:
    items = []
    for node in _safe_root(xml_text).iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not is_web_url(link):
            continue
        items.append(
            make_item(
                lab=lab,
                kind=kind,
                source=source,
                title=title,
                url=link,
                summary=node.findtext("description") or "",
                published_at=_rfc822(node.findtext("pubDate")),
            )
        )
    return items


def parse_atom(
    xml_text: str, *, lab: str, kind: str, source: str, skip_title: str | None = None
) -> list[dict]:
    items = []
    for entry in _safe_root(xml_text).iter(f"{ATOM}entry"):
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        href = next(
            (
                link.get("href")
                for link in entry.findall(f"{ATOM}link")
                if link.get("rel", "alternate") == "alternate"
            ),
            None,
        )
        if not title or not href or not is_web_url(href):
            continue
        if skip_title and re.search(skip_title, title, re.I):
            continue
        items.append(
            make_item(
                lab=lab,
                kind=kind,
                source=source,
                title=title,
                url=href,
                summary=entry.findtext(f"{ATOM}content") or "",
                published_at=_iso_or_none(entry.findtext(f"{ATOM}updated")),
            )
        )
    return items
