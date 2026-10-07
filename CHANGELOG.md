# Changelog

## Unreleased

- Dropped the hermes-agent release feed: its whole release window is pipeline noise, so the
  prerelease filter left it with nothing to publish and it reported a permanent false stale
  marker. Five sources remain (three free feeds, two paid scrapes); the prerelease filter still
  guards every Atom release feed. Ticket H8, which existed to fix the false marker, is dropped.
- **Hardening increment (H1-H7), live-verified 2026-10-06.** Operational guarantees now hold under bad input, crashes and contention: state files are shape-validated (a wrong-shape file is refused, exit 2), every HTTP reader has a byte cap (16 MiB per XML feed, 8 MiB per scraped page), each paid source is requested at most once per UTC day (`data/attempts.json`), and one writer per data directory is enforced by a `flock` (a second writer exits 3). A live paid pull on 2026-10-06 used exactly 2 credits, 5 of 6 sources ok, and confirmed both scrapers (anthropic-news 3 dated items, nous-blog 5 undated) and the Firecrawl v2 endpoint. hermes-agent-releases showed as stale only because all its current releases are prereleases. Suite: 130 tests. README, design spec and plans updated; `DATA_DIR` must be a local filesystem.

- `pull` and `prune` now run as the data directory's only writer: each takes a non-blocking `flock` on `DATA_DIR/.writer.lock` for its whole read-modify-write, so the scheduler, the CLI and a prune can no longer race on items/state/attempts or each other's temp files. A second writer fetches and writes nothing: the CLI prints `another writer owns <dir>` and exits 3, the scheduler logs a warning and keeps its normal one-minute tick without touching `lastPull`. The kernel frees the lock when a writer dies, so there is no stale lock to clear. Also fixed: a pull or prune on an empty data directory no longer shares (and leaks status into) a module-level empty catalog between runs.
- Each paid Firecrawl source (Anthropic news, Nous blog) is requested at most once per UTC day, even across a crash, CLI re-run or supervisor restart: the attempt is saved to data/attempts.json before the request and counts whether the request succeeds, fails or the process dies. A second pull that day defers just that source (shown stale, old items kept) while free feeds keep refreshing; a corrupt attempts file is refused rather than trusted. Old records are pruned with state maintenance.
- Recorded the writer-lock decision for one active writer per data directory: a non-blocking `fcntl.flock` on `DATA_DIR/.writer.lock` held for the whole write transaction, released by the kernel on process death so no stale-lock expiry is needed; a second writer fetches and writes nothing (CLI exits 3, the scheduler skips its turn). Local filesystems on macOS/launchd and Linux/systemd only. Decision and prototype evidence: `docs/superpowers/plans/2026-10-05-writer-lock-decision.md`. No behavior change yet.
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
