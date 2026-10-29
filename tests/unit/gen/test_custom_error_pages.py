"""Custom error routing preserves request context and permits static non-GET pages."""

import re
import shutil
import subprocess
from pathlib import Path

import jinja2
import pytest

TEMPLATE = Path(__file__).resolve().parents[3] / "src/common/core/errors/confs/server-http/errors.conf"
LUA = shutil.which("lua") or shutil.which("luajit")


def render(**overrides):
    settings = dict(ERRORS="403=/blocked.html", INTERCEPTED_ERROR_CODES="400 403 404", ROOT_FOLDER="", MULTISITE="yes", SERVER_NAME="app.example alias")
    settings.update(overrides)
    env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    return env.from_string(TEMPLATE.read_text()).render(**settings)


@pytest.mark.parametrize("code", ["401", "403", "404", "429", "500"])
@pytest.mark.parametrize("root", ["", "/srv/pages"])
def test_custom_error_uses_named_location_without_resetting_reason(code, root):
    output = render(ERRORS=f"{code}=/blocked.html", ROOT_FOLDER=root)
    assert f"error_page {code} @bwcustomerror{code};" in output
    block = output.split(f"location @bwcustomerror{code} {{", 1)[1].split("\n}", 1)[0]
    assert "rewrite ^ /blocked.html break;" in block
    assert "set $reason" not in block and "set $ctx_ref" not in block
    assert "modsecurity off;" in block and "auth_basic off;" in block
    assert f"root {root or '/var/www/html/app.example'};" in block
    direct = output.split("location = /blocked.html {", 1)[1].split("}", 1)[0]
    assert "internal;" in direct
    assert f"error_page {code} @bwerror{code};" not in output


@pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "PUT", "DELETE"])
def test_custom_page_rewrite_uses_get_but_preserves_head(method):
    output = render()
    block = re.search(r"rewrite_by_lua_block \{(.*?)\n\s*}", output, re.S)
    assert block is not None, "custom static pages must reset non-HEAD methods"
    program = "local method = '" + method + "'\n"
    program += "ngx = {HTTP_GET = 'GET', req = {get_method = function() return method end, set_method = function(m) method = m end}}\n"
    program += block.group(1) + "\nprint(method)"
    result = subprocess.run([LUA, "-"], input=program, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ("HEAD" if method == "HEAD" else "GET")


def test_400_keeps_uri_target_and_built_in_errors_still_render():
    output = render(ERRORS="400=/bad.html 403=/blocked.html")
    assert "error_page 400 /bad.html;" in output
    assert "@bwcustomerror400" not in output
    assert "error_page 404 @bwerror404;" in output
    assert "error_page 400 /bwerror400;" not in output


def test_empty_custom_errors_leave_default_handlers():
    output = render(ERRORS="")
    assert "@bwcustomerror" not in output
    assert "error_page 400 /bwerror400;" in output
    assert "error_page 403 @bwerror403;" in output
