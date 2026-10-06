# Changelog

## Unreleased

- Each paid Firecrawl source (Anthropic news, Nous blog) is requested at most once per UTC day, even across a crash, CLI re-run or supervisor restart: the attempt is saved to data/attempts.json before the request and counts whether the request succeeds, fails or the process dies. A second pull that day defers just that source (shown stale, old items kept) while free feeds keep refreshing; a corrupt attempts file is refused rather than trusted. Old records are pruned with state maintenance.
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
- Every HTTP reader caps its body (16 MiB per XML feed, 8 MiB per scraped page); an over-limit response stales only that source. A Firecrawl success payload of the wrong shape (list, string, non-string markdown) is now a safe FetchError instead of aborting the whole pull, and invalid UTF-8 from Firecrawl gets a normalized, key-free error message.
