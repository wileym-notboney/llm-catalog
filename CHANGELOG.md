# Changelog

## Unreleased

- Project scaffolding, design spec, implementation plan and normalized item helpers.
- RSS and Atom parsers with a DTD guard and http(s)-only links.
- Firecrawl scrape client and parsers for Anthropic news and the Nous blog.
- Item store with 10-day retention, per-lab floor of 3 and 90-day tombstones.
- python3 -m feed pull|prune: one pull across six sources, stale handling, guarded prune; canary/rc tags filtered.
- serve.py: static server plus daily scheduler with catch-up on start and crash backoff.
- Dashboard UI in the Mythological Punk theme, committed as app/dist/index.html.
