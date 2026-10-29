"""autoconf main.py: the environment picks the controller, and the healthy marker follows its lifecycle."""

import logging
import os
import runpy
import signal
from pathlib import Path

import pytest
from _autoconf_helpers import LogCapture

import common_utils
import controllers.DockerController as docker_module
import controllers.GatewayController as gateway_module
import controllers.IngressController as ingress_module
import controllers.SwarmController as swarm_module

MAIN = Path(__file__).resolve().parents[3] / "src" / "autoconf" / "main.py"


class Exit(BaseException):
    def __init__(self, code):
        self.code = code


class FakeController:
    instances = [{"name": "bw-1"}, {"name": "bw-2"}]

    def __init__(self, *args):
        self.args = args
        self.events = []
        type(self).last = self

    def wait(self, interval):
        self.events.append(("wait", interval))
        return self.instances

    def initial_apply(self):
        self.events.append(("initial_apply",))
        return True

    def process_events(self):
        self.events.append(("process_events", marker_exists()))


MARKER = {}


def marker_exists():
    return MARKER["path"].exists()


@pytest.fixture
def run_main(clean_env, tmp_path, monkeypatch):
    for name in ("SWARM_MODE", "KUBERNETES_MODE", "KUBERNETES_GATEWAY_MODE", "DOCKER_HOST", "WAIT_RETRY_INTERVAL"):
        clean_env.delenv(name, raising=False)
    monkeypatch.setattr(common_utils, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(signal, "signal", lambda *a: handlers.__setitem__(a[0], a[1]))
    monkeypatch.setattr(os, "_exit", lambda code: (_ for _ in ()).throw(Exit(code)))
    state = tmp_path / "autoconf.healthy"
    MARKER["path"] = state
    real_write, real_unlink = Path.write_text, Path.unlink
    monkeypatch.setattr(
        Path, "write_text", lambda self, text, *a, **k: real_write(state, text, *a, **k) if self.name == "autoconf.healthy" else real_write(self, text, *a, **k)
    )
    monkeypatch.setattr(Path, "unlink", lambda self, *a, **k: real_unlink(state, *a, **k) if self.name == "autoconf.healthy" else real_unlink(self, *a, **k))
    for module, name in (
        (swarm_module, "SwarmController"),
        (ingress_module, "IngressController"),
        (docker_module, "DockerController"),
        (gateway_module, "GatewayController"),
    ):
        fake = type(name, (FakeController,), {})
        clean_env.setattr(module, name, fake)
    handlers.clear()
    capture = LogCapture()
    logger = logging.getLogger("AUTOCONF")
    logger.addHandler(capture)
    logger.setLevel(logging.DEBUG)

    def run():
        try:
            runpy.run_path(str(MAIN), run_name="autoconf_main_under_test")
            code = None
        except Exit as e:
            code = e.code
        except SystemExit as e:
            code = e.code
        return code, capture

    yield run, clean_env
    logger.removeHandler(capture)


handlers = {}


def controller_of(module, name):
    return getattr(module, name).last


def test_docker_is_the_default_mode(run_main):
    run, env = run_main
    env.setenv("DOCKER_HOST", "tcp://docker:2375")

    code, log = run()

    ctrl = controller_of(docker_module, "DockerController")
    assert code is None
    assert ctrl.args == ("tcp://docker:2375",)
    assert ctrl.events == [("wait", 5), ("initial_apply",), ("process_events", True)]
    assert log.has("Docker mode detected") and log.has("Instance #1 : bw-1") and log.has("Instance #2 : bw-2")


def test_swarm_mode(run_main):
    run, env = run_main
    env.setenv("SWARM_MODE", "YES")

    run()

    assert controller_of(swarm_module, "SwarmController").args == ("unix:///var/run/docker.sock",)


def test_kubernetes_mode_uses_the_ingress_controller(run_main):
    run, env = run_main
    env.setenv("KUBERNETES_MODE", "yes")
    env.setenv("WAIT_RETRY_INTERVAL", "9")

    code, log = run()

    assert controller_of(ingress_module, "IngressController").events[0] == ("wait", 9)
    assert log.has("Kubernetes mode detected")


def test_gateway_mode_implies_kubernetes_and_uses_the_gateway_controller(run_main):
    run, env = run_main
    env.setenv("KUBERNETES_GATEWAY_MODE", "yes")

    _, log = run()

    assert controller_of(gateway_module, "GatewayController").events[-1] == ("process_events", True)
    assert log.has("Kubernetes Gateway API mode detected")


def test_swarm_wins_over_kubernetes(run_main):
    run, env = run_main
    env.setenv("SWARM_MODE", "yes")
    env.setenv("KUBERNETES_MODE", "yes")

    run()

    assert controller_of(swarm_module, "SwarmController").events


def test_invalid_retry_interval_stops_before_any_controller_starts(run_main):
    run, env = run_main
    env.setenv("WAIT_RETRY_INTERVAL", "five")

    code, log = run()

    assert code == 1
    assert log.has("Invalid WAIT_RETRY_INTERVAL value, must be an integer", logging.ERROR)
    assert not hasattr(docker_module.DockerController, "last")


def test_a_controller_crash_exits_with_an_error_and_clears_the_healthy_marker(run_main):
    run, _ = run_main
    MARKER["path"].write_text("ok")

    def boom(self):
        raise RuntimeError("db unreachable")

    docker_module.DockerController.process_events = boom
    code, log = run()

    assert code == 1
    assert log.has("Exception while running autoconf :", logging.ERROR)
    assert not MARKER["path"].exists()


def test_stop_signals_exit_cleanly(run_main):
    run, _ = run_main
    run()

    with pytest.raises(Exit) as stopped:
        handlers[signal.SIGTERM](signal.SIGTERM, None)

    assert stopped.value.code == 0
    assert set(handlers) == {signal.SIGINT, signal.SIGTERM}
