"""``reload_plugins`` (Web UI) must not overwrite or sweep away a hand-mounted plugin the scheduler refused.

The scheduler keeps a malformed ``plugin.json`` directory on disk and gives it no database row. The Web UI
shares ``/etc/bunkerweb/plugins`` and its reload (a) re-extracted the stored copy over a manual plugin whose
directory was being edited and (b) removed every directory the database did not know, so the operator's only
copy went with the first plugin change made in the UI.
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
_UI_APP = ROOT / "src" / "ui" / "app"
if str(ROOT / "src" / "common" / "gen") not in sys.path:
    sys.path.append(str(ROOT / "src" / "common" / "gen"))

from Configurator import Configurator  # type: ignore  # noqa: E402

DEPENDENCIES = _UI_APP / "dependencies.py"


def _load(module_name: str, path: Path, stubs: dict) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
    return module


def _setting(setting_id):
    return {"id": setting_id, "context": "global", "default": "x", "help": "h", "label": "L", "regex": "^.*$", "type": "text"}


def _manifest(plugin_id, **settings):
    return {
        "id": plugin_id,
        "name": "N",
        "description": "d",
        "version": "1.0",
        "stream": "no",
        "settings": settings or {f"{plugin_id.upper()}_ONE": _setting(f"{plugin_id}-one")},
    }


class _Api:
    def __init__(self, plugins):
        self.plugins = plugins

    def get_plugins(self, **kwargs):
        return self.plugins

    def checked_changes(self, *args, **kwargs):
        return None


@pytest.fixture
def ui(tmp_path):
    ui_data = _load("app.models._ui_data_p2a_test", _UI_APP / "models" / "ui_data.py", {})
    stubs = {name: MagicMock() for name in ("app.api_client", "app.perf", "app.models.config", "app.models.instance", "app.plugin_api")}
    stubs["app.models.ui_data"] = ui_data
    module = _load("app._dependencies_p2a_test", DEPENDENCIES, stubs)
    module.EXTERNAL_PLUGINS_PATH = tmp_path / "plugins"
    module.PRO_PLUGINS_PATH = tmp_path / "pro"
    module.EXTERNAL_PLUGINS_PATH.mkdir()
    module.PLUGIN_VALIDATOR = Configurator(
        str(ROOT / "src" / "common" / "settings.json"), str(ROOT / "src" / "common" / "core"), [], [], {}, logging.getLogger("ui-p2a")
    )

    def stored(manifest, *, method="manual", dir_name=None):
        """A database row (with its archive) for ``manifest``; the directory is NOT created on disk."""
        source = tmp_path / "src" / (dir_name or manifest["id"])
        source.mkdir(parents=True)
        source.joinpath("plugin.json").write_text(json.dumps(manifest))
        content = create_plugin_tar_gz(source, arc_root=source.name)
        return manifest | {
            "type": "external",
            "method": method,
            "name": manifest["name"],
            "data": content.getvalue(),
            "checksum": bytes_hash(content, algorithm="sha256"),
        }

    def mount(name, content):
        folder = module.EXTERNAL_PLUGINS_PATH / name
        folder.mkdir()
        text = content if isinstance(content, str) else json.dumps(content)
        folder.joinpath("plugin.json").write_text(text)
        return folder

    def reload(*rows):
        module.API_CLIENT = _Api(list(rows))
        module.reload_plugins()

    module.stored, module.mount, module.reload = stored, mount, reload
    return module


def test_an_orphan_with_a_malformed_manifest_survives_a_reload(ui):
    broken = ui.mount("broken", "{ typo")
    invalid = ui.mount("invalid", {"id": "invalid"})

    ui.reload()

    assert broken.joinpath("plugin.json").read_text() == "{ typo"
    assert invalid.is_dir()


def test_an_orphan_that_is_valid_or_has_no_manifest_is_still_swept(ui):
    valid = ui.mount("valid", _manifest("valid"))
    stray = ui.EXTERNAL_PLUGINS_PATH / "stray"
    stray.mkdir()
    (stray / "notes.txt").write_text("x")

    ui.reload()

    assert not valid.exists() and not stray.exists()


def test_an_orphan_the_scheduler_refused_for_a_duplicate_setting_id_survives(ui):
    holder = ui.stored(_manifest("holder", HOLDER_ONE=_setting("held-id")))
    thief = ui.mount("thief", _manifest("thief", THIEF_ONE=_setting("held-id")))

    ui.reload(holder)

    assert thief.is_dir()
    assert ui.EXTERNAL_PLUGINS_PATH.joinpath("holder", "plugin.json").is_file()


def test_a_broken_edit_of_a_stored_manual_plugin_is_not_overwritten(ui):
    row = ui.stored(_manifest("mine"))
    broken = ui.mount("mine", "{ half-edited")

    ui.reload(row)

    assert broken.joinpath("plugin.json").read_text() == "{ half-edited"


def test_a_broken_directory_with_another_name_than_the_id_is_not_overwritten(ui):
    row = ui.stored(_manifest("mine"), dir_name="folder-name")
    broken = ui.mount("folder-name", "{ half-edited")

    ui.reload(row)

    assert broken.joinpath("plugin.json").read_text() == "{ half-edited"


def test_an_installed_plugin_is_restored_over_a_broken_directory(ui):
    row = ui.stored(_manifest("fetched"), method="scheduler")
    ui.mount("fetched", "{ junk")

    ui.reload(row)

    assert json.loads(ui.EXTERNAL_PLUGINS_PATH.joinpath("fetched", "plugin.json").read_text())["id"] == "fetched"


def test_a_stored_plugin_whose_directory_name_is_not_its_id_is_not_swept_after_extraction(ui):
    row = ui.stored(_manifest("mine"), dir_name="folder-name")

    ui.reload(row)

    assert ui.EXTERNAL_PLUGINS_PATH.joinpath("folder-name", "plugin.json").is_file()


def test_nothing_is_called_valid_when_the_validator_cannot_be_built(ui, tmp_path):
    ui.PLUGIN_VALIDATOR = None
    ui.CORE_PLUGINS_PATH = tmp_path / "nowhere" / "core"  # no settings.json beside it
    broken = ui.mount("broken", "{ typo")
    valid = ui.mount("valid", _manifest("valid"))

    ui.reload()

    assert broken.is_dir() and valid.is_dir()
