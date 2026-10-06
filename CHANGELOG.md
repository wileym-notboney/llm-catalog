# Changelog

## Unreleased

- items.json and state.json are shape-checked on read: a valid-JSON file with the wrong dashboard shape is refused with a StoreError naming the file (CLI exits 2, scheduler backs off) before anything is written; unknown fields are preserved.
- Added a proposed incremental hardening plan, deferred optimization backlog, and Sonnet/Opus implementation and review handoff.
- Project scaffolding, design spec, implementation plan and normalized item helpers.
- RSS and Atom parsers with a DTD guard and http(s)-only links.
- Firecrawl scrape client and parsers for Anthropic news and the Nous blog.
- Item store with 10-day retention, per-lab floor of 3 and 90-day tombstones.
- python3 -m feed pull|prune: one pull across six sources, stale handling, guarded prune; canary/rc tags filtered.
- serve.py: static server plus daily scheduler with catch-up on start and crash backoff.
- Dashboard UI in the Mythological Punk theme, committed as app/dist/index.html.
- README with run, configuration and launchd/systemd supervision instructions.
- Plan header marked implemented; paid Firecrawl check still open.
- AGENTS.md with project names, commands, invariants and gotchas.
