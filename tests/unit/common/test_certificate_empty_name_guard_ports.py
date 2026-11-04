"""Certificate-provider init must finish cleanly when the global service roster is empty."""

import shutil
import subprocess

import pytest

from test_init_empty_server_name_guards_lua import HARNESS, PLUGINS

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


def run_provider(plugin, server_name):
    path, extras, _ = PLUGINS[plugin]
    variables = "{ " + ", ".join(f'["{key}"] = "{value}"' for key, value in extras.items()) + " }"
    preamble = (
        f"SERVER_NAME = [==[{server_name}]==]\nVARIABLES = {variables}\n"
        'package.loaded["bunkerweb.acme"] = {}\n'
        'package.loaded["resty.env"] = { set = function() end }\n'
        'package.loaded["resty.openssl.x509"] = {}\n'
    )
    return subprocess.run(["lua", "-e", preamble + HARNESS % {"lua": str(path)}], capture_output=True, text=True)


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
@pytest.mark.parametrize("server_name", ["", "   "])
def test_empty_roster_refuses_without_raising_or_reading_a_service_certificate(plugin, server_name):
    result = run_provider(plugin, server_name)
    assert result.returncode == 0, result.stderr
    assert "RET=false" in result.stdout
    assert "MSG=no server name configured" in result.stdout
    assert "SERVER_NAME is empty" in result.stdout
    assert "READ=" not in result.stdout


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
def test_configured_roster_still_reads_the_first_service_certificate(plugin):
    result = run_provider(plugin, "www.example.com alias.example.com")
    assert result.returncode == 0, result.stderr
    assert PLUGINS[plugin][2] % "www.example.com" in result.stdout
