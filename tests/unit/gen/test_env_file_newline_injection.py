"""A multi-line ``file`` setting must not be able to declare other settings in ``variables.env`` (SEC-03).

``has_embedded_newline`` exempts ``type: file`` settings, so their newlines reach the writers. The
writers used to emit ``KEY=value`` raw, which made every later line of the value a line of the file:
``init_by_lua`` and ``api.lua`` read it line by line (``API_TOKEN`` included), and the Python reader
ends a value at any key it knows. The writers now encode such a value on one line and the Python reader
decodes it, so what the Lua readers see is a single ``KEY=`` line.
"""

import logging
import re
from pathlib import Path

import pytest

import env_file
from env_file import make_key_predicate, parse_env_file, parse_env_lines

# getattr: the behavioural tests below must run, and fail, against a tree that has no encoder yet.
ENV_B64_PREFIX = getattr(env_file, "ENV_B64_PREFIX", "bw-b64:")

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"

PAYLOADS = {
    "pem_with_known_key_inside": "-----BEGIN CERTIFICATE-----\nQUJDRA==\nAPI_TOKEN=evil\n-----END CERTIFICATE-----",
    "pem_then_known_key_after": "-----BEGIN CERTIFICATE-----\nQUJD\n-----END CERTIFICATE-----\nUSE_ANTIBOT=captcha",
    "wrapped_base64_then_known_key": "QUJD\nRA==\nAPI_TOKEN=evil",
    "interior_and_trailing_newline": "QUJD\nRA==\n",
    "crlf": "-----BEGIN CERTIFICATE-----\r\nQUJD\r\nAPI_TOKEN=evil\r\n-----END CERTIFICATE-----\r\n",
    "backslashes_and_prefix": f"{ENV_B64_PREFIX}\\n\nAPI_TOKEN=evil",
}


def _args(tmp_path):
    for name in ("external", "pro"):
        (tmp_path / name).mkdir(exist_ok=True)
    return str(SETTINGS), str(CORE), str(tmp_path / "external"), str(tmp_path / "pro")


def _config(tmp_path, payload):
    from Configurator import Configurator  # type: ignore

    variables = {"SERVER_NAME": "www.example.com", "MULTISITE": "no", "CUSTOM_SSL_CERT_DATA": payload}
    return Configurator(*_args(tmp_path), variables, logging.getLogger("sec03")).get_config(None)


@pytest.fixture
def written(tmp_path, monkeypatch):
    """Render ``variables.env`` for a payload with the real Templator writer."""
    import Templator as T  # type: ignore

    monkeypatch.setattr(T, "sep", str(tmp_path))
    output = tmp_path / "out"
    output.mkdir()

    def write(payload):
        config = _config(tmp_path, payload)
        T.Templator(
            str(CONFS), str(CORE), str(tmp_path / "external"), str(tmp_path / "pro"), str(output), "/etc/nginx", config, config.copy(), config.copy()
        )._write_config()
        return config, output / "variables.env"

    return write


@pytest.mark.parametrize("payload", PAYLOADS.values(), ids=PAYLOADS.keys())
def test_lua_style_line_readers_see_only_declared_settings(written, payload):
    """``init-lua.conf`` and ``api.lua`` match ``^([^=]+)=(.*)$`` per line: no value line may qualify."""
    config, path = written(payload)
    seen = {}
    for line in path.read_text().split("\n"):
        match = re.match(r"^([^=]+)=(.*)$", line)
        if match:
            seen[match.group(1)] = match.group(2)
    assert set(seen) == set(config)
    assert seen["API_TOKEN"] == config["API_TOKEN"]
    assert seen["USE_ANTIBOT"] == config["USE_ANTIBOT"]
    assert "evil" not in seen["API_TOKEN"]


@pytest.mark.parametrize("payload", PAYLOADS.values(), ids=PAYLOADS.keys())
def test_configurator_reads_the_value_back_whole_and_no_other_setting(tmp_path, written, payload):
    from Configurator import Configurator  # type: ignore

    config, path = written(payload)
    actual = Configurator(*_args(tmp_path), str(path), logging.getLogger("sec03")).get_config(None)
    assert actual["CUSTOM_SSL_CERT_DATA"] == payload
    assert actual["API_TOKEN"] == config["API_TOKEN"]
    assert actual["USE_ANTIBOT"] == config["USE_ANTIBOT"]


@pytest.mark.parametrize("payload", PAYLOADS.values(), ids=PAYLOADS.keys())
def test_bare_parser_round_trips_byte_exactly(written, payload):
    config, path = written(payload)
    parsed = parse_env_file(path)
    assert parsed["CUSTOM_SSL_CERT_DATA"] == payload
    assert set(parsed) == set(config)


def test_trailing_line_breaks_alone_are_written_and_read_as_before():
    """A ConfigMap block scalar ends in a newline: it must still read back stripped, never as ``val\\n``."""
    assert env_file.format_env_line("K", "val\n") == "K=val\n"
    assert parse_env_lines(["K=val", "", "OTHER=1"]) == {"K": "val", "OTHER": "1"}


def test_format_env_line_leaves_single_line_values_alone():
    assert env_file.format_env_line("USE_ANTIBOT", "captcha") == "USE_ANTIBOT=captcha"
    assert env_file.format_env_line("X", "a=b\\c") == "X=a=b\\c"
    assert env_file.format_env_line("X", "") == "X="


@pytest.mark.parametrize("value", ["\nlead", "a\nb", "a\rb", "a\r\nb\r\n", f"{ENV_B64_PREFIX}abc", "é\nü"])
def test_format_env_line_is_one_line_and_reversible(value):
    line = env_file.format_env_line("KEY", value)
    assert "\n" not in line and "\r" not in line
    assert parse_env_lines([line])["KEY"] == value


def test_a_file_written_by_rc4_still_reads_the_same():
    """Raw multi-line PEM, as rc4 wrote it, is folded by the existing rules and never decoded."""
    lines = [
        "SERVER_NAME=www.example.com",
        "CUSTOM_SSL_CERT_DATA=-----BEGIN CERTIFICATE-----",
        "QUJDRA==",
        "-----END CERTIFICATE-----",
        "USE_ANTIBOT=captcha",
        "MY_PATTERN=\\d+\\n",
    ]
    parsed = parse_env_lines(lines)
    assert parsed["CUSTOM_SSL_CERT_DATA"] == "-----BEGIN CERTIFICATE-----\nQUJDRA==\n-----END CERTIFICATE-----"
    assert parsed["USE_ANTIBOT"] == "captcha"
    assert parsed["MY_PATTERN"] == "\\d+\\n"


def test_a_malformed_encoded_value_is_kept_as_written():
    assert parse_env_lines([f"KEY={ENV_B64_PREFIX}***not base64***"])["KEY"] == f"{ENV_B64_PREFIX}***not base64***"


def test_predicate_helpers_still_see_the_encoded_key():
    parsed = parse_env_lines(
        [env_file.format_env_line("CUSTOM_SSL_CERT_DATA", "a\nAPI_TOKEN=evil"), "API_TOKEN=real"],
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"API_TOKEN", "CUSTOM_SSL_CERT_DATA"}),
    )
    assert parsed == {"CUSTOM_SSL_CERT_DATA": "a\nAPI_TOKEN=evil", "API_TOKEN": "real"}
