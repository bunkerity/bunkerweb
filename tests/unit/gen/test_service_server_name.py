"""A service always has a name: an empty per-service SERVER_NAME is refused, an empty global one is not.

The shipped ``SERVER_NAME`` regex lets the value be empty, which the GLOBAL setting needs (no service
yet, the documented autoconf/Kubernetes value, QAR Q4). Applied to ``<service>_SERVER_NAME`` it let
``server_name ;`` through to nginx, which refuses the whole configuration (dev ``cea19bc67``).
"""

import json
import logging

import pytest

from Configurator import Configurator  # type: ignore  (src/common/gen on path)

REAL_SERVER_NAME = {
    "context": "multisite",
    "default": "www.example.com",
    "help": "h",
    "id": "server-name",
    "label": "x",
    # Verbatim from src/common/settings.json: the optional group is what makes "" legal.
    "regex": r"^(?!.*\.\.)(?:(\b[^\s+\/:A-Z]{1,255}\b)(?:\s+\b[^\s+\/:A-Z]{1,255}\b)*)?$",
    "type": "text",
}
SETTINGS = {
    "SERVER_NAME": REAL_SERVER_NAME,
    "MULTISITE": {"context": "global", "default": "no", "help": "h", "id": "multisite", "label": "x", "regex": "^(yes|no)$", "type": "check"},
}
CORE_PLUGIN = {
    "id": "test",
    "name": "Test",
    "description": "Test plugin",
    "version": "1.0",
    "stream": "no",
    "settings": {"TEST_MS": {"context": "multisite", "default": "ms", "help": "h", "id": "tm", "label": "x", "regex": "^[a-z]+$", "type": "text"}},
}


@pytest.fixture
def paths(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(SETTINGS))
    plugin_dir = tmp_path / "core" / "test"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(CORE_PLUGIN))
    return str(settings_file), str(tmp_path / "core")


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _config(paths, variables):
    logger = logging.getLogger(f"sv-{id(variables)}")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    records = _Records()
    logger.addHandler(records)
    settings_file, core = paths
    return Configurator(settings_file, core, [], [], variables, logger).get_config(), records.messages


@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "blank"])
def test_an_empty_service_server_name_is_refused_and_the_service_keeps_its_id(paths, blank):
    config, messages = _config(paths, {"MULTISITE": "yes", "SERVER_NAME": "app1", "app1_SERVER_NAME": blank})

    assert config["app1_SERVER_NAME"] == "app1"
    assert any("app1_SERVER_NAME" in message and "can't be empty" in message for message in messages), messages


def test_a_service_server_name_with_aliases_is_kept(paths):
    config, _ = _config(paths, {"MULTISITE": "yes", "SERVER_NAME": "app1", "app1_SERVER_NAME": "app1 alias.test"})

    assert config["app1_SERVER_NAME"] == "app1 alias.test"


def test_a_sibling_is_not_affected(paths):
    config, _ = _config(paths, {"MULTISITE": "yes", "SERVER_NAME": "app1 app2", "app1_SERVER_NAME": "", "app2_SERVER_NAME": "app2 alias.test"})

    assert config["app1_SERVER_NAME"] == "app1"
    assert config["app2_SERVER_NAME"] == "app2 alias.test"


@pytest.mark.parametrize("multisite", ["yes", "no"])
def test_an_empty_global_server_name_stays_valid(paths, multisite):
    """QAR Q4: the empty global value is the documented one when no service exists yet."""
    config, messages = _config(paths, {"MULTISITE": multisite, "SERVER_NAME": ""})

    assert config["SERVER_NAME"] == ""
    assert not any("can't be empty" in message for message in messages), messages
