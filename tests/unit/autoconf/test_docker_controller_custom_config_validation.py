"""`DockerController.get_configs()` against the shared custom-config validator.

Before this lane, a `bunkerweb.CUSTOM_CONF_HTTP_*` (or `STREAM`/`DEFAULT_SERVER_HTTP`) label
simply did not match `__custom_confs_rx` and vanished with zero diagnostic (report-CC-A.md
§4.3, "silent non-match"). An invalid *name* on an otherwise-supported type was never checked
at all -- Docker labels accepted `.+`. This file pins both: the global-type case now logs an
explicit refusal naming the alternative, and a bad name is WARN-only (design AC 6: a
Docker-labelled install keeps accepting exactly what it accepted before).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


def _stub_docker():
    docker = ModuleType("docker")
    docker.DockerClient = Mock()
    containers_mod = ModuleType("docker.models.containers")
    containers_mod.Container = type("Container", (), {})
    models = ModuleType("docker.models")
    models.containers = containers_mod
    errors = ModuleType("docker.errors")

    class DockerException(Exception):
        pass

    errors.DockerException = DockerException
    docker.models = models
    docker.errors = errors
    return {
        "docker": docker,
        "docker.models": models,
        "docker.models.containers": containers_mod,
        "docker.errors": errors,
    }


def _load_docker_controller():
    stubs = _stub_docker()
    controllers = ModuleType("controllers")
    controller_mod = ModuleType("controllers.Controller")
    controller_mod.Controller = type("Controller", (), {})
    controllers.Controller = controller_mod
    stubs |= {"controllers": controllers, "controllers.Controller": controller_mod}

    with patch.dict(sys.modules, stubs):
        path = ROOT / "src" / "autoconf" / "controllers" / "DockerController.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_docker_controller", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


DOCKER = _load_docker_controller()
DockerController = DOCKER.DockerController


def _bare_controller():
    """A controller without `__init__` -- `__init__` builds a real DockerClient."""
    controller = object.__new__(DockerController)
    controller._logger = Mock()
    controller._namespaces = None
    controller._supported_config_types = [
        "http",
        "stream",
        "server-http",
        "server-stream",
        "default-server-http",
        "modsec",
        "modsec-crs",
        "crs-plugins-before",
        "crs-plugins-after",
    ]
    controller._DockerController__custom_confs_rx = DOCKER.build_docker_label_key_rx()
    controller._DockerController__custom_confs_rx_all_types = DOCKER.build_docker_label_key_rx(DOCKER.CUSTOM_CONFIG_TYPES)
    controller._DockerController__warned_global_custom_conf_labels = set()
    controller._DockerController__warned_invalid_custom_conf_names = set()
    controller._DockerController__ignored_labels_exact = set()
    controller._DockerController__ignored_label_suffixes = set()
    controller._is_service_present = Mock(return_value=True)
    return controller


def _container(cid, labels):
    obj = Mock()
    obj.id = cid
    obj.name = cid
    obj.labels = labels
    return obj


def _get_configs(controller, containers):
    controller._DockerController__client = Mock()
    controller._DockerController__client.containers.list.return_value = containers
    return controller.get_configs()


class TestSixTypesStillWork:
    def test_valid_label_is_stored(self):
        controller = _bare_controller()
        containers = [_container("c1", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.CUSTOM_CONF_SERVER_HTTP_mysnippet": "location /x {}"})]
        configs = _get_configs(controller, containers)
        assert configs["server-http"]["app.example.com/mysnippet"] == "location /x {}"
        controller._logger.warning.assert_not_called()

    def test_modsec_crs_not_misparsed_as_modsec(self):
        controller = _bare_controller()
        containers = [_container("c1", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.CUSTOM_CONF_MODSEC_CRS_foo": "SecRule ..."})]
        configs = _get_configs(controller, containers)
        assert configs["modsec-crs"]["app.example.com/foo"] == "SecRule ..."
        assert "app.example.com/CRS_foo" not in configs.get("modsec", {})


class TestFleetGlobalTypesAreExplicitlyRefused:
    """report-CC-A.md §4.3: the silent non-match becomes a logged, explicit refusal."""

    def test_http_label_logs_the_alternative_and_is_not_stored(self):
        controller = _bare_controller()
        containers = [_container("c1", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.CUSTOM_CONF_HTTP_mysnippet": "server {}"})]
        configs = _get_configs(controller, containers)
        assert configs["http"] == {}
        controller._logger.warning.assert_called_once()
        message = controller._logger.warning.call_args[0][0]
        assert "fleet-global" in message
        assert "docker config create" in message

    def test_warned_only_once_per_container(self):
        controller = _bare_controller()
        containers = [_container("c1", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.CUSTOM_CONF_STREAM_mysnippet": "x"})]
        _get_configs(controller, containers)
        _get_configs(controller, containers)
        assert controller._logger.warning.call_count == 1


class TestInvalidNameIsWarnOnly:
    """AC 6: a Docker-labelled install keeps accepting exactly what it accepted before --
    an invalid name warns, it does not disappear."""

    def test_bad_name_is_still_stored(self):
        controller = _bare_controller()
        containers = [_container("c1", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.CUSTOM_CONF_SERVER_HTTP_bad name!": "x"})]
        configs = _get_configs(controller, containers)
        assert configs["server-http"]["app.example.com/bad name!"] == "x"
        controller._logger.warning.assert_called_once()
        message = controller._logger.warning.call_args[0][0]
        assert "1.8" in message

    def test_conventional_dot_conf_name_does_not_warn(self):
        """The name eventually stored has `.conf` stripped by `Config.py`; validating the
        raw label suffix would warn on every ordinary `foo.conf`-named label."""
        controller = _bare_controller()
        containers = [_container("c1", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.CUSTOM_CONF_SERVER_HTTP_foo.conf": "x"})]
        _get_configs(controller, containers)
        controller._logger.warning.assert_not_called()
