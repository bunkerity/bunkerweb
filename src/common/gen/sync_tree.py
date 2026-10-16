#!/usr/bin/env python3

from contextlib import contextmanager, suppress
from fcntl import LOCK_EX, LOCK_NB, flock
from filecmp import cmp
from logging import Logger
from os import O_CLOEXEC, O_CREAT, O_RDONLY, close, fchmod, kill, open as os_open, replace
from pathlib import Path
from re import fullmatch, match
from shutil import rmtree
from time import monotonic, sleep
from typing import Callable, Iterator, Optional

# Entries of the destination root carrying this prefix belong to the instance push (staging, trash)
# and to the generator's own staging area. They are never part of a render, so they are never swept.
# Keep the prefix in step with pushswap.RESERVED_PREFIX.
RESERVED_PREFIX = ".bw-"

# Created by the reload handler of the API before it signals nginx, removed by the new workers once
# they are up (or by the init phase when it rejects the reload). A reader of the shared output must not
# see it change while the marker exists.
RELOADING_PATH = Path("/var/tmp/bunkerweb/reloading")
# Locked (flock) by the generator from the first file it installs until the last one is in place. The
# kernel drops the lock when the holder exits, however it exits, so nothing is ever stale. The reload
# handler probes it without holding it. The file itself is never removed. Keep the path in step with api.lua.
GENERATING_PATH = Path("/var/tmp/bunkerweb/generating")
# Pid file of the nginx master, the same path in every integration (nginx.conf)
NGINX_PID_PATH = Path("/var/run/bunkerweb/nginx.pid")
# Longest the generator waits for a reload in flight, or for another generator to finish.
WAIT_SECONDS = 30.0
POLL_SECONDS = 0.2
RELOAD_MARKER_MAX_AGE = 300


class InstallBlocked(Exception):
    """The install may not go ahead: exclusion against a reload or another generator could not be proven."""


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        rmtree(path.as_posix(), ignore_errors=True)


def same_file(first: Path, second: Path) -> bool:
    """True when both files have the same mode and the same content."""
    return first.stat().st_mode == second.stat().st_mode and cmp(first, second, shallow=False)


def sync_tree(source: Path, destination: Path, before_change: Optional[Callable[[], None]] = None) -> bool:
    """Make destination hold exactly what source holds, without ever emptying it first.

    A reader sharing the destination (nginx on all-in-one and Linux) must find every file it
    needs at every instant. Each file is swapped in with rename(2), so it is either the old
    content or the new one, and a file whose content did not change is not touched at all.
    Stale entries are only removed once every new one is in place. Source and destination must
    be on one filesystem.

    before_change runs once, ahead of the first modification. Returns whether anything changed.
    """
    changed = False

    def touch() -> None:
        nonlocal changed
        if not changed:
            changed = True
            destination.mkdir(parents=True, exist_ok=True)
            if before_change:
                before_change()

    def walk(src: Path, dst: Path, root: bool) -> None:
        if dst.is_symlink() or (dst.exists() and not dst.is_dir()):
            touch()
            _remove(dst)
        if not dst.exists():
            touch()
            dst.mkdir(parents=True)

        wanted = set()
        for entry in src.iterdir():
            wanted.add(entry.name)
            target = dst / entry.name
            if entry.is_dir() and not entry.is_symlink():
                walk(entry, target, False)
                continue
            if target.is_dir() and not target.is_symlink():
                touch()
                _remove(target)
            if entry.is_file() and not entry.is_symlink() and target.is_file() and not target.is_symlink() and same_file(entry, target):
                continue
            touch()
            replace(entry, target)

        for existing in dst.iterdir():
            if existing.name in wanted or (root and existing.name.startswith(RESERVED_PREFIX)):
                continue
            touch()
            _remove(existing)

    walk(source, destination, True)
    return changed


def pid_alive(pid: int) -> bool:
    """True unless the pid is gone; a pid we may not signal still counts as alive."""
    try:
        kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def nginx_master_running(pid_file: Path) -> bool:
    """False only when it is proven that no master runs: no pid file, or a pid that is gone."""
    try:
        text = pid_file.read_text().strip()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return not text.isdigit() or pid_alive(int(text))


def _open_lock(path: Path) -> int:
    # Opened without O_CREAT when the file is there: a file owned by another user in a sticky
    # directory refuses an open that could create it. Read-only is enough for flock.
    try:
        return os_open(path, O_RDONLY | O_CLOEXEC)
    except FileNotFoundError:
        fd = os_open(path, O_RDONLY | O_CREAT | O_CLOEXEC, 0o644)
        with suppress(OSError):
            # Whatever the umask, the reload handler (another user) has to be able to open it.
            fchmod(fd, 0o644)
        return fd


def _try_lock(fd: int) -> bool:
    try:
        flock(fd, LOCK_EX | LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _remove_orphaned_marker(path: Path, logger: Logger) -> bool:
    try:
        token = path.read_bytes()
        stamp = fullmatch(rb"[0-9]+\.[0-9]+\.([0-9]+)", token)
        uptime = match(rb"([0-9]+)\.[0-9]+\s", Path("/proc/uptime").read_bytes())
        if not stamp or not uptime or int(uptime[1]) - int(stamp[1]) <= RELOAD_MARKER_MAX_AGE:
            return False
        # ponytail: two removers and a fresh publisher can still race between this comparison and unlink.
        if path.read_bytes() != token:
            return False
        path.unlink()
    except (OSError, ValueError):
        return False
    logger.warning(f"Removing orphaned reload marker {path} older than 5 minutes")
    return True


@contextmanager
def install_guard(
    logger: Logger,
    reloading: Path = RELOADING_PATH,
    generating: Path = GENERATING_PATH,
    wait: float = WAIT_SECONDS,
    poll: float = POLL_SECONDS,
    nginx_pid: Path = NGINX_PID_PATH,
) -> Iterator[None]:
    """Keep the install out of every reload of the nginx that reads the output.

    A reload reads the routing (server blocks) and the variables at different moments, so files
    that change in between give it a mix of two generations: a service removed from the variables
    while its server block is still served runs on the global settings. The two sides therefore
    take turns. We take the generating lock first and only then look for a reload; the reload
    handler publishes its marker first and only then probes the lock. Whoever goes second sees the
    other one and backs off, so the two can never both go ahead. While a reload is in flight the
    lock is given back between looks, so the handler of another reload never waits on a generator
    that is itself waiting.

    A marker whose monotonic stamp is older than five minutes is treated as an orphan of a rejected reload and removed.
    Without that proof exclusion holds: when it cannot be proven within the
    wait (lock held by a live generator, lock file unusable, reload marker still there) the install
    does not happen and InstallBlocked is raised, leaving the destination as it is. The single
    proof that is not about time: a marker with no nginx master to stand for it is leftover.
    """
    fd = None
    deadline = monotonic() + wait
    try:
        while True:
            if fd is None:
                try:
                    fd = _open_lock(generating)
                except OSError as e:
                    raise InstallBlocked(
                        f"Can't open the generating lock {generating} ({e}), the current configuration is kept. Fix the permissions of that path, then generate again"
                    ) from e
            try:
                locked = _try_lock(fd)
            except OSError as e:
                raise InstallBlocked(
                    f"Can't lock {generating} ({e}), the current configuration is kept. Fix the permissions of that path, then generate again"
                ) from e
            if locked and not reloading.exists():
                break
            if locked:
                if _remove_orphaned_marker(reloading, logger):
                    continue
                if not nginx_master_running(nginx_pid):
                    logger.warning(f"{reloading} exists but no nginx master is running, so it stands for no reload: removing it")
                    try:
                        reloading.unlink(missing_ok=True)
                    except OSError as e:
                        raise InstallBlocked(
                            f"Can't remove {reloading} ({e}), the current configuration is kept. Remove it by hand, then generate again"
                        ) from e
                    break
                # Give the lock back between looks while the reload runs
                close(fd)
                fd = None
            if monotonic() >= deadline:
                if locked:
                    raise InstallBlocked(
                        f"{reloading} is still there after {wait:.0f}s: a reload is in flight, or the last one was rejected after its configuration was parsed. "
                        f"The current configuration is kept. Generate again once the reload is done; if none is running, a marker with a monotonic stamp is cleared automatically once it is older than 5 minutes. "
                        f"Restart BunkerWeb or remove {reloading} to clear it sooner, then generate again"
                    )
                raise InstallBlocked(
                    f"Another generator still holds {generating} after {wait:.0f}s, the current configuration is kept. Generate again once it is done"
                )
            sleep(poll)
        yield
    finally:
        if fd is not None:
            close(fd)  # drops the lock
