"""Every value the shipped regex of a duration setting accepts is a value the parser reads.

The 28 settings of dev 3075b9d16 keep the 1.6.16 regex so that 1.7 accepts what 1.6.16 stored. A
regex that is wider than the parser turns a rejected value into a worse one (a permanent ban, an
antibot error), so this walks the shipped ``plugin.json`` files rather than a copy of the regexes.
The unit of each setting is the unit its reader passes to the parser.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import common_utils

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"
DURATION_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "duration.lua"
VECTORS = json.loads((ROOT / "tests" / "unit" / "fixtures" / "duration_vectors.json").read_text())
LUA = shutil.which("lua") or shutil.which("luajit")

# setting -> native unit (family.out of W25-SETCOMPAT, the unit each reader passes)
NATIVE = {
    "ANTIBOT_TIME_RESOLVE": "s",
    "ANTIBOT_TIME_VALID": "s",
    "BAD_BEHAVIOR_BAN_TIME": "s",
    "BAD_BEHAVIOR_COUNT_TIME": "s",
    "CORS_MAX_AGE": "s",
    "CROWDSEC_APPSEC_CONNECT_TIMEOUT": "ms",
    "CROWDSEC_APPSEC_PROCESS_TIMEOUT": "ms",
    "CROWDSEC_APPSEC_SEND_TIMEOUT": "ms",
    "CROWDSEC_CACHE_EXPIRATION": "s",
    "CROWDSEC_REQUEST_TIMEOUT": "ms",
    "CROWDSEC_UPDATE_FREQUENCY": "s",
    "DATABASE_MAX_SESSION_AGE_DAYS": "d",
    "DATABASE_POOL_RECYCLE": "s",
    "DATABASE_POOL_TIMEOUT": "s",
    "DATABASE_REQUEST_RETRY_DELAY": "s",
    "DATABASE_RETRY_TIMEOUT": "s",
    "LETS_ENCRYPT_DNS_PROPAGATION": "s",
    "LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT": "s",
    "LETS_ENCRYPT_ZEROSSL_API_MAX_TIME": "s",
    "LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY": "s",
    "METRICS_REDIS_TTL": "s",
    "REDIS_KEEPALIVE_IDLE": "ms",
    "REDIS_TIMEOUT": "ms",
    "REVERSE_SCAN_TIMEOUT": "ms",
    "SELF_SIGNED_SSL_EXPIRY": "d",
    "SESSIONS_ABSOLUTE_TIMEOUT": "s",
    "SESSIONS_IDLING_TIMEOUT": "s",
    "SESSIONS_ROLLING_TIMEOUT": "s",
}
# Values of these settings that are valid but are not durations; their readers handle them first.
NOT_A_DURATION = {"DATABASE_POOL_RECYCLE": {"-1"}, "LETS_ENCRYPT_DNS_PROPAGATION": {"default"}}
# Settings read in Lua, which only parses whole numbers.
LUA_READ = {name for name in NATIVE if name.split("_")[0] in {"ANTIBOT", "BAD", "CORS", "SESSIONS", "REVERSE", "METRICS", "REDIS"}}

# ASCII only: the 1.6.16 regex uses \d, which also matches other scripts' digits (the full-width
# "１２" vector), and no parser reads those. Residual, reported with this lane.
CANDIDATES = sorted(
    {value for value, _, _ in VECTORS if value.isascii()} | {"0.25", "1.5s", "250ms", "1m", "1M", "30m", "1y", "-1", "default", "10", "100ms", "7d"}
)


def _settings():
    found = {}
    for path in sorted(CORE.glob("*/plugin.json")):
        for name, setting in json.loads(path.read_text()).get("settings", {}).items():
            if name in NATIVE:
                found[name] = setting
    return found


SETTINGS = _settings()


def test_all_28_settings_are_present():
    assert sorted(SETTINGS) == sorted(NATIVE)
    assert len(NATIVE) == 28


@pytest.mark.parametrize("name", sorted(NATIVE))
def test_the_regex_accepts_the_1616_forms(name):
    setting = SETTINGS[name]
    assert setting["type"] == "text", "a number or duration type would canonicalize the stored value"
    for value in ("30", "2h"):
        assert re.search(setting["regex"], value), f"{name} must accept {value}"
    assert re.search(setting["regex"], setting["default"]), f"{name} rejects its own default {setting['default']}"


@pytest.mark.parametrize("name", sorted(NATIVE))
def test_the_python_parser_reads_every_accepted_value(name):
    regex = SETTINGS[name]["regex"]
    for value in CANDIDATES:
        if value in NOT_A_DURATION.get(name, ()) or not re.search(regex, value):
            continue
        common_utils.parse_duration_int(value, NATIVE[name])
    default = SETTINGS[name]["default"]
    if default not in NOT_A_DURATION.get(name, ()):
        common_utils.parse_duration_int(default, NATIVE[name])


@pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
def test_the_lua_parser_reads_every_accepted_value(tmp_path):
    pairs = []
    for name in sorted(LUA_READ):
        regex = SETTINGS[name]["regex"]
        for value in CANDIDATES + [SETTINGS[name]["default"]]:
            if value not in NOT_A_DURATION.get(name, ()) and re.search(regex, value):
                pairs.append((name, value, NATIVE[name]))
    script = tmp_path / "parity.lua"
    rows = ",\n".join("{%s, %s, %s}" % (json.dumps(n), json.dumps(v), json.dumps(u)) for n, v, u in pairs)
    script.write_text(f"""
local parse = dofile(arg[1]).parse_duration
local bad = {{}}
for _, row in ipairs({{ {rows} }}) do
    if parse(row[2], row[3]) == nil then bad[#bad + 1] = row[1] .. "=" .. row[2] end
end
print(#bad == 0 and "OK" or table.concat(bad, " "))
""")
    out = subprocess.run([LUA, str(script), str(DURATION_LUA)], capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "OK", out.stdout + out.stderr
    assert len(pairs) > 100


# \d matches any Unicode decimal digit in Python's re: "１d" (full-width) or "٣h" (Arabic-Indic) would pass
# validation, Lua would read nil, and BAD_BEHAVIOR_BAN_TIME would turn into a permanent ban.
NON_ASCII_DIGIT_VALUES = ("１d", "٣h", "１２", "٣", "1２s", "5٣")


@pytest.fixture(scope="module")
def configurator_check():
    import logging

    gen = str(ROOT / "src" / "common" / "gen")
    if gen not in sys.path:
        sys.path.insert(0, gen)
    from Configurator import Configurator  # type: ignore

    logger = logging.getLogger("duration-ascii-digits")
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.CRITICAL)
    configurator = Configurator(str(ROOT / "src" / "common" / "settings.json"), str(CORE), [], [], {}, logger)
    check = configurator._Configurator__check_var

    def accepted(name, value):
        configurator._Configurator__variables = {name: value}
        return check(name)[0]

    return accepted


@pytest.mark.parametrize("name", sorted(NATIVE))
def test_the_configurator_rejects_non_ascii_digits(name, configurator_check):
    assert configurator_check(name, "1d" if name != "DATABASE_REQUEST_RETRY_DELAY" else "1s"), "control: an ASCII suffixed value is accepted"
    for value in NON_ASCII_DIGIT_VALUES:
        assert not configurator_check(name, value), f"{name} accepted {value!r}"
