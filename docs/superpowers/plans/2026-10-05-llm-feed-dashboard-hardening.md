# LLM Feed Dashboard — Reliability Hardening and Optimization Backlog

Date: 2026-10-05 · Status: H1-H6 complete and approved through G1-G4; H7 (docs) ready for review; H8 open

**Completed:** H1 (shape validators), H2 (byte caps, malformed-payload containment), H3
(durable paid-attempt accounting), H4 (writer-lock decision, G2), H5 (single-writer flock plus
empty-catalog/state factory fix, G3), H6 (live paid acceptance, G4). Each was reviewed and
approved by a separate Opus context through gates G1-G4.

**H6 evidence (2026-10-06T04:02:30Z):** one isolated pull into a tmp directory outside the
repo, using the owner's 1Password key via `op read` straight into the process environment
(never written to a file). Exactly 2 credits, one per paid source; `attempts.json` holds two
records, both stamped `2026-10-06T04:02:30Z`. 5 of 6 sources ok; 36 items, 1388 tombstones,
`state.json` 100,038 bytes. All three JSON files pass H1's validators. Secret scans clean
(live key `grep -F`'d against every file, plus pattern scan). The sixth source,
hermes-agent-releases, parsed 0 items because every current entry was a prerelease removed
by `SKIP_PRERELEASE`; fetch and parser are fine. That is H8, not a parser defect.

**Deferred:** the optimization backlog below; H8 is a small P2 fix, not a release blocker.

## Why this exists

The initial dashboard implementation passed 51 offline tests (130 after hardening), but adversarial review
identified four gaps that make its operational guarantees weaker than its design:

1. a process death after a paid scrape can cause another paid scrape on restart;
2. the scheduler and documented manual CLI can write the same state concurrently;
3. syntactically valid but structurally bad state crashes later with an unhelpful error;
4. malformed response encodings can abort a whole pull rather than stale one source.

This plan closes those gaps without changing the product scope: one stdlib-only Python
process, two Firecrawl scrapes at most per UTC day, no key in persistent state, and
the existing data retention rules. It separately records sensible optimizations that
are not required for safe unattended use.

## Product contract after hardening

- Each paid source is attempted no more than once per UTC day, including across a
  crash, supervisor restart, or a manual pull made while the server is running.
- A process may continue to refresh free feeds when paid-source attempts are deferred.
- No source response or persisted data file can turn malformed input into an overwrite
  of known-good state; failures identify the affected file or source.
- One data directory has one active writer. A second writer does no fetches or writes
  and returns a clear, actionable result.
- The dashboard remains able to read only `items.json`; it never receives Firecrawl
  secrets, paid-attempt records, or tombstones.

## Delivery method

Use small tracer-bullet tickets. Each ticket has one owner, one narrow outcome, named
tests, and a green full-suite requirement. A low-cost implementation model is suitable
for every ticket except the lock-design spike; it should receive the ticket verbatim,
the named existing tests, and no authority to run Firecrawl or edit `.env` files.

Every completed implementation ticket is reviewed by a separate higher-reasoning model
before it is considered done. That reviewer does not implement, self-approve, run paid
calls, or rely on the author's summary: it inspects the actual diff, the relevant
existing code, focused/full test evidence, and the ticket's acceptance criteria. It
returns one of **approve**, **changes required**, or **escalate to owner**. “Approve”
means the ticket may unblock its dependents; it is not permission to alter scope or to
spend Firecrawl credits.

**Definition of ready:** the ticket's blockers are complete, its acceptance criteria
are unambiguous, and the assigned agent can work entirely offline.

**Reviewer handoff:** include the ticket text, base and head commit IDs, changed-file
list, focused-test output, full-suite output, and any known limitation. The reviewer
must explicitly check: no secret is persisted or logged; the stdlib-only runtime and
localhost-only serving boundary remain intact; the change cannot cause a paid retry;
and the tests prove external behavior rather than only mocked internals.

**Approval gates:**

| Gate | Reviewer focus | Blocks | Cannot approve |
| --- | --- | --- | --- |
| G1 | H1/H2 error containment and backwards compatibility | H3 and H4 | Live Firecrawl use or schema-scope expansion |
| G2 | H4 lock decision: crash, contention, and host-support semantics | H5 | A lock design with undocumented platform limits |
| G3 | H3/H5 combined state machine, spend cap, and writer serialization | H6 | Use of an API key or live paid validation |
| G4 | H6 evidence, parser behavior, and release-doc accuracy | H7/release recommendation | Replacing panda-master approval for release or paid spend |

Any `changes required` result returns to the owning ticket as a new checklist item.
Any `escalate to owner` result pauses only the affected dependency path; unrelated
frontier tickets may continue.

**Definition of done:** focused tests plus `.venv/bin/python -m pytest -q` pass; the
required higher-reasoning review gate is approved; no runtime dependency or secret
persistence was added; `CHANGELOG.md` describes the user-visible/operational change;
the task is one commit using the repository's convention.

## Increment 1 — Fail safely on bad local or remote input

### H1 — Validate persisted catalog and state shapes

**Priority:** P0 · **Blocked by:** none · **Suitable model:** inexpensive

**Outcome:** A valid JSON file with an invalid dashboard shape is rejected as a
`StoreError` before a pull mutates state. The CLI names the offending file and exits
non-zero; the scheduler backs off without overwriting it.

**Scope:** Define minimal validators for the persisted catalog and state contracts.
Validate required top-level containers, item fields used by merge/prune/UI, source
statuses, ISO timestamps, and tombstone timestamp values. Preserve forward-compatible
unknown fields. Do not redesign the item schema or recover automatically.

**Acceptance criteria:**

- [ ] `{}`, an array, wrong container types, missing required item timestamps, and bad
  tombstone timestamps are each rejected before a write.
- [ ] Rejection leaves both original files byte-for-byte unchanged.
- [ ] A valid existing catalog/state round-trips through pull and prune unchanged except
  for intentional refresh fields.
- [ ] New tests cover both `items.json` and `state.json`, following the existing
  corrupt-file tests.

### H2 — Contain malformed source payloads to one stale source

**Priority:** P0 · **Blocked by:** none · **Suitable model:** inexpensive

**Outcome:** Invalid UTF-8, JSON payloads with unexpected shape, and oversized source
responses are reported as a failure for only that source; they do not crash the whole
scheduler step or replace old source items.

**Scope:** Give every HTTP reader a documented finite byte limit appropriate to an XML
feed or one scraped markdown page. Normalize decoding/payload failures to the existing
safe `FetchError` path. Keep Firecrawl headers and errors free of the API key.

**Acceptance criteria:**

- [ ] Invalid bytes from one free feed leave that source stale while the other five
  sources still merge.
- [ ] Invalid bytes and malformed success payloads from Firecrawl raise a safe error
  that contains neither the key nor request headers.
- [ ] An over-limit body is rejected before unbounded memory allocation.
- [ ] Existing request shape, no-retry policy, and offline test behavior remain intact.

## Increment 2 — Make paid refresh attempts crash-safe

### H3 — Add durable per-source paid-attempt accounting

**Priority:** P0 · **Blocked by:** G1 · **Suitable model:** Sonnet 5.5 with a reviewed
prompt

**Outcome:** A paid source is never charged twice on the same UTC day because of a
crash or supervisor restart. Free sources remain refreshable even when a paid source
has already consumed its daily attempt.

**Design contract:** Immediately before calling Firecrawl for source `S`, atomically
record an opaque record for `S` in private state containing the current UTC date and
attempt time. Treat the record as consumption whether the request later succeeds,
fails, or the process dies. A same-day later pull skips only `S`, preserving its old
items and setting an explainable stale/deferred status. Prune old attempt records with
state maintenance. This is deliberately a maximum-spend guarantee, not a retry system.

**Acceptance criteria:**

- [ ] Simulated termination after recording an Anthropic attempt but before its request
  results in no Anthropic request after restart that UTC day.
- [ ] A crash after the first paid request still permits the never-attempted paid source
  to make its one allowed request.
- [ ] Repeated CLI pulls and scheduler restarts cannot exceed two paid source calls in
  one UTC day.
- [ ] The daily boundary permits a new attempt on the next UTC day.
- [ ] Attempt records never reach `items.json`, server responses, logs, or UI data.

## Increment 3 — Serialize state writers

### H4 — Resolve and prototype a portable writer-lock strategy

**Priority:** P0 · **Blocked by:** G1 · **Suitable model:** Opus 5

**Outcome:** A short, tested decision selects a lock that works for the project's
supported macOS/Linux launchd/systemd deployments, including process death and a
second CLI invocation. No production behavior changes in this task.

**Decision questions:** Is POSIX advisory locking sufficient for the documented host
set? If not, what stale-lock ownership/expiry rule avoids both permanent lockout and
two writers after a long pull? How will the lock cover state read, paid-attempt record,
fetch/merge, and both durable writes without holding it across an unbounded network
operation if that would harm availability?

**Acceptance criteria:**

- [ ] Decision note compares at least two stdlib-only approaches and records the chosen
  host support and failure semantics.
- [ ] A disposable prototype demonstrates contention and process-death behavior without
  touching repository `data/`.
- [ ] The selected contract gives a deterministic response to a second writer.

### H5 — Enforce the selected single-writer contract

**Priority:** P0 · **Blocked by:** H3 and G2 · **Suitable model:** Sonnet 5.5

**Outcome:** The scheduled pull and manual commands cannot race each other or overwrite
each other's temporary files/state.

**Acceptance criteria:**

- [ ] A contending CLI/server invocation fetches nothing, writes nothing, and reports
  that another writer owns the data directory.
- [ ] A writer interrupted at each critical persistence point leaves a valid, recoverable
  catalog/state pair under the H4 contract.
- [ ] The lock does not expose `state.json` or alter the localhost-only server boundary.
- [ ] Tests exercise real separate processes where feasible, not only mocked locks.

## Increment 4 — Operational proof and release gate

### H6 — Run the owner-only live paid acceptance check

**Priority:** P0 · **Blocked by:** G3 · **Suitable model:** owner only

**Outcome:** The current Firecrawl endpoint and both parsers are verified against live
responses without storing the key or raw response in the repository.

**Acceptance criteria:**

- [ ] Panda master runs one isolated pull with their own environment-provided key.
- [ ] At most two credits are consumed; all sources are successful or each failure
  has its current markdown evidence captured outside the repository for diagnosis.
- [ ] The resulting catalog has Anthropic and Nous entries meeting the current schema;
  its `state.json` contains no secret.
- [ ] If a parser needs revision, create a new bounded ticket with a sanitized fixture;
  do not change it opportunistically during the live check.

### H7 — Document hardened behavior and close the release increment

**Priority:** P1 · **Blocked by:** G4 · **Suitable model:** Sonnet 5.5

**Outcome:** Operators know the paid-attempt, contention, and corrupt-state behavior;
the design/implementation-plan status accurately distinguishes completed hardening
from deferred optimization.

**Acceptance criteria:**

- [ ] README explains no more than one paid attempt per source per UTC day and the
  command/result when a writer is already active.
- [ ] Design success criteria and known risks reflect verified, not assumed, live status.
- [ ] The full suite passes and release notes identify the hardening increment.

### H8 — Distinguish "all entries filtered" from "fetch or parse failed" — DROPPED

**Status:** dropped 2026-10-06 by panda master, not implemented. H8 existed only because
`hermes-agent-releases` showed a permanent, misleading stale banner: its entire release
window is pipeline noise, `SKIP_PRERELEASE` removed every entry, and `parsed 0 items` was
then reported as a failure. The source was removed from `SOURCES` instead, as it was not a
must-have. With no source in that state, the banner is gone and the ticket has no subject.

`SKIP_PRERELEASE` remains in `feed/pull.py` and still applies to every Atom release feed,
so the underlying conflation of "all entries filtered" with "fetch or parse failed" is
still latent. If a future Atom source ever publishes nothing but prereleases, it will show
the same false stale marker, and this ticket is the fix to revive: count entries before
filtering, treat parsed > 0 with kept == 0 as success-with-zero-items, and keep parsed == 0
as a real failure so a genuine parser breakage still fails loudly.

## Dependency map and Agile cadence

```text
Sprint 1:  H1 ─┐
           H2 ─┴─> G1 ─┬─> Sprint 2: H3 ─┐
                        └> H4 ─> G2 ─────┼─> Sprint 3: H5 ─> G3 ─> Sprint 4: H6 ─> G4 ─> H7
```

Sprint 1 tasks may run in parallel. H4 is intentionally a small discovery spike,
not an invitation to a broad refactor. After every sprint: run the full offline suite,
have the high-reasoning reviewer inspect the changed diff and acceptance evidence,
record its decision, update the plan status, and re-plan the next frontier. Do not
begin a blocked ticket early.

The copy-paste orchestration prompt, agent handoffs, and review record template live in
`docs/superpowers/plans/2026-10-05-llm-feed-dashboard-agent-handoff.md`.

## Deferred optimization backlog

These are useful, but they do not gate the hardening release and should be individually
approved before entering a sprint.

| Priority | Optimization | Value | Guardrail |
| --- | --- | --- | --- |
| P2 | Remove unused frontend dependencies and lockfile entries | Reduces install time, audit noise, and dev supply-chain surface | Rebuild the committed single-file UI and verify no UI regression |
| P2 | Add source-age stale state and friendly source labels | Makes an inactive scheduler/old successful pull visible to users | Do not add a polling service or expose private state |
| P2 | Add UI contract tests for new badges, stale rendering, and malformed catalog responses | Covers user-visible behavior absent from Python-only tests | Keep test tooling dev-only |
| P2 | Add restrictive response headers/CSP | Limits future browser-side rendering mistakes | Preserve the inline committed bundle or explicitly account for its CSP needs |
| P3 | Add a parsing-health fixture refresh workflow | Makes scraper-layout drift easier to diagnose | Never automate a paid Firecrawl call or commit credentials/raw sensitive output |

## Explicitly out of scope

No database, Docker, hosted scheduler, Firecrawl retry loop, additional data sources,
authentication, background browser polling, JSON-extract by default, or runtime
dependency is authorized by this plan. A live Firecrawl check remains owner-controlled.
