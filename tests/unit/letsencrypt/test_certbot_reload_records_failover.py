"""The certbot jobs' own reload delivery feeds the UI's failover banner.

Both jobs push the renewed cache and reload the instances themselves, so the answers they get are
the only verdict for that reload: a refusal must raise the banner and an accepted reload must clear
it (a busy instance is neither). The block is extracted and run as shipped, like the publication
lock test next to it.
"""

import ast
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

import pytest

from reload_outcome import record_reload_responses

ROOT = Path(__file__).resolve().parents[3]
OK = {"status": "success", "msg": "reloaded"}
REFUSED = {"status": "error", "msg": 'nginx: [emerg] unknown directive "bogus"'}
BUSY = {"status": "error", "msg": "a configuration swap is still in progress"}


def _deliver(script, sent, responses):
    path = ROOT / "src/common/core/letsencrypt/jobs" / script
    tree = ast.parse(path.read_text(), filename=str(path))
    delivery = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and isinstance(node.body[0], ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "token" for target in node.body[0].targets)
    )
    caller = Mock()
    caller.send_files.return_value = True
    caller.send_to_apis.return_value = (sent, responses)
    db = Mock()
    db.record_reload_outcome.return_value = ""
    db.get_instances.return_value = [{"status": "up"}]
    namespace = {
        "status": 1,
        "LOGGER": Mock(),
        "getenv": lambda name, default=None: default,
        "JOB": Mock(db=db),
        "ApiCaller": Mock(return_value=caller),
        "API": Mock(),
        "CACHE_PATH": Path("/tmp/letsencrypt"),
        "le_cache_write_lock": nullcontext,
        "cache_publication_lock": lambda *_a, **_k: nullcontext(),
        "RELOAD_TIMEOUT": (5, 30),
        "record_reload_responses": record_reload_responses,
    }
    exec(compile(ast.Module(body=[delivery], type_ignores=[]), str(path), "exec"), namespace)  # noqa: S102
    return namespace, caller, db


@pytest.mark.parametrize("script", ["certbot-new.py", "certbot-renew.py"])
class TestDirectDelivery:
    def test_the_reload_asks_for_every_instances_answer(self, script):
        _, caller, _ = _deliver(script, True, {"bw-1": OK})
        caller.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30), response=True)

    def test_an_accepted_reload_is_recorded_so_it_can_clear_the_banner(self, script):
        namespace, _, db = _deliver(script, True, {"bw-1": OK, "bw-2": OK})
        db.record_reload_outcome.assert_called_once_with({"bw-1": None, "bw-2": None}, fleet=True)
        assert namespace["status"] == 0

    def test_a_refused_reload_is_recorded_and_the_worker_fallback_stays(self, script):
        namespace, _, db = _deliver(script, False, {"bw-1": REFUSED})
        db.record_reload_outcome.assert_called_once_with({"bw-1": REFUSED["msg"]}, fleet=True)
        assert namespace["status"] == 1

    def test_a_busy_instance_is_not_a_verdict(self, script):
        namespace, _, db = _deliver(script, False, {"bw-1": BUSY})
        db.record_reload_outcome.assert_not_called()
        assert namespace["status"] == 1
