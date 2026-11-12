"""``AUTH_BASIC_USER`` refuses a CR or LF anywhere in the value, a terminal one included.

``[^:\\r\\n]+$`` is not enough: ``$`` also matches before a final ``\\n`` in Python ``re``, which the
server uses (Configurator, ``Database.check_setting``, the UI) with ``re.search``, so ``alice\\n`` would
still pass. The shipped regex refuses it with a lookahead instead. The engines that evaluate a
plugin regex are Python ``re``, the ``regex`` module (UI and API helpers) and the browser, which
``tests/unit/ui/test_authbasic_user_browser_pattern.py`` covers.
"""

import json
import logging
import re
from pathlib import Path

import pytest
import regex

from Configurator import Configurator  # type: ignore  (src/common/gen on path)

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src" / "common" / "core" / "authbasic" / "plugin.json"
USER_REGEX = json.loads(PLUGIN.read_text(encoding="utf-8"))["settings"]["AUTH_BASIC_USER"]["regex"]

LOGGER = logging.getLogger("authbasic-user-regex")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)

VALID_USERS = ["alice", "bob smith", "a.b-c_d@example.com", "changeme"]
INVALID_USERS = ["alice\n", "alice\r", "alice\r\n", "al\nice", "al\rice", "al\r\nice", "\nalice", "\n", "", "al:ice"]


@pytest.mark.parametrize("engine", [re.search, regex.search], ids=["re", "regex"])
@pytest.mark.parametrize("value", VALID_USERS)
def test_a_normal_user_is_accepted(engine, value):
    assert engine(USER_REGEX, value) is not None


@pytest.mark.parametrize("engine", [re.search, regex.search], ids=["re", "regex"])
@pytest.mark.parametrize("value", INVALID_USERS, ids=[repr(v) for v in INVALID_USERS])
def test_a_value_with_a_cr_or_lf_is_refused(engine, value):
    assert engine(USER_REGEX, value) is None


@pytest.mark.parametrize("value", ["alice\n", "alice\r", "al\r\nice"], ids=repr)
def test_the_configurator_drops_a_user_with_a_cr_or_lf(tmp_path, value):
    """The Configurator tolerates a trailing newline on text settings (Kubernetes block scalars); for this setting the regex stops it."""
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"SERVER_NAME": {"context": "multisite", "default": "", "help": "h", "id": "sn", "label": "x", "regex": "^.*$", "type": "text"}})
    )
    plugin_dir = tmp_path / "core" / "authbasic"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(PLUGIN.read_text(encoding="utf-8"))
    config = Configurator(str(settings), str(tmp_path / "core"), [], [], {"AUTH_BASIC_USER": value}, LOGGER).get_config()
    # A refused value is dropped and the shipped default stays: the value itself never reaches the config.
    assert config["AUTH_BASIC_USER"] == "changeme"
