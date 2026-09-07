"""A setting value may not carry its own newline (port of dev ``f6800cbd9``).

`variables.env` is line-oriented: `Templator` writes `KEY=VALUE\\n` and `load_variables` reads
every schema-known key back. A value holding an embedded newline therefore DECLARES A SECOND
SETTING when the file is read — a value like `x\\nAPI_TOKEN=stolen` reaches the reader as two
declarations. Regexes anchored with `^...$` (no MULTILINE) already refused it; the ones written
`.*` did not, which is why `API_TOKEN` is re-anchored in the same port.

Settings of type `file` hold PEM data and are exempt, and a TRAILING newline stays valid — a
Kubernetes ConfigMap block scalar always leaves one.
"""

import json
import logging

import pytest

from Configurator import Configurator  # type: ignore  (src/common/gen on path)

LOGGER = logging.getLogger("cfg-newline-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)

SETTINGS = {
    "SERVER_NAME": {"context": "multisite", "default": "www.example.com", "help": "h", "id": "server-name", "label": "x", "regex": "^.*$", "type": "text"},
    "MULTISITE": {"context": "global", "default": "no", "help": "h", "id": "multisite", "label": "x", "regex": "^(yes|no)$", "type": "check"},
    # A permissive regex on purpose: `.*` is the shape the newline guard exists for, since an
    # unanchored regex matches the first line and lets the rest through.
}

CORE_PLUGIN = {
    "id": "test",
    "name": "Test",
    "description": "d",
    "version": "1.0",
    "stream": "no",
    # get_config() exits when a core plugin declares no settings at all, so this one carries the
    # permissive pair the guard is about.
    "settings": {
        "LOOSE_TOKEN": {"context": "global", "default": "", "help": "h", "id": "lt", "label": "x", "regex": ".*", "type": "text"},
        "LOOSE_MS": {"context": "multisite", "default": "", "help": "h", "id": "lm", "label": "x", "regex": ".*", "type": "text"},
        "CERT_DATA": {"context": "multisite", "default": "", "help": "h", "id": "cd", "label": "x", "regex": ".*", "type": "file"},
    },
}

PEM = "-----BEGIN CERTIFICATE-----\nMIIBkTCB+wIJAK==\n-----END CERTIFICATE-----"


@pytest.fixture
def cfg_paths(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(SETTINGS))
    plugin_dir = tmp_path / "core" / "test"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(CORE_PLUGIN))
    return str(settings_file), str(tmp_path / "core")


def _config(cfg_paths, variables):
    settings_file, core = cfg_paths
    return Configurator(settings_file, core, [], [], variables, LOGGER).get_config()


def test_a_single_site_value_with_an_embedded_newline_is_refused(cfg_paths):
    config = _config(cfg_paths, {"LOOSE_TOKEN": "value\nAPI_TOKEN=stolen"})

    assert config["LOOSE_TOKEN"] == "", "the injected declaration was accepted"


def test_a_carriage_return_is_refused_too(cfg_paths):
    assert _config(cfg_paths, {"LOOSE_TOKEN": "value\rAPI_TOKEN=stolen"})["LOOSE_TOKEN"] == ""


def test_a_multisite_value_with_an_embedded_newline_is_refused(cfg_paths):
    config = _config(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app.example.com", "app.example.com_LOOSE_MS": "a\nb"})

    assert config.get("app.example.com_LOOSE_MS", "") == "", "the injected declaration was accepted on the multisite path"


def test_a_trailing_newline_is_still_accepted(cfg_paths):
    """A ConfigMap block scalar always leaves one; refusing it would break every k8s install."""
    assert _config(cfg_paths, {"LOOSE_TOKEN": "value\n"})["LOOSE_TOKEN"] == "value\n"


def test_a_file_setting_keeps_its_pem_block(cfg_paths):
    config = _config(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app.example.com", "app.example.com_CERT_DATA": PEM})

    assert config["app.example.com_CERT_DATA"] == PEM, "a file setting must keep its newlines"


def test_the_shipped_api_token_regex_is_anchored():
    """The other half of the port: `.*` matched the first line and let the rest through."""
    from pathlib import Path

    settings = json.loads((Path(__file__).resolve().parents[3] / "src" / "common" / "settings.json").read_text(encoding="utf-8"))

    assert settings["API_TOKEN"]["regex"] == "^.*$", "API_TOKEN's regex is unanchored again"


def test_a_whitespace_separated_list_written_across_lines_is_now_refused(cfg_paths):
    """Pinned deliberately: this is the one behaviour change the guard makes VISIBLE to operators.

    `SERVER_NAME` is a `text` setting whose regex separates names with `\\s+`, so a value written as
    a YAML block scalar (`SERVER_NAME: |` in a Kubernetes ConfigMap, one host per line) used to
    validate — and was then written into `variables.env` as a MULTI-LINE value, which is the
    corruption this guard exists to stop. It is now refused, and `Configurator.get_config` turns a
    refused value into `exit(1)`: on such a host the scheduler stops instead of booting with a
    silently mangled server list. Collapsing the newlines to spaces instead would be an equally
    valid reading; that is a PO call, recorded in `report-DEV-2b.md`, not something this port
    decides on its own.
    """
    with pytest.raises(SystemExit):
        _config(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com\napp2.example.com"})


def test_the_same_list_on_one_line_is_untouched(cfg_paths):
    config = _config(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com app2.example.com"})

    assert config["SERVER_NAME"] == "app1.example.com app2.example.com"
