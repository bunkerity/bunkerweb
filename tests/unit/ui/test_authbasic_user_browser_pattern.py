"""The browser refuses a CR or LF in ``AUTH_BASIC_USER`` too, a terminal one included.

The server side (Python ``re`` and ``regex``) is covered by ``tests/unit/gen/test_authbasic_user_regex.py``. The
browser gets the regex as an HTML ``pattern`` (Python spelling through ``v_safe_pattern``, JS spelling
through ``vSafePattern``), anchored as ``^(?:...)$`` and compiled with the ``v`` flag.
"""

import json
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

from app.html_pattern import v_safe_pattern

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src" / "common" / "core" / "authbasic" / "plugin.json"
SETTING_CONTROLS = ROOT / "src" / "ui" / "app" / "static" / "js" / "modules" / "setting_controls.js"
USER_REGEX = json.loads(PLUGIN.read_text(encoding="utf-8"))["settings"]["AUTH_BASIC_USER"]["regex"]

VALID_USERS = ["alice", "bob smith", "a.b-c_d@example.com"]
INVALID_USERS = ["alice\n", "alice\r", "alice\r\n", "al\nice", "al\rice", "\nalice", "", "al:ice"]

NODE = r"""
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [modulePath, inputPath] = process.argv.slice(1);
const { vSafePattern } = await import(pathToFileURL(modulePath).href);
const { regex, samples, pythonPattern } = JSON.parse(readFileSync(inputPath, "utf8"));
const jsPattern = vSafePattern(regex);
const verdicts = (pattern) => {
  const browser = new RegExp(`^(?:${pattern})$`, "v");
  new RegExp(pattern); // page scripts re-test `pattern` without the v flag
  return samples.map((sample) => browser.test(sample));
};
process.stdout.write(JSON.stringify({ jsPattern, js: verdicts(jsPattern), python: verdicts(pythonPattern) }));
"""


@pytest.mark.skipif(which("node") is None, reason="node is not installed")
def test_the_browser_pattern_accepts_a_normal_user_and_refuses_any_cr_or_lf(tmp_path):
    samples = VALID_USERS + INVALID_USERS
    python_pattern = v_safe_pattern(USER_REGEX)
    assert python_pattern, "the regex must keep a browser pattern"
    payload = tmp_path / "in.json"
    payload.write_text(json.dumps({"regex": USER_REGEX, "samples": samples, "pythonPattern": python_pattern}))
    result = run(["node", "--input-type=module", "-e", NODE, str(SETTING_CONTROLS), str(payload)], capture_output=True, text=True, check=True, cwd=tmp_path)
    out = json.loads(result.stdout)
    expected = [True] * len(VALID_USERS) + [False] * len(INVALID_USERS)
    assert out["jsPattern"] == python_pattern
    assert out["js"] == expected
    assert out["python"] == expected
