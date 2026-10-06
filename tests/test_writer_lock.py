# ABOUTME: Tests the single-writer lock on DATA_DIR/.writer.lock using real separate OS processes.
# ABOUTME: Covers refusal, kernel release on death, interruption recovery and the prune-vs-pull race.
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import feed.pull as pull_module
import feed.store as store
from feed.pull import run_prune, run_pull
from feed.schedule import BACKOFF_SECONDS, TICK_SECONDS, step
from feed.store import StoreError, read_json
from tests.test_paid_attempts import NOW, PaidFetcher, pull
from tests.test_pull import feeds

ROOT = Path(__file__).resolve().parent.parent
SLOT = NOW.time()

# A holder written against the raw contract (path + flock), not our helper, so these tests
# fail on code that never takes the lock. It prints the path it locked, then waits on stdin.
HOLDER = """
import fcntl, os, sys
fd = os.open(os.path.join(sys.argv[1], ".writer.lock"), os.O_CREAT | os.O_RDWR, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
print(os.path.realpath(os.path.join(sys.argv[1], ".writer.lock")), flush=True)
sys.stdin.read()
"""

# Runs the real CLI entry point with the network replaced by a recorder that always fails,
# so a writer that wrongly proceeds is visible (fetch log, rc 1) without touching the internet.
CLI = """
import sys, urllib.error, urllib.request
log = sys.argv[1]
def no_network(request, timeout=None):
    open(log, "a").write(request.full_url + "\\n")
    raise urllib.error.URLError("offline test")
urllib.request.urlopen = no_network
from feed.__main__ import main
sys.exit(main(sys.argv[2:]))
"""

# A pull that dies by SIGKILL just before the Nth os.replace, i.e. at one persistence point.
DYING_PULL = """
import os, signal, sys
from pathlib import Path
import feed.store as store
from feed.pull import run_pull
from tests.test_paid_attempts import NOW, PaidFetcher
from tests.test_pull import feeds
die_at, replaces = int(sys.argv[2]), [0]
real_replace = os.replace
def replace(src, dst):
    replaces[0] += 1
    if replaces[0] == die_at:
        os.kill(os.getpid(), signal.SIGKILL)
    real_replace(src, dst)
store.os.replace = replace
run_pull(Path(sys.argv[1]), NOW, feeds(), PaidFetcher())
"""


def python(script, *args, **kwargs):
    return subprocess.run([sys.executable, "-c", script, *map(str, args)], cwd=ROOT,
                          capture_output=True, text=True, timeout=60, **kwargs)


class Holder:
    """A real second process holding the data directory's writer lock."""

    def __init__(self, data_dir):
        self.proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(data_dir)], cwd=ROOT,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.lock_path = self.proc.stdout.readline().strip()
        assert self.lock_path, "holder never acquired the lock"

    def release(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)

    def kill(self):
        self.proc.kill()
        self.proc.wait(timeout=10)


@pytest.fixture
def holder(tmp_path):
    held = Holder(tmp_path)
    yield held
    if held.proc.poll() is None:
        held.kill()


def snapshot(tmp_path):
    return {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.name != ".writer.lock"}


def seed(tmp_path):
    """Valid files from a clean pull, so refusal can be checked byte for byte."""
    pull(tmp_path, PaidFetcher())
    return snapshot(tmp_path)


@pytest.mark.parametrize("command", ["pull", "prune"])
def test_a_second_cli_writer_is_refused_with_exit_3_and_changes_nothing(tmp_path, command):
    before = seed(tmp_path)
    fetch_log = tmp_path.parent / f"{tmp_path.name}-fetches-{command}.log"
    held = Holder(tmp_path)
    try:
        result = python(CLI, fetch_log, "--data", tmp_path, command)
    finally:
        held.kill()
    assert result.returncode == 3  # not 2 (StoreError) and not 1 (all sources failed)
    assert result.stderr.strip() == (
        f"error: another writer owns {tmp_path}; nothing was fetched or written")
    assert not fetch_log.exists()
    assert snapshot(tmp_path) == before  # byte for byte, no leftover .tmp either


def test_contenders_and_holder_agree_on_one_lock_path(tmp_path, holder):
    assert holder.lock_path == os.path.realpath(tmp_path / ".writer.lock")
    assert [p.name for p in tmp_path.iterdir()] == [".writer.lock"]  # no second lock file made
    with pytest.raises(store.WriterBusy):  # refused because it resolved the SAME file
        with store.writer_lock(tmp_path):
            pass
    assert (tmp_path / ".writer.lock").stat().st_mode & 0o777 == 0o600


def test_a_killed_holder_never_locks_the_directory_out(tmp_path, holder):
    holder.kill()  # SIGKILL: no cleanup code runs, the kernel must release the lock
    fetch_log = tmp_path.parent / f"{tmp_path.name}-fetches-after-kill.log"
    result = python(CLI, fetch_log, "--data", tmp_path, "prune")
    assert result.returncode == 0, result.stderr


def test_a_released_lock_can_be_taken_again_with_no_waiting(tmp_path, holder):
    holder.release()
    with store.writer_lock(tmp_path):
        pass
    with store.writer_lock(tmp_path):
        pass


def test_two_writers_in_one_process_exclude_each_other_because_each_opens_its_own_fd(tmp_path):
    with store.writer_lock(tmp_path):
        with pytest.raises(store.WriterBusy):
            with store.writer_lock(tmp_path):
                pass
        with pytest.raises(store.WriterBusy):
            run_prune(tmp_path, NOW)
    run_prune(tmp_path, NOW)  # and the first lock was untouched by the refusals' closes


def test_writer_busy_is_not_a_store_error_so_it_cannot_exit_2():
    assert issubclass(store.WriterBusy, Exception)
    assert not issubclass(store.WriterBusy, StoreError)


def test_a_refused_scheduler_step_ticks_normally_fetches_nothing_and_keeps_last_pull(
        tmp_path, caplog):
    before = seed(tmp_path)
    old_last_pull = read_json(tmp_path / "state.json", {})["lastPull"]
    fetcher = PaidFetcher()
    held = Holder(tmp_path)
    try:
        with caplog.at_level(logging.INFO, logger="feed"):
            wait = step(tmp_path, NOW.replace(day=7), SLOT,  # due: last pull was two days ago
                        lambda d, n: run_pull(d, n, feeds(), fetcher))
    finally:
        held.kill()
    assert wait == TICK_SECONDS != BACKOFF_SECONDS
    assert fetcher.calls == []
    assert snapshot(tmp_path) == before
    assert read_json(tmp_path / "state.json", {})["lastPull"] == old_last_pull
    refusals = [r for r in caplog.records if "another writer owns" in r.getMessage()]
    assert [r.levelno for r in refusals] == [logging.WARNING]
    assert refusals[0].getMessage() == (
        "another writer owns the data directory; skipping this pull")
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]  # no crash traceback


def test_step_returns_a_normal_tick_when_the_pull_itself_reports_a_busy_writer(tmp_path):
    def busy(directory, now):
        raise store.WriterBusy(str(directory))

    assert step(tmp_path, NOW, SLOT, busy) == TICK_SECONDS


def test_pulls_on_two_data_dirs_in_one_process_do_not_leak_state(tmp_path):
    first, third = tmp_path / "a", tmp_path / "c"
    run_pull(first, NOW, feeds(), None)  # records a status for every source
    run_prune(third, NOW)  # an empty directory must produce an empty catalog
    assert read_json(third / "items.json", {})["sources"] == {}
    assert read_json(third / "items.json", {})["items"] == []
    assert read_json(third / "state.json", {})["tombstones"] == {}


def test_a_failing_source_in_one_data_dir_does_not_inherit_another_dirs_success(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    run_pull(first, NOW, feeds(), None)
    broken = feeds()

    def fail_openai(url):
        if "openai.com" in url:
            raise OSError("down")
        return broken(url)

    run_pull(second, NOW, fail_openai, None)
    status = read_json(second / "items.json", {})["sources"]["openai-news"]
    assert status == {"lastOk": None, "lastError": "down"}  # not first dir's lastOk


def test_prune_cannot_erase_an_attempt_record_a_racing_pull_just_wrote(tmp_path, monkeypatch):
    old = {"date": "2026-10-04", "at": "2026-10-04T12:00:00Z"}  # makes prune rewrite the file
    (tmp_path / "attempts.json").write_text(json.dumps({"attempts": {"stale": old}}))
    fetcher, raced = PaidFetcher(), []
    real_prune = pull_module.prune

    def prune_while_a_pull_races(*args):
        try:  # the racing pull arrives after prune snapshotted attempts, before it writes back
            run_pull(tmp_path, NOW, feeds(), fetcher)
        except store.WriterBusy:
            raced.append("refused")
        return real_prune(*args)

    monkeypatch.setattr(pull_module, "prune", prune_while_a_pull_races)
    run_prune(tmp_path, NOW)
    assert raced == ["refused"]
    assert fetcher.calls == []  # no paid call was licensed by an erased record
    records = json.loads((tmp_path / "attempts.json").read_text())["attempts"]
    assert "stale" not in records


def count_persistence_points(tmp_path):
    seen = []
    real = store.os.replace
    store.os.replace = lambda src, dst: (seen.append(Path(dst).name), real(src, dst))[1]
    try:
        pull(tmp_path, PaidFetcher())
    finally:
        store.os.replace = real
    return seen


def test_the_persistence_points_of_a_pull_are_attempts_attempts_items_state(tmp_path):
    assert count_persistence_points(tmp_path) == [
        "attempts.json", "attempts.json", "items.json", "state.json"]


@pytest.mark.parametrize("die_at", [1, 2, 3, 4])
@pytest.mark.parametrize("prior", [False, True])
def test_sigkill_at_each_persistence_point_leaves_a_valid_recoverable_pair(
        tmp_path, die_at, prior):
    if prior:
        seed(tmp_path)
        (tmp_path / "attempts.json").unlink()  # yesterday's pull: a fresh day of attempts
        (tmp_path / "state.json").write_text(
            (tmp_path / "state.json").read_text().replace("2026-10-05", "2026-10-04"))
    result = python(DYING_PULL, tmp_path, die_at)
    assert result.returncode == -signal.SIGKILL, result.stderr
    for name, validate in (("items.json", store.validate_catalog),
                           ("state.json", store.validate_state),
                           ("attempts.json", store.validate_attempts)):
        if (tmp_path / name).exists():
            read_json(tmp_path / name, {}, validate)  # every file present parses and validates
    lock = os.open(tmp_path / ".writer.lock", os.O_RDWR)  # created by the dead writer...
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # ...and free: no stale lock
    os.close(lock)
    fetcher = PaidFetcher()
    summary = pull(tmp_path, fetcher)  # recovery is just running the next pull
    assert summary["failed"] == {}
    read_json(tmp_path / "items.json", {}, store.validate_catalog)
    read_json(tmp_path / "state.json", {}, store.validate_state)
    paid_before_death = {1: 0, 2: 1, 3: 2, 4: 2}[die_at]  # attempts recorded before the kill
    assert len(fetcher.calls) == 2 - paid_before_death  # a recorded attempt is never re-spent
