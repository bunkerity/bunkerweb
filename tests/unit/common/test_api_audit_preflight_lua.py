"""``check_audit_storage`` in ``api.lua``: the ModSecurity audit preflight the instance API runs (port of dev 4b00bfb15).

``POST /reload`` and ``POST /confs`` run ``modsecurity_audit.py`` against the live (or the staged)
``variables.env`` before they touch nginx. The helper must answer "valid" ONLY for the script's exact success
line: an empty read, a traceback or a refusal all mean "do not reload". Runs the real function through the ``lua``
binary with ``io.popen`` replaced, the way ``test_modsecurity_body_reason_lua.py`` runs ``get_reason``.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

SUCCESS = "ModSecurity audit preflight successful\\n"


def function_source() -> str:
    text = API_LUA.read_text(encoding="utf-8")
    chunk = re.search(r"^local function check_audit_storage\(variables_path\)$.*?^end$", text, re.S | re.M)
    assert chunk, "check_audit_storage was not found in api.lua -- renamed or restructured?"
    return chunk.group(0)


def run(popen_body: str, path: str = "/etc/nginx/variables.env") -> list:
    script = "\n".join(
        [
            "local commands = {}",
            f"io.popen = function(command) commands[#commands + 1] = command; {popen_body} end",
            function_source(),
            f'local valid, detail = check_audit_storage("{path}")',
            'print(tostring(valid), (detail or ""):gsub("\\n", "|"), commands[1] or "")',
        ]
    )
    result = subprocess.run([str(LUA), "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.rstrip("\n").split("\t")


@needs_lua
class TestCheckAuditStorage:
    def test_the_exact_success_line_is_valid(self):
        valid, detail, command = run(f'return {{ read = function() return "{SUCCESS}" end, close = function() end }}')[:3]
        assert valid == "true"
        assert detail.startswith("ModSecurity audit preflight successful")
        assert "/usr/share/bunkerweb/utils/modsecurity_audit.py" in command
        assert "'/etc/nginx/variables.env'" in command
        assert command.rstrip().endswith("2>&1"), "stderr must reach the answer, it carries the reason"

    def test_a_refusal_is_invalid_and_carries_the_reason(self):
        refusal = "ModSecurity audit preflight failed: MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR is required\\n"
        valid, detail = run(f'return {{ read = function() return "{refusal}" end, close = function() end }}')[:2]
        assert valid == "false"
        assert "is required" in detail

    @pytest.mark.parametrize("answer", ["", "Traceback (most recent call last):\\n", "ModSecurity audit preflight successful\\nextra\\n"])
    def test_anything_but_the_success_line_is_invalid(self, answer):
        assert run(f'return {{ read = function() return "{answer}" end, close = function() end }}')[0] == "false"

    def test_a_missing_interpreter_is_invalid(self):
        valid, detail = run("return nil")[:2]
        assert valid == "false"
        assert "cannot run" in detail

    def test_the_staged_path_is_passed_through(self):
        command = run(f'return {{ read = function() return "{SUCCESS}" end, close = function() end }}', "/etc/nginx/.bw-staging/variables.env")[2]
        assert "'/etc/nginx/.bw-staging/variables.env'" in command
