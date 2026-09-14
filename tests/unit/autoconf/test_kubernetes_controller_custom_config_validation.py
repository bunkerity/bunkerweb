"""`KubernetesController.get_configs()` against the shared custom-config validator.

A ConfigMap annotated `bunkerweb.io/CONFIG_TYPE` already accepts all nine types -- like Swarm
config objects, it is a namespaced cluster object, not a container label, so the Docker
fleet-global restriction (report-CC-A.md §4.3) does not apply here. What was never checked is
the *name* (a ConfigMap data key can be any string). This file pins WARN-only (design AC 6: a
ConfigMap-labelled install keeps accepting exactly what it accepts today).

Reuses @integration's controller loader (`test_lb_address_call_sites.py`) rather than a second
copy of the kubernetes stub -- a plain import on purpose: if it is renamed this file goes RED.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_lb_address_call_sites import _load  # noqa: E402

K8S = _load("KubernetesController", {})
KubernetesController = K8S.KubernetesController

ALL_NINE = (
    "http",
    "stream",
    "server-http",
    "server-stream",
    "default-server-http",
    "modsec",
    "modsec-crs",
    "crs-plugins-before",
    "crs-plugins-after",
)


def _bare_controller():
    controller = object.__new__(KubernetesController)
    controller._logger = Mock()
    controller._namespaces = None
    controller._supported_config_types = list(ALL_NINE)
    controller._services = []
    controller._ignored_annotations_exact = set()
    controller._ignored_annotation_suffixes = set()
    controller._warned_invalid_custom_conf_names = set()
    controller._api = Mock()
    return controller


def _configmap(name, config_type, data, *, namespace="default", config_site=None):
    annotations = {"bunkerweb.io/CONFIG_TYPE": config_type}
    if config_site:
        annotations["bunkerweb.io/CONFIG_SITE"] = config_site
    cm = Mock()
    cm.metadata.annotations = annotations
    cm.metadata.namespace = namespace
    cm.metadata.name = name
    cm.data = data
    return cm


def _get_configs(controller, configmaps):
    controller._corev1 = Mock()
    controller._corev1.list_config_map_for_all_namespaces.return_value.items = configmaps
    controller._is_service_present = Mock(return_value=True)
    return controller.get_configs()


class TestAllNineTypesStillWork:
    def test_http_configmap_is_accepted(self):
        controller = _bare_controller()
        _, configs = _get_configs(controller, [_configmap("cm1", "http", {"mysnippet.conf": "server {}"})])
        assert configs["http"]["mysnippet.conf"] == "server {}"
        controller._logger.warning.assert_not_called()


class TestInvalidNameIsWarnOnly:
    def test_bad_name_is_still_stored(self):
        controller = _bare_controller()
        _, configs = _get_configs(controller, [_configmap("cm1", "server-http", {"bad name!": "x"})])
        assert configs["server-http"]["bad name!"] == "x"
        controller._logger.warning.assert_called_once()
        message = controller._logger.warning.call_args[0][0]
        assert "1.8" in message

    def test_conventional_dot_conf_name_does_not_warn(self):
        controller = _bare_controller()
        _get_configs(controller, [_configmap("cm1", "modsec", {"mysnippet.conf": "x"})])
        controller._logger.warning.assert_not_called()

    def test_settings_type_configmaps_are_not_validated_as_custom_configs(self):
        """`CONFIG_TYPE: settings` is a different mechanism entirely (extra global
        settings, not a custom config) -- it must never run through this validator."""
        controller = _bare_controller()
        controller._api.validate_setting.return_value = (True, "")
        config, configs = _get_configs(controller, [_configmap("cm1", "settings", {"USE_ANTIBOT": "captcha"})])
        assert config == {"USE_ANTIBOT": "captcha"}
        assert all(not d for d in configs.values())
        controller._logger.warning.assert_not_called()

    def test_config_site_prefix_stripped_before_validating_name(self):
        controller = _bare_controller()
        _, configs = _get_configs(controller, [_configmap("cm1", "server-http", {"mysnippet.conf": "x"}, config_site="app.example.com")])
        assert configs["server-http"]["app.example.com/mysnippet.conf"] == "x"
        controller._logger.warning.assert_not_called()

    def test_warned_only_once_per_configmap_key(self):
        controller = _bare_controller()
        cm = _configmap("cm1", "modsec", {"bad name!": "x"})
        _get_configs(controller, [cm])
        _get_configs(controller, [cm])
        assert controller._logger.warning.call_count == 1
