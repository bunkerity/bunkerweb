"""UB5-5/7: drive core.py against container logs from before and during an action."""

import runpy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(params=["core", "api"])
def core(monkeypatch, tmp_path, request):
    suite = request.param
    now = datetime.now(timezone.utc)
    old = now - timedelta(seconds=30)
    state = {"last_test": (now - timedelta(minutes=1)).isoformat(), "restart_stack": "0"}
    utils = ModuleType("utils")
    utils.__path__ = []
    utils.resolve_env_placeholders = lambda text: text
    monkeypatch.setitem(sys.modules, "utils", utils)
    monkeypatch.setitem(sys.modules, "utils.logger", ModuleType("utils.logger"))
    action_utils = ModuleType("utils.action")
    action_utils.is_derived_from_selenium_action = lambda _: False

    def parse_action(_logger, _choices, integration, _name, data):
        defaults = dict(type="status", delay=0, annotations={}, url="", repeat=0, cooldown=0, log="", not_log="", full_clean=False, restart_stack=True)
        action = SimpleNamespace(**(defaults | {key: value for key, value in data.items() if key != integration} | data.get(integration, {})))
        action.integrations = {integration}
        state["log_from"] = getattr(action, "log_from", "bunkerweb")
        return action

    action_utils.parse_action = parse_action
    monkeypatch.setitem(sys.modules, "utils.action", action_utils)
    redis = ModuleType("redis")
    redis.Redis = lambda **_: SimpleNamespace(ping=lambda: True, get=state.get, set=state.__setitem__)
    monkeypatch.setitem(sys.modules, "redis", redis)
    handlers = ModuleType("core_handlers")
    for name in (
        "redis",
        "database",
        "bwcli",
        "tool",
        "script",
        "export",
        "http_string",
        "http_path",
        "http_status",
        "http_header",
        "http_ssl",
        "selenium_xpath",
        "selenium_cookie",
        "limit",
    ):
        setattr(handlers, f"{name}_handler", SimpleNamespace(handle=lambda *_: None))
    monkeypatch.setitem(sys.modules, "core_handlers", handlers)
    monkeypatch.setattr("time.sleep", lambda _: None)

    def run(action=None, *, events=(), restart=False, upgrade=None, integration="Docker"):
        state["restart_stack"] = "1" if restart else "0"

        def logs(_logger, _integration, since=None, *, log_from="bunkerweb"):
            boundary = datetime.fromisoformat(since) if isinstance(since, str) else since
            return [line for stamp, stream, line in events if stream == log_from and (boundary is None or stamp >= boundary)]

        utils.get_logs = logs
        if upgrade:
            monkeypatch.chdir(ROOT)
            test = f"upgrade;{upgrade}"
        else:
            directory = tmp_path / "tests" / suite
            directory.mkdir(parents=True, exist_ok=True)
            import yaml

            (directory / "fixture.yml").write_text(yaml.safe_dump({"actions": {"check": action}}))
            monkeypatch.chdir(tmp_path)
            test = "fixture;check"
        monkeypatch.setattr(sys, "argv", ["core.py", test, integration])
        runpy.run_path(str(ROOT / "tests" / f"{suite}.py"), run_name="__main__")

    return SimpleNamespace(run=run, old=old, fresh=now + timedelta(seconds=1))


def test_old_action_log_cannot_satisfy_later_action(core):
    with pytest.raises(SystemExit) as failed:
        core.run({"type": "status", "log": "request detected"}, events=[(core.old, "bunkerweb", "request detected")])
    assert failed.value.code == 1


def test_old_action_error_does_not_fail_later_action(core):
    core.run({"type": "status", "not_log": "old error"}, events=[(core.old, "bunkerweb", "old error")])


def test_current_action_log_satisfies_check(core):
    core.run({"type": "status", "log": "request detected"}, events=[(core.fresh, "bunkerweb", "request detected")])


def test_log_during_action_delay_is_in_scope(core, monkeypatch):
    events = []

    def sleep(_):
        if not events:
            events.append((datetime.now(timezone.utc), "bunkerweb", "delayed event"))

    monkeypatch.setattr("time.sleep", sleep)
    core.run({"type": "status", "delay": 1, "log": "delayed event"}, events=events)


def test_current_action_error_fails(core):
    with pytest.raises(SystemExit) as failed:
        core.run({"type": "status", "not_log": "new error"}, events=[(core.fresh, "bunkerweb", "new error")])
    assert failed.value.code == 1


@pytest.mark.parametrize(
    "name",
    [
        "to_latest_sqlite",
        "to_latest_1_sqlite",
        "to_latest_mariadb",
        "to_latest_1_mariadb",
        "to_latest_mysql",
        "to_latest_1_mysql",
        "to_latest_postgresql",
        "to_latest_1_postgresql",
    ],
)
@pytest.mark.parametrize("core", ["core"], indirect=True)
def test_upgrade_checks_scheduler_startup_errors(core, name):
    with pytest.raises(SystemExit) as failed:
        core.run(events=[(core.old, "scheduler", "❌ migration failed")], restart=True, upgrade=name)
    assert failed.value.code == 1


def test_restart_action_can_assert_its_startup_logs(core):
    core.run({"type": "status", "log": "startup event"}, events=[(core.old, "bunkerweb", "startup event")], restart=True)


@pytest.mark.parametrize("integration", ["Autoconf", "Kubernetes"])
def test_scheduler_errors_before_ready_marker_still_fail(core, integration):
    with pytest.raises(SystemExit) as failed:
        core.run(
            {"type": "status", "not_log": "❌", "log_from": "scheduler", "delay": 1},
            events=[(core.old, "scheduler", "❌ migration failed"), (core.fresh, "scheduler", "Executing job scheduler ...")],
            restart=True,
            integration=integration,
        )
    assert failed.value.code == 1
