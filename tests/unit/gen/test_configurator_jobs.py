"""``Configurator.__validate_plugin`` — the ``jobs[]`` block (1.7).

``regenerate`` joins ``reload`` and ``async`` as a declared job flag. The manifest is the only
place a plugin author can turn it on, and a flag nobody reads is indistinguishable from a flag
set to false — so a typo (``"regenrate"``) would silently reproduce the very defect the flag
exists to close. The key set is therefore closed: an unknown key is refused, with the offending
name in the message, and the plugin is skipped rather than loaded half-configured.
"""

import json
import logging

import pytest

from Configurator import Configurator  # type: ignore

LOGGER = logging.getLogger("cfg-jobs-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)

SETTINGS = {
    "SERVER_NAME": {"context": "multisite", "default": "www.example.com", "help": "h", "id": "server-name", "label": "x", "regex": "^.*$", "type": "text"},
}

BASE = {"id": "myplug", "name": "My", "description": "d", "version": "1.0", "stream": "no", "settings": {}}


def _configurator(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(SETTINGS))
    core = tmp_path / "core"
    core.mkdir()
    return Configurator(str(settings_file), str(core), [], [], {}, LOGGER)


def _validate(tmp_path, job):
    return _configurator(tmp_path)._Configurator__validate_plugin(dict(BASE, jobs=[job]))


def _job(**over):
    job = {"name": "myjob", "file": "myjob.py", "every": "hour", "reload": True}
    job.update(over)
    return job


class TestRegenerate:
    @pytest.mark.parametrize("value", (True, False))
    def test_bool_accepted(self, tmp_path, value):
        ok, msg = _validate(tmp_path, _job(regenerate=value))
        assert ok, msg

    def test_absent_accepted(self, tmp_path):
        ok, msg = _validate(tmp_path, _job())
        assert ok, msg

    @pytest.mark.parametrize("value", ("yes", "true", 1, None, []))
    def test_non_bool_refused(self, tmp_path, value):
        ok, msg = _validate(tmp_path, _job(regenerate=value))
        assert not ok
        assert "regenerate" in msg


class TestClosedKeySet:
    def test_typo_refused_and_named(self, tmp_path):
        """The whole point: `regenrate: true` must not be accepted as "no flag set"."""
        ok, msg = _validate(tmp_path, _job(regenrate=True))
        assert not ok
        assert "regenrate" in msg

    def test_every_allowed_key_together(self, tmp_path):
        ok, msg = _validate(tmp_path, _job(**{"async": True, "regenerate": True}))
        assert ok, msg

    def test_unknown_keys_listed_sorted(self, tmp_path):
        ok, msg = _validate(tmp_path, _job(zebra=1, alpha=2))
        assert not ok
        assert "alpha, zebra" in msg
