"""bwcli inside an enrolled bare instance must use its own credential, not the global API_TOKEN.

L-A2 (wave 12): once `/var/lib/bunkerweb/instance-credential.json` exists, api.lua refuses the
global API_TOKEN and answers only to the credential it stores (PO ruling 2026-09-02, see
report-L-A.md §8 Q2 and utils.sh's `redeem_enrollment_code`). `CLI.__init__`'s no-database branch
(a bare `bw` container talking to its own loopback API) still dialed 127.0.0.1 with API_TOKEN
unconditionally, so every bwcli command against such an instance would 401 after enrollment.

Only the no-database, no-BWCLI_API_URL branch is covered here: that is the one this fix touches.
`test_api_token_fallback.py` already covers the database and explicit-URL branches, untouched by
this change.
"""

import logging
import sys
from pathlib import Path as RealPath
from unittest.mock import Mock

import pytest

_ROOT = RealPath(__file__).resolve().parents[3]
for _p in (
    _ROOT / "src" / "common" / "cli",
    _ROOT / "src" / "common" / "api",
    _ROOT / "src" / "common" / "utils",
    _ROOT / "src" / "common" / "db",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import CLI as CLI_MODULE  # noqa: E402

VARIABLES_ENV = ("/", "etc", "nginx", "variables.env")
BW_VARIABLES_ENV = ("/", "etc", "bunkerweb", "variables.env")


def _fake_variables_path_factory():
    """Just enough of pathlib.Path for CLI.__init__'s variables.env read. Mirrors
    test_api_token_fallback.py's stub; kept local so this file has no cross-test dependency."""
    content = "API_TOKEN=the-global-token\n"

    class FakePath:
        def __init__(self, *parts):
            self._parts = tuple(str(p) for p in parts)

        def is_file(self):
            return self._parts == VARIABLES_ENV

        def exists(self):
            # No `/usr/share/bunkerweb/db`: only the no-database branch is under test here.
            return False

        def read_text(self, encoding=None):
            return content

        def as_posix(self):
            return "/".join(self._parts)

    return FakePath


class _FakeCredentialFile:
    """Stands in for CLI_MODULE.INSTANCE_CREDENTIAL_FILE. Tracks whether read_text was even
    called, so the "absent file" tests can prove the is_file() guard actually runs first."""

    def __init__(self, *, present, content=None, read_error=None):
        self._present = present
        self._content = content
        self._read_error = read_error
        self.read_calls = 0

    def is_file(self):
        return self._present

    def read_text(self, encoding=None):
        self.read_calls += 1
        if self._read_error is not None:
            raise self._read_error
        return self._content

    def __str__(self):
        return "/var/lib/bunkerweb/instance-credential.json"


def _build_cli(monkeypatch, credential_file):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("API_SERVER_NAME", raising=False)
    monkeypatch.delenv("BWCLI_API_URL", raising=False)

    fake_path = _fake_variables_path_factory()
    monkeypatch.setattr(CLI_MODULE, "Path", fake_path)
    monkeypatch.setattr(CLI_MODULE, "OPERATOR_VARIABLES_PATHS", (fake_path(*BW_VARIABLES_ENV),))
    monkeypatch.setattr(CLI_MODULE, "GENERATED_VARIABLES_PATHS", (fake_path(*VARIABLES_ENV),))
    monkeypatch.setattr(CLI_MODULE, "VARIABLES_PATHS", (fake_path(*BW_VARIABLES_ENV), fake_path(*VARIABLES_ENV)))
    monkeypatch.setattr(CLI_MODULE, "INSTANCE_CREDENTIAL_FILE", credential_file)
    monkeypatch.setattr(CLI_MODULE, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(CLI_MODULE, "get_redis_client", lambda **kwargs: None)
    monkeypatch.setattr(CLI_MODULE, "get_terminal_size", lambda: Mock(columns=80))

    return CLI_MODULE.CLI()


def _tokens(cli):
    return [api._API__token for api in cli.apis]


def test_a_present_and_readable_credential_file_wins_over_the_global_token(monkeypatch):
    credential_file = _FakeCredentialFile(present=True, content='{"credential": "instance-own-credential", "code_fingerprint": "abc"}')
    cli = _build_cli(monkeypatch, credential_file)
    assert _tokens(cli) == ["instance-own-credential"]
    assert credential_file.read_calls == 1


def test_an_absent_credential_file_falls_back_to_the_global_token_without_reading(monkeypatch):
    """The normal, unenrolled case: no warning, and the guard must not even attempt the read."""
    credential_file = _FakeCredentialFile(present=False)
    cli = _build_cli(monkeypatch, credential_file)
    assert _tokens(cli) == ["the-global-token"]
    assert credential_file.read_calls == 0


def test_an_unreadable_credential_file_falls_back_and_warns_once(monkeypatch, caplog):
    """`logger.py` reassigns WARNING's `levelname` to an emoji (`addLevelName`), so this filters
    by `levelno` rather than the now-cosmetic `levelname` string."""
    credential_file = _FakeCredentialFile(present=True, read_error=OSError("permission denied"))
    with caplog.at_level(logging.WARNING, logger="CLI"):
        cli = _build_cli(monkeypatch, credential_file)
    assert _tokens(cli) == ["the-global-token"]
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "instance-credential.json" in warnings[0].message


def test_malformed_json_in_the_credential_file_falls_back_and_warns(monkeypatch, caplog):
    credential_file = _FakeCredentialFile(present=True, content="not json at all")
    with caplog.at_level(logging.WARNING, logger="CLI"):
        cli = _build_cli(monkeypatch, credential_file)
    assert _tokens(cli) == ["the-global-token"]
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_a_credential_file_without_a_credential_key_falls_back(monkeypatch):
    """A file that exists but was never actually populated (e.g. a torn write caught mid-way in
    some future edit) must not silently authenticate with `null`."""
    credential_file = _FakeCredentialFile(present=True, content="{}")
    cli = _build_cli(monkeypatch, credential_file)
    assert _tokens(cli) == ["the-global-token"]


def test_non_utf8_bytes_in_the_credential_file_fall_back_and_warn(monkeypatch, caplog):
    """`read_text(encoding="utf-8")` on a corrupt/binary file raises UnicodeDecodeError, a
    ValueError subclass, not an OSError or JSONDecodeError. The except tuple must catch it too, or
    a corrupt credential file kills every bwcli command (including `bwcli unban` mid-incident)
    with a traceback instead of the documented warn-and-fall-back."""
    credential_file = _FakeCredentialFile(present=True, read_error=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
    with caplog.at_level(logging.WARNING, logger="CLI"):
        cli = _build_cli(monkeypatch, credential_file)
    assert _tokens(cli) == ["the-global-token"]
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_the_credential_file_path_matches_utils_sh_and_api_lua(monkeypatch):
    """Nothing else pins this constant against the other two languages that hardcode the same
    path (utils.sh's INSTANCE_CREDENTIAL_FILE default, api.lua's own literal); every other test
    here monkeypatches the constant away entirely, so a rename on either side would otherwise
    degrade silently to "global token -> 401" with no test failure."""
    assert CLI_MODULE.INSTANCE_CREDENTIAL_FILE.as_posix() == "/var/lib/bunkerweb/instance-credential.json"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
