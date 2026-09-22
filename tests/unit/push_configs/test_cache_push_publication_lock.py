"""Every push-configs cache send must exclude concurrent Job cache writers."""

import ast
import sys
from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

import jobs

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src/common/core/jobs/jobs/push-configs.py"


def _probe(cache_root):
    with (cache_root / jobs.CACHE_PUBLICATION_LOCK_NAME).open("a") as lock:
        try:
            flock(lock, LOCK_EX | LOCK_NB)
        except BlockingIOError:
            return True
        flock(lock, LOCK_UN)
        return False


@pytest.fixture
def push(tmp_path, monkeypatch):
    tree = ast.parse(JOB_PATH.read_text(), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]
    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger")}
    for name in ("API", "ApiCaller", "Database"):
        setattr(stubs[name], name, Mock())
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["jobs"] = jobs
    module = ModuleType("bw_push_configs_publication")
    module.__file__ = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)
    monkeypatch.setattr(jobs, "CACHE_PATH", tmp_path)
    for name in ("CACHE_PATH", "CUSTOM_CONFIGS_PATH", "EXTERNAL_PLUGINS_PATH", "PRO_PLUGINS_PATH"):
        setattr(module, name, tmp_path)
    return module


def test_push_all_locks_only_cache(push, tmp_path):
    seen = {}
    caller = Mock(apis=[Mock()])
    caller.send_files.side_effect = lambda src, endpoint, **kwargs: seen.setdefault(endpoint, _probe(tmp_path)) or True
    configs = tmp_path / "nginx"
    configs.mkdir()
    (configs / "variables.env").write_text("API_TOKEN=test\n")
    original_push_configs = push._push_configs
    push._push_configs = lambda instances: original_push_configs(instances, configs)
    push._build_api_caller = Mock(return_value=caller)

    assert push._push_all(caller, [{"hostname": "instance"}]) is True
    assert seen["/cache"] is True
    for endpoint in ("/confs", "/custom_configs", "/plugins", "/pro_plugins"):
        assert seen[endpoint] is False
    assert _probe(tmp_path) is False


def test_snapshot_restore_locks_cache(push, tmp_path):
    snapshot = tmp_path / "snapshot"
    (snapshot / "cache").mkdir(parents=True)
    seen = []
    caller = Mock(apis=[Mock()])
    caller.send_files.side_effect = lambda *args, **kwargs: seen.append(_probe(tmp_path)) or True
    caller.send_to_apis.side_effect = lambda *args, **kwargs: (not _probe(tmp_path), {})

    assert push._restore_from_snapshot(snapshot, caller, []) is True
    assert seen == [True]
    caller.send_to_apis.assert_called_once()
    assert _probe(tmp_path) is False


def test_unlockable_tree_never_sends(push, tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "CACHE_PATH", tmp_path / "missing")
    caller = Mock(apis=[Mock()])

    assert push._push_one_kind(caller, tmp_path, "/cache") is False
    caller.send_files.assert_not_called()
