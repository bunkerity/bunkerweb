"""Validate the shipped ALTCHA selector and multisite settings."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SETTINGS = json.loads((Path(__file__).resolve().parents[3] / "src/common/core/antibot/plugin.json").read_text(encoding="utf-8"))["settings"]


def test_altcha_is_opt_in_and_secret_is_server_only():
    mode = SETTINGS["USE_ANTIBOT"]
    assert mode["default"] == "no"
    assert "altcha" in mode["select"] and re.search(mode["regex"], "altcha")
    for name in ("ANTIBOT_ALTCHA_FRONTEND_URL", "ANTIBOT_ALTCHA_BACKEND_URL", "ANTIBOT_ALTCHA_SITEKEY", "ANTIBOT_ALTCHA_SECRET"):
        setting = SETTINGS[name]
        assert setting["context"] == "multisite" and setting["default"] == ""
        assert setting["type"] == ("password" if name == "ANTIBOT_ALTCHA_SECRET" else "text")


@pytest.mark.parametrize("name", ["ANTIBOT_ALTCHA_FRONTEND_URL", "ANTIBOT_ALTCHA_BACKEND_URL"])
def test_altcha_origin_requires_an_authority_only(name):
    regex = SETTINGS[name]["regex"]
    for valid in ("", "https://altcha.example", "https://altcha-1.example.:8443"):
        assert re.search(regex, valid), valid
    is_backend = name == "ANTIBOT_ALTCHA_BACKEND_URL"
    for internal in ("http://verifier:8080", "http://[2001:db8::1]:8443", "http://192.0.2.17"):
        assert bool(re.search(regex, internal)) == is_backend
    for invalid in (
        "https://altcha.example/",
        "https://altcha.example?query",
        "https://altcha.example#fragment",
        "https://user:pass@altcha.example",
        "https://altcha.example:0",
        "https://altcha.example:65536",
        "https://altcha.example\n",
        "https://[bad]",
        "https://altcha.example; script-src *",
    ):
        assert not re.search(regex, invalid), invalid


def test_altcha_https_origins_require_a_dns_hostname():
    backend = SETTINGS["ANTIBOT_ALTCHA_BACKEND_URL"]["regex"]
    frontend = SETTINGS["ANTIBOT_ALTCHA_FRONTEND_URL"]["regex"]
    for host in (
        "192.0.2.17",
        "[2001:db8::1]",
        "192.2.17",
        "3221226001",
        "0300.0.2.17",
        "0xc0000211.",
        "0xc0.0.2.0x11",
        "-verifier.example",
        "verifier-.example",
        "verifier..example",
        "a" * 64 + ".example",
        ".".join(["a" * 63] * 4),
    ):
        assert not re.search(backend, f"https://{host}:8443"), host
        assert not re.search(frontend, f"https://{host}:8443"), host


def test_altcha_sitekey_is_safe_in_a_query_parameter():
    regex = SETTINGS["ANTIBOT_ALTCHA_SITEKEY"]["regex"]
    assert re.search(regex, "key_123-456.example")
    assert not re.search(regex, "key&other=1")
    assert not re.search(regex, "key_123\n")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required to check UI setting validation")
def test_altcha_settings_work_with_the_admin_ui_regexp():
    examples = {
        "ANTIBOT_ALTCHA_FRONTEND_URL": "https://altcha.example",
        "ANTIBOT_ALTCHA_BACKEND_URL": "http://verifier:8080",
        "ANTIBOT_ALTCHA_SITEKEY": "site-key",
        "ANTIBOT_ALTCHA_SECRET": "example-secret",
    }
    cases = [(SETTINGS[name]["regex"], value, True) for name, value in examples.items()]
    backend = SETTINGS["ANTIBOT_ALTCHA_BACKEND_URL"]["regex"]
    cases += [
        (SETTINGS["ANTIBOT_ALTCHA_FRONTEND_URL"]["regex"], "https://[2001:db8::1]", False),
        (backend, "https://verifier.example.:8443", True),
        (backend, "http://[2001:db8::1]:8443", True),
        (backend, "http://192.0.2.17", True),
        (backend, "https://192.0.2.17", False),
        (backend, "https://[2001:db8::1]", False),
        (backend, "https://0xc0000211.", False),
        (backend, "https://verifier-.example", False),
    ]
    subprocess.run(
        [
            "node",
            "-e",
            r"""
const assert = require('node:assert/strict');
for (const [pattern, value, expected] of JSON.parse(process.argv[1])) {
  const regex = new RegExp(pattern);
  assert.equal(regex.test(value), expected, value);
  assert.ok(!regex.test(value + '\n'), value);
}
""",
            json.dumps(cases),
        ],
        check=True,
        timeout=10,
    )
