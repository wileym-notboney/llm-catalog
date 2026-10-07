# Writer-lock decision — one active writer per data directory

Date: 2026-10-05 · Status: decided; G2 corrections applied, ready for re-review · Ticket: H4

This closes the decision questions in H4 of
`docs/superpowers/plans/2026-10-05-llm-feed-dashboard-hardening.md`. It changes no
production behavior. H5 implements the contract recorded in **The contract H5 implements**
below; nothing here authorizes widening its scope.

**Owner rulings, 2026-10-05.** The G2 reviewer found no blocking defect and escalated two
questions. The owner ratified **exit code 3** for "another writer owns the data directory"
(1 and 2 are taken by `feed/__main__.py:42` and `:38`, and a corrupt file and a busy
writer need different operator actions, so they must not share a code); and **accepted the
unexecuted-Linux limit as documented**, so H5 proceeds on the specification argument plus
the errno caveat below. Both are recorded here so neither is re-litigated.

## Decision

**Use `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on `DATA_DIR/.writer.lock`, held for the whole
write transaction, with no expiry rule and no stale-lock recovery.** A writer that cannot
take the lock does nothing and says so.

POSIX advisory locking _is_ sufficient for the documented host set, but only the `flock`
flavor of it. The kernel releases the lock when the holding process dies, so there is
nothing to expire; that is why the "permanent lockout vs. two writers after a long pull"
trade-off the ticket asks about does not arise here. The prototype below demonstrates the
kernel release rather than assuming it, because G2 cannot approve a lock with undocumented
platform limits.

## Who the writers actually are

Traced in the code, not assumed:

- `feed/pull.py:run_pull` reads `items.json` and `state.json`, fetches five sources, merges,
  prunes, then writes both files through `feed/store.py:write_json` (temp file +
  `os.replace`).
- `feed/pull.py:run_prune` reads and writes the same two files, offline.
- `serve.py:main` starts `scheduler_loop` as a **daemon thread in the server process**;
  that thread calls `run_pull` through `feed/schedule.py:step`.
- `python3 -m feed pull|prune` is a documented operator command (README, AGENTS.md) and may
  be run while the server is up. This is the contention case the plan cares about.
- H3 adds a third persisted file, `data/attempts.json`, written the same way. Its
  paid-attempt record is the most spend-sensitive write in the system, so the lock must
  cover it; the contract below places it inside the critical section by construction.

Readers are not writers and are not affected. `serve.py`'s `DashboardHandler` only maps
`/items.json` onto `data_dir / "items.json"` in `translate_path` and otherwise serves
`app/dist`; it inherits `SimpleHTTPRequestHandler`, so it answers `GET`/`HEAD` only and
never writes. Combined with `write_json`'s `os.replace`, a reader sees either the old
complete file or the new complete file. **The HTTP server is therefore never blocked by a
writer, which is what makes holding the lock across the network phase acceptable.**

## Alternatives compared (stdlib only)

|                                      | A. `fcntl.flock` on a lock file         | B. `O_CREAT\|O_EXCL` pid/timestamp lockfile                     | C. `fcntl.lockf` / POSIX record locks |
| ------------------------------------ | --------------------------------------- | --------------------------------------------------------------- | ------------------------------------- |
| Released on process death            | Yes, by the kernel                      | **No** — file outlives the process                              | Yes, by the kernel                    |
| Needs an expiry rule                 | No                                      | **Yes**, and it must be longer than the slowest legitimate pull | No                                    |
| Second writer in the same process    | **Refused** (per open-file-description) | Refused                                                         | **Granted** (per process)             |
| Closing one fd while another is open | Lock survives                           | n/a                                                             | **Lock dropped**                      |
| Code                                 | ~6 lines                                | ~40 lines plus an expiry policy nobody can tune correctly       | ~6 lines                              |

**B is rejected on the evidence of case 5 below:** after the holder is `SIGKILL`ed its
lockfile remains and every later writer is refused forever. Fixing that needs an expiry,
and an expiry cannot be chosen safely here, because **a legitimate pull has no time bound
at all**.

The nominal worst case is 5 minutes: `feed/pull.py:32-45` has exactly two Firecrawl
sources at a 90s timeout (`feed/scrape_pages.py:36`) and four XML feeds at 30s
(`feed/pull.py:54`), so `2*90 + 4*30 = 300s`. But that figure is the floor of the problem,
not the ceiling. The `timeout` handed to `urlopen` does bound the TCP connect; what it
does not bound is *total elapsed time*, because a socket timeout applies per blocking
operation rather than to the whole transfer. `read_capped` (`feed/scrape_pages.py:24-32`)
issues one `response.read(limit + 1)`, and `http.client` satisfies that with repeated
`recv` calls, each of which gets a fresh 30s/90s window. A server trickling one byte at a
time therefore holds a source open indefinitely. **The real bound on a pull is the byte
cap, not the clock** — `MAX_XML_BYTES` (16 MiB) and `MAX_PAGE_BYTES` (8 MiB) from H2, and
at a trickle those take as long as the sender likes.

So no expiry can be correct: there is no duration D such that a pull still running at D is
certainly dead. An expiry shorter than a slow pull produces two writers mid-pull — the
exact outcome H5 exists to prevent, and the one that can double-charge a credit. A
generous one (say 15 minutes) means a crash during the daily pull silently disables
refresh until an operator notices. Both failure modes are worse than the problem. A
kernel-released lock sidesteps the question entirely: it is released exactly when the
holder stops existing, which is the only correct predicate.

**C is rejected on the evidence of case 6 below.** POSIX record locks are owned per
_process_, so a second acquisition inside `serve.py` — exactly the scheduler-thread
case — is granted, and the lock gives no protection where we most need a deterministic
answer. Worse, closing _any_ descriptor on the file drops the process's lock, so an
unrelated `read_json` on the lock path would silently unlock a pull in flight. `flock`
ownership is per open-file-description, so each writer opening its own fd gets a correct
answer even inside one process (case 4).

## Host support and failure semantics

**Supported:** macOS under launchd and Linux under systemd — the two deployments documented
in README "Keep it running" — with `DATA_DIR` on a **local** filesystem (APFS, ext4, xfs,
btrfs). `fcntl.flock` is in the stdlib on both and adds no dependency.

| Event                                                               | Semantics                                                                                                                                          |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Holder exits normally                                               | Lock released when the fd closes (or at process exit).                                                                                             |
| Holder is `SIGKILL`ed, panics, or is `launchctl`/`systemctl` killed | Kernel closes all fds and releases the lock. The next writer acquires immediately. Case 2, and the G2 reviewer's independent runs under uncaught exception, `os._exit` and parent death. |
| Holder spawns a subprocess that inherits the lock fd | The lock survives the holder's own death until the child exits too. **Latent, not live**: no writer here spawns a subprocess, and `subprocess.Popen` defaults to `close_fds=True`. Recorded for whoever adds one. |
| Host loses power | No lock state survives a reboot: the lock lives in the kernel, not in the file. The lock file itself is an empty 0-byte artifact, mode 0600, and is not state — nothing in it can go stale and nothing in it can leak. |
| Holder runs for minutes                                             | Contenders keep getting a clean refusal for as long as the holder lives, with no expiry to misfire. Case 3.                                        |
| Two writers in one process                                          | Refused, because each writer opens its own fd. Case 4.                                                                                             |
| Lock file deleted under a running holder                            | A new writer creates a fresh inode and acquires it: **two writers**. Out of the supported set; `data/` is not an operator work area.               |

**Network filesystems are out of the supported set.** NFS, SMB and sshfs are explicitly not
supported for `DATA_DIR`. If someone uses one anyway: macOS `flock` over NFS is advisory on
the local client only, and Linux `flock` on NFS is either `ENOTSUP` or emulated by the
client, so two _hosts_ sharing one `DATA_DIR` over NFS can both believe they hold the lock
and both write. Within a single host it still serializes correctly, which is the deployment
we document. This is a real limit and is recorded as such rather than guarded against:
detecting the filesystem reliably is more code than the supported deployment justifies, and
H5's scope is serialization, not storage validation. **H7 must carry "`DATA_DIR` must be
on a local filesystem" into the README as its own acceptance criterion** — right now that
requirement lives only in this note, and a deferral with no home is a dropped
requirement.

## The contract H5 implements

Acquire once, at the top of each write entry point, and hold it for the whole transaction:

```
acquire DATA_DIR/.writer.lock (O_CREAT|O_RDWR, mode 0600; LOCK_EX|LOCK_NB)
  read items.json, state.json           (and attempts.json, per H3)
  record the paid attempt               (H3 — inside the lock, before any paid call)
  fetch and merge
  write items.json                      (temp + os.replace)
  write state.json                      (temp + os.replace)
release (close the fd)
```

The lock spans the network phase deliberately. The availability argument for releasing it
around the fetch does not apply, because readers are never blocked (see "Who the writers
actually are"), and there is one legitimate writer per day. Releasing and re-acquiring
would reopen a lost-update window between the state read and the write, and would split
H3's record-then-call sequence across an unlocked gap — the one window where a crash can
cost a credit twice.

Holding the lock across both writes is also what satisfies H5's "cannot overwrite each
other's temporary files" criterion. `write_json` (`feed/store.py:91`) builds its temp path
as a fixed `path.name + ".tmp"`, so two concurrent writers would use the same
`items.json.tmp` and clobber each other between the write and the `os.replace`. Nothing in
`write_json` prevents that; the lock does.

One read is deliberately outside the critical section: `step()` reads `state.json` at
`feed/schedule.py:43` to decide whether a pull is due, before any acquire. That is benign
and H5 should leave it there — a stale "due" reading leads to a lock refusal, not a second
pull — but H5 must not mistake it for a protected read.

**A second writer gets a non-blocking refusal. No wait, no retry loop, no spin.**

- `python3 -m feed pull` / `prune`: fetches nothing, writes nothing, prints to stderr
  `error: another writer owns <data dir>; nothing was fetched or written` and **exits 3**.
  3 is free: `feed/__main__.py` already uses 1 for "every source failed" and 2 for
  `StoreError`.
- The scheduler thread in `serve.py`: `step()` treats the refusal as "not my turn", logs
  one line at WARNING (`another writer owns the data directory; skipping this pull`), and
  returns the normal `TICK_SECONDS` tick — not `BACKOFF_SECONDS`, because nothing crashed.
  It must **not** update `lastPull`; the writer that holds the lock sets it, after which
  `pull_due` is false and the scheduler goes quiet on its own. Because the lock is taken
  before any fetch and before H3's attempt record, a refused scheduler step costs zero
  credits and consumes no daily attempt.

Both paths see the same condition, so a distinct exception type (e.g. `store.WriterBusy`)
raised by the acquire helper and handled in `feed/__main__.py` and `feed/schedule.py` is
the whole change. **`WriterBusy` must not subclass `StoreError`, and its handler must come
before the existing `except StoreError` in `feed/__main__.py:36` and before the existing
`except Exception` in `feed/schedule.py:49`.** Both hazards are live: the acquire helper
naturally wants to live in `feed/store.py` next to `read_json`/`write_json`, and a
`WriterBusy(StoreError)` there would be caught by `feed/__main__.py:36` and exit **2**
instead of 3, silently contradicting this contract; the scheduler's blanket
`except Exception` would swallow it and return `BACKOFF_SECONDS` (3600s), which this
contract explicitly forbids. A corrupt file and a busy writer need different operator
actions, which is why they must not share an exit code.

H5 also absorbs the pre-existing `dict(EMPTY_CATALOG)` shallow-copy bug
(`feed/pull.py:88,120`) by the owner's decision of 2026-10-05; it is noted here only
because it sits inside the same read-modify-write transaction the lock now wraps. It is
not fixed by this ticket. The lock file lives in `DATA_DIR`, which `serve.py` exposes only as
`/items.json`, so it is not reachable over HTTP; it is created empty and never written to,
so there is nothing in it to leak.

## Prototype evidence

Disposable, run outside the repository on a temporary directory; the repository's `data/`
was never touched. Real separate OS processes, not mocks. Tested on **CPython 3.14.8**
(`.venv/bin/python -V`), **Darwin 27.0.0, arm64 (Darwin Kernel Version 27.0.0: Tue Aug 11
21:05:27 PDT 2026; root:xnu-13432.1.9~1/RELEASE_ARM64_T8103)**, APFS. The Linux/systemd
half of the host set is **not** covered by this run — see "Not ruled out".

The acquire helper under test, in full:

```python
class Busy(Exception):
    pass


def acquire(path=None):
    """Non-blocking exclusive lock. Returns an fd; raises Busy if another writer holds it."""
    fd = os.open(path or lock_path(), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:            # EWOULDBLOCK / EAGAIN
        os.close(fd)
        raise Busy(f"{type(error).__name__} errno={error.errno}") from None
    return fd
```

Each case forks a child process per role; a refused contender exits 3, the proposed CLI
code. Observed output, verbatim (child lines are flushed as they happen, so they appear
before the parent's buffered section headers):

```text
holder pid=39203 acquired
contender REFUSED: BlockingIOError errno=35
holder exiting cleanly
holder pid=39217 acquired
contender REFUSED: BlockingIOError errno=35
contender ACQUIRED
holder pid=39230 acquired
contender REFUSED: BlockingIOError errno=35
contender REFUSED: BlockingIOError errno=35
holder exiting cleanly
pid-holder pid=39443 created lockfile
pid-contender REFUSED: lockfile exists: '39443 1791257547.974873'
pid-contender REFUSED: lockfile exists: '39443 1791257547.974873'
python 3.14.8  dir=/var/folders/0k/004qhp892zj6p6_qr618stm40000gn/T/h4spike-9_xgavmt

--- case 1: two concurrent OS processes contend (holder busy 3s) ---
contender exit=3

--- case 2: holder SIGKILLed while holding; can a new writer acquire? ---
contender-before-kill exit=3
holder killed (rc=-9)
contender-after-kill exit=0

--- case 3: long hold (12s, longer than any expiry rule would be) ---
t+4s contender exit=3
t+8s contender exit=3

--- case 4: second acquire inside ONE process (the serve.py thread case) ---
main thread holds the lock; thread REFUSED: BlockingIOError errno=35
re-flock of the SAME fd by the holder: succeeds (flock is per-OFD, not re-entrancy-safe across code paths)

--- case 5: rejected alternative, O_EXCL pid lockfile, holder SIGKILLed ---
pid-contender-before-kill exit=3
pid-holder killed
pid-contender-after-kill exit=3  <-- permanent lockout without an expiry rule

--- case 6: fcntl.lockf (POSIX record lock) in ONE process, two fds ---
second lockf in the same process: ACQUIRED (record locks are per-process: no in-process protection)
after closing the second fd, is the lock still held by fd 3? NO - another process acquired it (the close dropped the lock)
```

What each case settles:

1. **Contention.** Exactly one writer wins; the loser gets `BlockingIOError` (errno 35,
   `EAGAIN`/`EWOULDBLOCK` on Darwin) and exits 3. Deterministic, immediate, no wait.
2. **Process death.** This is the load-bearing result. While the holder lives, the
   contender is refused; after `SIGKILL` (`rc=-9`, so no cleanup code ran) the next
   contender acquires at once. The kernel released it — **no expiry rule is needed**, which
   is what makes option B's trade-off avoidable rather than merely tolerable.

   The G2 reviewer rebuilt this spike from this note alone, reproduced every case above,
   and extended the death modes to four: uncaught exception (`rc=1`), **`os._exit` with no
   interpreter cleanup and no `atexit` (`rc=7`)**, and a parent dying while a child that
   inherited the fd still runs. All release, and the next writer acquires immediately. The
   `os._exit` case is the one that matters: it proves release-on-death is a kernel
   property and does not depend on any Python cleanup path, which is the actual
   load-bearing claim. The reviewer also confirmed the crashed holder leaves a 0-byte,
   mode-0600, empty lock file: an artifact, not state.
3. **Long hold.** A 12-second holder keeps refusing contenders at t+4s and t+8s with no
   expiry to misfire. The behavior is the same at 12 seconds, at 5 minutes and at an hour,
   because nothing in the design is time-based; there is no duration at which the refusal
   silently becomes an acquisition.
4. **Two writers in one process** — the `serve.py` scheduler-thread-vs-CLI shape, in its
   hardest in-process form. A second thread opening its own fd is refused. The second line
   is a caveat for H5: re-`flock`ing the _same_ fd succeeds, because ownership is per
   open-file-description. So each writer must do its own `os.open`, and the acquire must
   not be nested on a shared fd. It is not a re-entrant mutex.
5. **Rejected option B, demonstrated failing.** The `SIGKILL`ed holder's lockfile survives
   and every later writer is refused forever: permanent lockout, exactly the failure the
   ticket names.
6. **Rejected option C, demonstrated failing.** Both record-lock footguns reproduce: a
   second `lockf` in the same process is granted, and closing an unrelated fd on the same
   file drops the lock a running writer holds.

The first version of this prototype reported _both_ contenders acquiring in case 1. That
was a bug in the harness, not a finding: `acquire(path=LOCK)` bound the lock path as a
default argument at import time, and each child process had already created its own
`mkdtemp`, so every process locked a different file. Recorded because it is the kind of
mistake that makes a lock look like it works when it does not — H5's tests should assert
that the contending processes agree on one path. The G2 reviewer checked this specifically,
printing the resolved lock path from inside every child, and confirmed all children print
one identical path while still refusing: the fix is a real fix, not a test-passing one.

## Not ruled out (G2 should weigh these explicitly)

1. **Linux/systemd was not executed.** Every result above is from macOS/APFS on CPython
   3.14.8. `flock(2)` release-on-close is specified identically on Linux and the stdlib
   wrapper is the same call, so the conclusions are expected to hold; the errno differs
   (`EWOULDBLOCK` is 11 on Linux, 35 on Darwin), which is why H5 must catch `OSError` /
   `BlockingIOError` rather than compare an errno constant. If G2 wants the host set
   proven rather than argued, re-running this spike on a Linux host is cheap and offline.
   **The owner accepted this limit as documented on 2026-10-05**, so G2's prohibition on
   *undocumented* platform limits is not triggered and H5 is not blocked on it.
2. **Network filesystems**, as described above: a shared `DATA_DIR` over NFS/SMB can admit
   two writers on two hosts. Documented out of scope, not prevented in code.
3. **A deleted lock file under a running holder** admits a second writer. Not prevented;
   `data/` is not an operator work area.
4. **The lock serializes writers, not writer-vs-reader.** That is correct here only because
   `serve.py` never writes and `os.replace` is atomic. If anything later gives the server a
   write path, this decision must be revisited.
