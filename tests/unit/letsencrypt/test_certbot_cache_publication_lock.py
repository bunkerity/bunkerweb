"""Exercise each script's delivery block without issuing real certificates."""

import ast
from contextlib import contextmanager
from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
from pathlib import Path
from unittest.mock import Mock

import pytest

import jobs

ROOT = Path(__file__).resolve().parents[3]


def _probe(cache_root):
    with (cache_root / jobs.CACHE_PUBLICATION_LOCK_NAME).open("a") as lock:
        try:
            flock(lock, LOCK_EX | LOCK_NB)
        except BlockingIOError:
            return True
        flock(lock, LOCK_UN)
        return False


@pytest.mark.parametrize("script", ["certbot-new.py", "certbot-renew.py"])
@pytest.mark.parametrize("unlockable", [False, True])
def test_delivery_locks_cache_before_send(script, unlockable, tmp_path, monkeypatch):
    path = ROOT / "src/common/core/letsencrypt/jobs" / script
    tree = ast.parse(path.read_text(), filename=str(path))
    # Run the complete delivery try/except, including its fallback and reload, as shipped.
    delivery = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and isinstance(node.body[0], ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "token" for target in node.body[0].targets)
    )
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "jobs"]
    monkeypatch.setattr(jobs, "CACHE_PATH", tmp_path / "missing" if unlockable else tmp_path)
    le_held = False

    @contextmanager
    def le_lock():
        nonlocal le_held
        assert not _probe(tmp_path), "LE must be taken before publication, matching cache_dir -> cache_file"
        le_held = True
        try:
            yield
        finally:
            le_held = False

    seen = []
    caller = Mock()

    def send(*args, **kwargs):
        seen.append((le_held, _probe(tmp_path)))
        return True

    caller.send_files.side_effect = send
    caller.send_to_apis.side_effect = lambda *args, **kwargs: (not le_held and not _probe(tmp_path), {})
    namespace = {
        "status": 1,
        "LOGGER": Mock(),
        "getenv": lambda name, default=None: default,
        "JOB": Mock(db=Mock(get_instances=Mock(return_value=[{"status": "up"}]))),
        "ApiCaller": Mock(return_value=caller),
        "API": Mock(),
        "CACHE_PATH": tmp_path / "letsencrypt",
        "le_cache_write_lock": le_lock,
        "RELOAD_TIMEOUT": (5, 30),
    }
    exec(compile(ast.Module(body=[*imports, delivery], type_ignores=[]), str(path), "exec"), namespace)

    if unlockable:
        caller.send_files.assert_not_called()
        caller.send_to_apis.assert_not_called()
        assert namespace["status"] == 1
        namespace["LOGGER"].error.assert_called_once()
    else:
        assert seen == [(True, True)]
        caller.send_to_apis.assert_called_once()
        assert namespace["status"] == 0
    assert not le_held and not _probe(tmp_path)
