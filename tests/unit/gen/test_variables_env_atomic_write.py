"""``variables.env`` must be REPLACED, never rewritten in place.

The file is read off disk outside the render, by readers the render does not coordinate with:
``src/bw/entrypoint.sh`` feeds it to ``gen/main.py --variables``, ``init_by_lua`` parses it at
reload, and since the 19g fallback ``src/bw/lua/bunkerweb/api.lua`` reads ``API_TOKEN`` and the
whitelist straight out of it when the internalstore comes up empty. On All-in-one and on the Linux
package the renderer writes the *live* ``/etc/nginx``, so a reader can land mid-write --
``Path.write_text`` truncates first, and the window it opens is one where the file parses fine and
is simply missing its tail.

A rename cannot be observed half-done: a reader holds either the whole old file or the whole new
one. The observable proxy for that here is the inode -- an in-place rewrite keeps it, a rename
gives the path a new one.
"""

import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"


@pytest.fixture
def templator(tmp_path, monkeypatch):
    import Templator as T  # type: ignore  (src/common/gen is on sys.path, see conftest)
    from Configurator import Configurator  # type: ignore

    monkeypatch.setattr(T, "sep", str(tmp_path))
    output = tmp_path / "out"
    output.mkdir()
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    pro_plugins = tmp_path / "pro-plugins"
    pro_plugins.mkdir()

    variables = {"SERVER_NAME": "www.example.com", "MULTISITE": "no"}
    config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("variables-env")).get_config(None)
    return T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()), output


def test_a_rewrite_replaces_the_file_instead_of_truncating_it(templator):
    instance, output = templator
    target = output / "variables.env"

    instance._write_config()
    first = target.stat()
    assert "SERVER_NAME=www.example.com\n" in target.read_text()

    instance._write_config()

    assert target.stat().st_ino != first.st_ino, "variables.env was rewritten in place -- a concurrent reader can see it truncated"
    assert "SERVER_NAME=www.example.com\n" in target.read_text(), "the replacement lost the content it was supposed to carry"


def test_no_temporary_file_is_left_in_the_pushed_tree(templator):
    """Whatever the write uses as scratch must not survive: ``push-configs`` copies this whole
    directory into the ``/confs`` tar, so a leftover would ship to every instance."""
    instance, output = templator

    instance._write_config()

    assert sorted(path.name for path in output.iterdir()) == ["variables.env"]
