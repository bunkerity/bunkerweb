"""`SwarmController.get_configs()` against the shared custom-config validator.

Swarm config objects (`bunkerweb.CONFIG_TYPE` / `bunkerweb.CONFIG_SITE` labels) already
accept all nine types -- they are cluster-scoped objects, not a container label, so the
Docker fleet-global restriction (report-CC-A.md §4.3) does not apply here. What Swarm never
checked before this lane is the *name*: any string a Docker config object could be created
with was accepted. This file pins WARN-only (design AC 6: a Swarm-labelled install keeps
accepting exactly what it accepted before).

Reuses @integration's controller loader (`test_swarm_controller_gaps.py`) rather than a
second copy of the docker stub -- a plain import on purpose: if it is renamed this file goes
RED, which is the correct kind of loud.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_swarm_controller_gaps import _bare_controller, _config_obj  # noqa: E402


def _controller_with_types(types):
    controller = _bare_controller()
    controller._supported_config_types = list(types)
    # `_bare_controller()` predates this lane's WARN-only tracking set.
    controller._SwarmController__warned_invalid_custom_conf_names = set()
    return controller


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


def _get_configs(controller, configs):
    controller._SwarmController__client = Mock()
    controller._SwarmController__client.configs.list.return_value = configs
    return controller.get_configs()


class TestAllNineTypesStillWork:
    """Unlike Docker labels, a Swarm config object is cluster-scoped -- the fleet-global
    restriction is Docker-label-only (report-CC-A.md §4.3)."""

    def test_http_config_object_is_accepted(self):
        controller = _controller_with_types(ALL_NINE)
        configs = _get_configs(controller, [_config_obj("mysnippet.conf", {"bunkerweb.CONFIG_TYPE": "http"})])
        assert configs["http"]["mysnippet.conf"] == b"# a config"
        controller._logger.warning.assert_not_called()


class TestInvalidNameIsWarnOnly:
    def test_bad_name_is_still_stored(self):
        controller = _controller_with_types(ALL_NINE)
        data = b"location /x {}"
        configs = _get_configs(controller, [_config_obj("bad name!", {"bunkerweb.CONFIG_TYPE": "server-http"}, data=data)])
        assert configs["server-http"]["bad name!"] == data
        controller._logger.warning.assert_called_once()
        message = controller._logger.warning.call_args[0][0]
        assert "1.8" in message

    def test_conventional_dot_conf_name_does_not_warn(self):
        controller = _controller_with_types(ALL_NINE)
        _get_configs(controller, [_config_obj("mysnippet.conf", {"bunkerweb.CONFIG_TYPE": "modsec"})])
        controller._logger.warning.assert_not_called()

    def test_warned_only_once_per_config_object(self):
        """`__warned_invalid_custom_conf_names` is set once in `__init__` and never reset
        (unlike `__swarm_configs`, which IS reset every pass) -- it dedupes across reconciles,
        not just within one."""
        controller = _controller_with_types(ALL_NINE)
        obj = _config_obj("bad name!", {"bunkerweb.CONFIG_TYPE": "modsec"})
        controller._SwarmController__client = Mock()
        controller._SwarmController__client.configs.list.return_value = [obj]
        controller.get_configs()
        controller.get_configs()
        assert controller._logger.warning.call_count == 1

    def test_config_site_prefix_stripped_before_validating_name(self):
        """`config_site` is joined with `/` into the storage key; the name check must run
        on the bare name, not the `site/name` compound, or every scoped config would warn."""
        controller = _controller_with_types(ALL_NINE)
        controller._is_service_present = Mock(return_value=True)
        configs = _get_configs(
            controller,
            [_config_obj("mysnippet.conf", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.CONFIG_SITE": "app.example.com"})],
        )
        assert configs["server-http"]["app.example.com/mysnippet.conf"] == b"# a config"
        controller._logger.warning.assert_not_called()
