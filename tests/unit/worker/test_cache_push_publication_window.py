"""The `/cache` push must hold the tree still while the instance swaps it.

`POST /cache` publishes by REPLACING every top-level entry of the destination with the archive's
copy (`api.lua`'s /confs handler -> `pushswap.swap`). On the Linux package and all-in-one that
destination IS `/var/cache/bunkerweb` on this host, so a job's `cache_file` landing between the tar
being built and the swap completing is parked into `.bw-trash` and deleted -- with its database row
already written. `send_files` returns only once the instance has answered, i.e. once the swap is
done, so holding the publication lock across that one call is what covers the whole window.

Linux CI run `7c7c50e66` job 103950399340 is the live case: `customcert/default-server/cert.pem`
written at 11:10:51 into the holder's in-flight push, then three reloads (11:10:52, :53, :54) all
logging "No such file or directory" for it -- the two later rounds could not carry it either,
because the swap had already deleted it from the very tree their tars were built from.
"""

from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
from os import O_CREAT, O_RDWR, close as os_close, open as os_open

import pytest

from test_delivery_guarantees import BROKER, LOGGER, TASKS
from test_reload_broadcast import _LockRedis, _apis, _with_redis

# The jobs module `tasks.py` actually holds. `_load_tasks()` imports it inside a
# `patch.dict(sys.modules, ...)`, which EVICTS it on exit, so a plain `import jobs` here would give
# a different module object and patching its CACHE_PATH would leave the push pointed at
# /var/cache/bunkerweb. These are the globals the bound function really reads.
# `.__wrapped__` because @contextmanager wraps it; the wrapper's globals are contextlib's.
JOBS_GLOBALS = TASKS.cache_publication_lock.__wrapped__.__globals__
LOCK_NAME = JOBS_GLOBALS["CACHE_PUBLICATION_LOCK_NAME"]


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    monkeypatch.setitem(JOBS_GLOBALS, "CACHE_PATH", tmp_path)
    return tmp_path


def _probe(cache_root) -> bool:
    """Would a concurrent worker child's exclusive flock be refused right now?"""
    fd = os_open((cache_root / LOCK_NAME).as_posix(), O_CREAT | O_RDWR, 0o660)
    try:
        try:
            flock(fd, LOCK_EX | LOCK_NB)
        except OSError:
            return True
        flock(fd, LOCK_UN)
        return False
    finally:
        os_close(fd)


def test_the_push_holds_the_publication_lock_across_send_files(cache_root):
    """The regression: a `cache_file` racing the tar-and-swap window used to be deleted by it."""
    seen = []
    apis = _apis()
    apis.send_files.side_effect = lambda *a, **k: seen.append(_probe(cache_root)) or True

    with _with_redis(_LockRedis()):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    apis.send_files.assert_called_once()
    assert seen == [True], "the cache tree was tarred and swapped with nothing holding writers off"


def test_the_lock_is_released_before_the_reload(cache_root):
    """Exactly the push, not the reload: a reload touches no file and can cost 30 s.

    Both halves are probed in one run on purpose. Asserting only "not held during the reload" is
    vacuously true of a build that takes no lock at all, which is the very state this file exists
    to keep out.
    """
    seen = []
    apis = _apis()
    apis.send_files.side_effect = lambda *a, **k: seen.append(("push", _probe(cache_root))) or True
    apis.send_to_apis.side_effect = lambda *a, **k: (seen.append(("reload", _probe(cache_root))), (True, {}))[1]

    with _with_redis(_LockRedis()):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    apis.send_to_apis.assert_called_once()
    assert seen == [("push", True), ("reload", False)], "the lock does not cover exactly the push"


def test_the_lock_is_released_when_the_push_fails(cache_root):
    """A failed push raises out of the `with`; a leaked flock would stall every later write."""
    apis = _apis()
    apis.send_files.return_value = False

    # The failure is re-raised to `execute_job`, which is what records the run as failed.
    with _with_redis(_LockRedis()), pytest.raises(RuntimeError):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    assert _probe(cache_root) is False, "the failed push left the publication lock held"


@pytest.mark.parametrize("failure", ["missing", "timeout", "permanent"])
def test_failed_lock_never_pushes_or_reloads(cache_root, monkeypatch, failure):
    from unittest.mock import Mock

    root = cache_root / "missing" if failure == "missing" else cache_root
    monkeypatch.setitem(JOBS_GLOBALS, "CACHE_PATH", root)
    monkeypatch.setitem(JOBS_GLOBALS, "CACHE_PUBLICATION_LOCK_WAIT", 0)
    if failure != "missing":
        error = BlockingIOError if failure == "timeout" else OSError
        monkeypatch.setitem(JOBS_GLOBALS, "flock", Mock(side_effect=error("lock unavailable")))
    apis = _apis()
    with _with_redis(_LockRedis()), pytest.raises(RuntimeError, match="publication lock"):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)
    apis.send_files.assert_not_called()
    apis.send_to_apis.assert_not_called()
    if failure == "missing":
        assert not root.exists()
