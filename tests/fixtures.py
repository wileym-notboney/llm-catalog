# ABOUTME: Shared test data: realistic RSS/Atom builders and trimmed copies of the scraped pages.
# ABOUTME: Shapes were captured from the live sources on 2026-10-05.
from __future__ import annotations

BS = "\\\\"  # the two backslashes Firecrawl emits before a hard line break


def rss(*entries: tuple[str, str, str]) -> str:
    """entries are (title, link, pubDate)."""
    body = "".join(
        f"<item><title><![CDATA[{title}]]></title><link>{link}</link>"
        f"<description><![CDATA[About {title}]]></description><pubDate>{date}</pubDate></item>"
        for title, link, date in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{body}</channel></rss>'


def atom(*entries: tuple[str, str, str]) -> str:
    """entries are (title, href, updated)."""
    body = "".join(
        f'<entry><updated>{updated}</updated><link rel="alternate" type="text/html" href="{href}"/>'
        f"<title>{title}</title><content type=\"html\">&lt;p&gt;Notes for {title}&lt;/p&gt;</content></entry>"
        for title, href, updated in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


ANTHROPIC_MD = (
    "# Newsroom\n\n- Press inquiries [press@anthropic.com](mailto:press@anthropic.com)\n\n"
    "![Video thumbnail](https://www.anthropic.com/_next/image?url=x)\n\n"
    f"[**Introducing Claude Sonnet 5.5** {BS}\n{BS}\nAnnouncementsSep 28, 2026{BS}\n{BS}\n"
    "A clear upgrade over Sonnet 5.](https://www.anthropic.com/claude-sonnet-5-5)\n\n"
    f"[AnnouncementsSep 22, 2026{BS}\n**Introducing Claude Opus 5.5** {BS}\n"
    "Opus 5.5 performs at the level of Fable 5.1.](https://www.anthropic.com/claude-opus-5-5)\n\n"
    "## News\n\nDateCategoryTitle\n\n"
    f"- [Oct 2, 2026Announcements{BS}\nAnthropic invests $100 million to train engineers]"
    "(https://www.anthropic.com/news/claude-frontier-academy)\n"
    f"- [Sep 22, 2026Announcements{BS}\nIntroducing Claude Opus 5.5]"
    "(https://www.anthropic.com/claude-opus-5-5)\n\n"
    "[See more](https://www.anthropic.com/news#)"
)

NOUS_MD = """[![](https://x/banner.webp)](https://nousresearch.com/refactoring-hermes-with-1393-agents)

ByTeknium

## [Refactoring Hermes with 1,393 agents](https://nousresearch.com/refactoring-hermes-with-1393-agents)

Hermes Agent autonomously plowed through a million lines of cleanup....

ByNightwing

## [Lighthouse Attention](https://nousresearch.com/lighthouse-attention)

A selection-based hierarchical attention ~17x faster than standard attention....

## Archive

### [Field Notes on Scaling MoE Expert Parallelism](https://nousresearch.com/moe-scaling-field-notes)

Documenting the journey of scaling expert parallelism....

## Hermes AgentHermes Agent

The self-improving AI agent built by Nous Research.
"""
