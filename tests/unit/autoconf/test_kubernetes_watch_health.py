"""A Kubernetes watch that stops streaming has to fail loudly, and an IPv6 load balancer
address has to be filed as an address rather than as a hostname.

Both behaviours are invisible from the outside when they are wrong: the watch case leaves a
controller that reconciles nothing while its health marker still says it is fine, and the IPv6
case is rejected by the API server with a 422 that only shows up in the controller's log.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_controller():
    """Import KubernetesController without the `kubernetes` package installed.

    `.venv-unit` deliberately does not carry autoconf's runtime deps, so the module's three
    `kubernetes*` imports and its `controllers.Controller` base are stubbed. Only module-level
    names are needed -- every function under test here touches neither.
    """
    kubernetes = ModuleType("kubernetes")
    kubernetes.client = ModuleType("kubernetes.client")
    kubernetes.client.Configuration = object
    kubernetes.config = Mock()
    kubernetes.watch = Mock()
    exceptions = ModuleType("kubernetes.client.exceptions")

    class ApiException(Exception):
        def __init__(self, status=None, reason=None):
            super().__init__(f"{status} {reason}")
            self.status = status
            self.reason = reason

    exceptions.ApiException = ApiException
    kubernetes.client.exceptions = exceptions

    controllers = ModuleType("controllers")
    controller_mod = ModuleType("controllers.Controller")
    controller_mod.Controller = type("Controller", (), {})
    controllers.Controller = controller_mod

    stubs = {
        "kubernetes": kubernetes,
        "kubernetes.client": kubernetes.client,
        "kubernetes.client.exceptions": exceptions,
        "controllers": controllers,
        "controllers.Controller": controller_mod,
    }
    with patch.dict(sys.modules, stubs):
        path = ROOT / "src" / "autoconf" / "controllers" / "KubernetesController.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_k8s_controller", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, ApiException


MODULE, ApiException = _load_controller()
KubernetesController = MODULE.KubernetesController


def _bare_controller(healthy_path):
    """A controller instance without __init__ -- __init__ builds real Kubernetes clients."""
    controller = object.__new__(KubernetesController)
    controller._logger = Mock()
    MODULE.HEALTHY_PATH = healthy_path
    return controller


# Named so a floor can assert they are still populated -- an emptied parametrize list collects
# nothing and the run still reports "N passed" (RULE 13).
IP_LITERALS = ["10.0.0.1", "192.168.1.254", "2001:db8::1", "::1", "fd00:1234:5678::abcd"]
DNS_NAMES = ["lb.example.com", "a1b2c3.elb.eu-west-1.amazonaws.com", "", "not an address"]


def test_the_address_tables_are_populated():
    """Floor, not an exact count -- growth is collaboration: another lane may add cases.
    Both families must stay represented, which is the whole point of the fix."""
    assert len(IP_LITERALS) >= 5, "IP_LITERALS emptied: the address tests collect nothing"
    assert len(DNS_NAMES) >= 4, "DNS_NAMES emptied: the hostname tests collect nothing"
    assert any(":" in a for a in IP_LITERALS), "no IPv6 literal left -- the regex this replaced passed IPv4 too"


class TestIsIpAddress:
    @pytest.mark.parametrize("address", IP_LITERALS)
    def test_ip_literals_of_both_families_are_addresses(self, address):
        assert KubernetesController._is_ip_address(address) is True

    @pytest.mark.parametrize("address", DNS_NAMES)
    def test_dns_names_are_not_addresses(self, address):
        assert KubernetesController._is_ip_address(address) is False

    def test_an_ipv6_literal_is_not_classified_as_a_hostname(self):
        """The whole point of the fix: the IPv4-only regex it replaced said False here, and the
        caller then filed the literal under `hostname`, which Kubernetes validates as an RFC 1123
        name and rejects."""
        assert KubernetesController._is_ip_address("2001:db8::1") is True


class TestWatchFailureIsLoud:
    def test_a_watch_that_never_streams_raises_instead_of_returning(self, tmp_path):
        controller = _bare_controller(tmp_path / "autoconf.healthy")
        with patch.object(MODULE.watch, "Watch") as watcher:
            watcher.return_value.stream.side_effect = ApiException(status=500, reason="boom")
            with patch.object(MODULE, "sleep"):
                with pytest.raises(RuntimeError, match="Failed to watch pod after 2 retries"):
                    list(controller._get_stream_with_retries("pod", Mock(), retries=2))

    def test_the_health_marker_is_dropped_when_the_watch_gives_up(self, tmp_path):
        """The marker is per watch_type since dev `dbd98e87a`: a watch stuck retrying must not be
        hidden behind a sibling watch that is still streaming and keeps the shared file alive."""
        marker = tmp_path / "autoconf.healthy"
        marker.write_text("ok")
        controller = _bare_controller(marker)
        pod_marker = controller._watch_healthy_path("pod")
        pod_marker.write_text("ok")
        sibling = controller._watch_healthy_path("ingress")
        sibling.write_text("ok")
        with patch.object(MODULE.watch, "Watch") as watcher:
            watcher.return_value.stream.side_effect = ApiException(status=401, reason="Unauthorized")
            with patch.object(MODULE, "sleep"):
                with pytest.raises(RuntimeError):
                    list(controller._get_stream_with_retries("pod", Mock(), retries=1))
        assert not pod_marker.exists(), "the orchestrator's liveness probe still reads this watch as healthy"
        assert sibling.exists(), "a failing watch must not drop a healthy sibling's marker"

    def test_rejected_credentials_are_named_in_the_log(self, tmp_path):
        controller = _bare_controller(tmp_path / "autoconf.healthy")
        with patch.object(MODULE.watch, "Watch") as watcher:
            watcher.return_value.stream.side_effect = ApiException(status=403, reason="Forbidden")
            with patch.object(MODULE, "sleep"):
                with pytest.raises(RuntimeError):
                    list(controller._get_stream_with_retries("pod", Mock(), retries=1))
        logged = " ".join(str(call) for call in controller._logger.error.call_args_list)
        assert "ServiceAccount" in logged, "a 403 has one likely cause and the log should name it"

    def test_a_streaming_watch_restores_the_marker(self, tmp_path):
        marker = tmp_path / "autoconf.healthy"
        controller = _bare_controller(marker)
        pod_marker = controller._watch_healthy_path("pod")
        assert not pod_marker.exists()
        controller._mark_healthy("pod")
        assert pod_marker.read_text() == "ok"

    def test_marking_healthy_twice_does_not_re_log(self, tmp_path):
        marker = tmp_path / "autoconf.healthy"
        controller = _bare_controller(marker)
        controller._mark_healthy("pod")
        controller._mark_healthy("pod")
        assert controller._logger.info.call_count == 1, "_mark_healthy runs on every event; it must be quiet once healthy"

    def test_every_expected_watch_is_seeded_healthy_and_published(self, tmp_path):
        """A watch for a resource kind with zero objects never receives an event, so the markers
        are SEEDED at start: absence must mean "this watch exhausted its retries", nothing else.
        The `.expected` list is what tells the healthcheck which markers to require."""
        marker = tmp_path / "autoconf.healthy"
        controller = _bare_controller(marker)
        controller._write_expected_watch_types(["pod", "ingress", "gateway.networking.k8s.io/v1/httproute"])
        expected = marker.with_name(f"{marker.name}.expected")
        listed = expected.read_text().split()
        assert listed == sorted(listed), "the list is written sorted so a restart does not churn it"
        assert set(listed) == {"pod", "ingress", "gateway_networking_k8s_io_v1_httproute"}
        for watch_type in listed:
            assert marker.with_name(f"{marker.name}.{watch_type}").read_text() == "ok"

    def test_a_watch_type_with_path_characters_cannot_escape_the_marker_directory(self, tmp_path):
        """watch_type reaches a filename: an API group is `a.b.c/v1/kind`, and `..` in it would
        otherwise walk out of /var/tmp/bunkerweb."""
        controller = _bare_controller(tmp_path / "autoconf.healthy")
        path = controller._watch_healthy_path("../../etc/passwd")
        assert path.parent == tmp_path
        assert path.name == "autoconf.healthy.______etc_passwd"

    def test_an_established_connection_that_closes_cleanly_is_not_a_failure(self, tmp_path):
        """The API server closes an idle watch on its own timeout. Counting that as an attempt
        exhausted the retry budget of a healthy but quiet watch (dev `dbd98e87a`)."""
        controller = _bare_controller(tmp_path / "autoconf.healthy")
        clock = {"now": 1000.0}
        closes = {"count": 0}

        def _stream(*args, **kwargs):
            closes["count"] += 1
            if closes["count"] > 3:
                raise ApiException(status=500, reason="boom")
            clock["now"] += MODULE.WATCH_ESTABLISHED_SECONDS + 1
            return iter(())

        with patch.object(MODULE.watch, "Watch") as watcher:
            watcher.return_value.stream.side_effect = _stream
            with patch.object(MODULE, "sleep"), patch.object(MODULE, "time", lambda: clock["now"]):
                with pytest.raises(RuntimeError):
                    list(controller._get_stream_with_retries("pod", Mock(), retries=2))

        # 3 long-lived closes reset the budget every time; only the raising attempts count.
        assert closes["count"] == 5, f"the retry budget was not reset by an established close ({closes['count']} streams)"
        assert controller._watch_healthy_path("pod").exists() is False, "the final give-up still drops the marker"
