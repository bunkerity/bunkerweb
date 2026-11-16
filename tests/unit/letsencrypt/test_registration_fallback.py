"""Failed pre-registration must keep orders sequential and in canonical storage."""

import ast
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import Mock

import pytest

import certbot_concurrency as concurrency
from letsencrypt_utils import LETSENCRYPT_PRODUCTION_DIRECTORY, ZEROSSL_DIRECTORY
from test_certbot_new_readiness_gate import CERTBOT_NEW, _load_definitions


@pytest.mark.parametrize("zerossl", [False, True])
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (CompletedProcess([], 0, stdout="registered"), True),
        (CompletedProcess([], 1, stdout="Existing account found"), True),
        (CompletedProcess([], 1, stdout="registration refused"), False),
        (TimeoutExpired("register", 300), False),
    ],
)
def test_registration_result(tmp_path, monkeypatch, zerossl, result, expected):
    process = Mock(side_effect=result) if isinstance(result, Exception) else Mock(return_value=result)
    monkeypatch.setattr(concurrency, "run", process)
    register = concurrency.ensure_zerossl_accounts if zerossl else concurrency.ensure_accounts
    assert register({(False, "")}, {}, "register", "INFO", tmp_path, "work", "logs", Mock()) is expected


@pytest.mark.parametrize("zerossl", [False, True])
def test_existing_account_needs_no_registration(tmp_path, monkeypatch, zerossl):
    server = ZEROSSL_DIRECTORY if zerossl else LETSENCRYPT_PRODUCTION_DIRECTORY
    account = tmp_path / "accounts" / concurrency._server_url_to_subpath(server) / "present"
    account.mkdir(parents=True)
    (account / "regr.json").write_text("{}")
    (account / "meta.json").write_text('{"email": "ops@example.com"}')
    process = Mock(side_effect=AssertionError("existing account must be reused"))
    monkeypatch.setattr(concurrency, "run", process)
    register = concurrency.ensure_zerossl_accounts if zerossl else concurrency.ensure_accounts
    assert register({(False, "ops@example.com")}, {}, "register", "INFO", tmp_path, "work", "logs", Mock()) is True
    process.assert_not_called()


@pytest.mark.parametrize("zerossl", [False, True])
def test_later_success_does_not_hide_registration_failure(tmp_path, monkeypatch, zerossl):
    process = Mock(side_effect=[CompletedProcess([], 1, stdout="refused"), CompletedProcess([], 0, stdout="registered")])
    monkeypatch.setattr(concurrency, "run", process)
    register = concurrency.ensure_zerossl_accounts if zerossl else concurrency.ensure_accounts
    assert register({(False, "a@example.com"), (False, "b@example.com")}, {}, "register", "INFO", tmp_path, "work", "logs", Mock()) is False
    assert process.call_count == 2


@pytest.mark.parametrize(("le_ok", "zerossl_ok"), [(True, True), (False, True), (True, False), (False, False)])
def test_order_dispatch_uses_registration_result(tmp_path, monkeypatch, le_ok, zerossl_ok):
    module = _load_definitions()
    monkeypatch.setenv("LETS_ENCRYPT_CONCURRENT_REQUESTS", "yes")
    module.DATA_PATH = tmp_path / "canonical"
    module.CACHE_PATH = tmp_path / "cache"
    module.WORK_DIR = str(tmp_path / "work")
    module.LOGS_DIR = str(tmp_path / "logs")
    module.prepare_certbot_paths = concurrency.prepare_certbot_paths
    module.finalize_certbot_run = concurrency.finalize_certbot_run
    module.certbot_new = Mock(return_value=0)
    module.ensure_accounts = Mock(return_value=le_ok)
    module.ensure_zerossl_accounts = Mock(return_value=zerossl_ok)
    module.start_progress_monitor = Mock()
    module.stop_progress_monitor = Mock()
    module.persist_issued_certificate = Mock()
    module.effective_cpu_count = Mock(return_value=2)
    executor = Mock(wraps=module.ThreadPoolExecutor)
    module.ThreadPoolExecutor = executor
    module.concurrent_requests = True
    module.cmd_env = {"LETS_ENCRYPT_CONCURRENT_REQUESTS": "yes"}
    module.services = {
        name: {
            "acme_server": ca,
            "email": "ops@example.com",
            "staging": False,
            "server_names": name,
            "wildcard": False,
            "challenge": "http",
            "profile": "classic",
            "retries": 0,
        }
        for name, ca in (("a.example.com", "letsencrypt"), ("b.example.com", "zerossl"))
    }
    module.pending_services = list(module.services.items())
    module.status = 0
    # Execute the job's dispatch block with real generation and storage helpers; stub only I/O.
    tree = ast.parse(CERTBOT_NEW.read_text())
    dispatch = next(node for node in ast.walk(tree) if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "pending_services")
    exec(compile(ast.Module(body=[dispatch], type_ignores=[]), str(CERTBOT_NEW), "exec"), module.__dict__)  # noqa: S102

    parallel = le_ok and zerossl_ok
    assert executor.call_count == int(parallel)
    assert module.status == 1
    assert all(config["exists"] for config in module.services.values())
    assert module.persist_issued_certificate.call_count == 2
    assert module.certbot_new.call_count == 2
    config_dirs = {call.args[3].config_dir for call in module.certbot_new.call_args_list}
    if parallel:
        assert len(config_dirs) == 2
        assert module.DATA_PATH not in config_dirs
    else:
        assert config_dirs == {module.DATA_PATH}
    assert module.cmd_env["LETS_ENCRYPT_CONCURRENT_REQUESTS"] == "yes"
    assert module.getenv("LETS_ENCRYPT_CONCURRENT_REQUESTS") == "yes"
    module.ensure_accounts.assert_called_once()
    module.ensure_zerossl_accounts.assert_called_once()
