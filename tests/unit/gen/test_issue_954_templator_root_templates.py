"""A template that sits directly in a context directory of the confs tree is rendered as a root config of its server.

`Templator` rendered a fixed list of root templates under their own name (`server.conf`, `access-lua.conf`, …) and
every other `confs/<context>/*.conf` of the tree under `<context>/<name>`, so a root template that was not in the
list was written where nginx never included it ("missing configuration file"). The set now comes from the tree
itself. A marker template that no list could know about is added to a copy of the shipped confs. Refs #954.
"""

import logging
import shutil
from pathlib import Path

import pytest

from _t4_helpers import CONFS, CORE, SETTINGS  # type: ignore

MARKER = "zz-root-marker.conf"


@pytest.fixture
def render(tmp_path, monkeypatch):
    import Templator as T  # type: ignore
    from Configurator import Configurator  # type: ignore

    monkeypatch.setattr(T, "sep", str(tmp_path))  # the Jinja bytecode cache goes under tmp_path, not /var/cache
    confs = tmp_path / "confs"
    shutil.copytree(CONFS, confs)
    (confs / "server-http" / MARKER).write_text("# marker {{ SERVER_NAME }}\n")
    plugins = tmp_path / "plugins"
    pro_plugins = tmp_path / "pro-plugins"
    plugins.mkdir()
    pro_plugins.mkdir()

    def _render(**variables):
        output = Path(tmp_path, f"out{len(list(tmp_path.glob('out*')))}")
        output.mkdir()
        config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("t5-templator")).get_config(None)
        T.Templator(str(confs), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()).render()
        return output

    return _render


def test_a_root_template_outside_any_fixed_list_is_rendered_at_the_server_root(render):
    output = render(SERVER_NAME="www.example.com")

    assert (output / MARKER).is_file(), sorted(path.name for path in output.glob("*.conf"))
    assert (output / MARKER).read_text() == "# marker www.example.com\n"
    assert not (output / "server-http" / MARKER).exists()


def test_the_root_template_follows_its_service_in_multisite(render):
    output = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com")

    assert (output / "a.example.com" / MARKER).is_file()
    assert (output / "a.example.com" / MARKER).read_text() == "# marker a.example.com\n"
    assert (output / "b.example.com" / MARKER).read_text() == "# marker b.example.com\n"
    assert not (output / "a.example.com" / "server-http" / MARKER).exists()


def test_a_plugin_template_keeps_its_context_directory(render):
    output = render(SERVER_NAME="www.example.com")

    assert (output / "server-http" / "reverse-proxy.conf").is_file()
    assert not (output / "reverse-proxy.conf").exists()
