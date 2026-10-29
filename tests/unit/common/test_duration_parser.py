"""One duration language for the 28 plugin settings, parsed the same way in Python and in Lua.

Dev 3075b9d16 + 192114cdd: units ``ms s m h d w M y``, a bare number takes the setting's native
unit, ``m`` is a minute and ``M`` a month, a non-zero value below the unit floors to 1 and 0 stays 0
(callers read 0 as permanent or disabled). ``tests/unit/fixtures/duration_vectors.json`` is the one
list both parsers must agree on; the Lua side runs it under stand-alone Lua 5.4.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import common_utils

ROOT = Path(__file__).resolve().parents[3]
DURATION_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "duration.lua"
VECTORS = json.loads((ROOT / "tests" / "unit" / "fixtures" / "duration_vectors.json").read_text())

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _python(value, unit):
    try:
        return common_utils.parse_duration_int(value, unit)
    except ValueError:
        return None


@pytest.mark.parametrize(("value", "unit", "expected"), VECTORS, ids=[f"{v}:{u}" for v, u, _ in VECTORS])
def test_python_parser_matches_the_shared_vectors(value, unit, expected):
    assert _python(value, unit) == expected


@needs_lua
def test_lua_parser_matches_the_shared_vectors(tmp_path):
    rows = ",\n".join("{%s, %s, %s}" % (json.dumps(v, ensure_ascii=False), json.dumps(u), "nil" if e is None else e) for v, u, e in VECTORS)
    script = tmp_path / "vectors.lua"
    script.write_text(
        """
local parse = dofile(arg[1]).parse_duration
local failures = {}
for _, row in ipairs({ %s }) do
    local got = parse(row[1], row[2])
    if got ~= row[3] then
        failures[#failures + 1] = string.format("%%s:%%s expected %%s got %%s", row[1], row[2], tostring(row[3]), tostring(got))
    end
end
print(#failures == 0 and "OK" or table.concat(failures, "\\n"))
""" % rows,
        encoding="utf-8",
    )
    out = subprocess.run([LUA, str(script), str(DURATION_LUA)], capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "OK", out.stdout + out.stderr


@needs_lua
def test_lua_parser_is_integers_only_and_nil_safe(tmp_path):
    script = tmp_path / "edge.lua"
    script.write_text(
        'local p = dofile(arg[1]).parse_duration\nprint(tostring(p(nil, "s")), tostring(p("", "s")), tostring(p("1.5", "s")), tostring(p("1d", "x")))\n'
    )
    out = subprocess.run([LUA, str(script), str(DURATION_LUA)], capture_output=True, text=True, timeout=30)
    assert out.stdout.split() == ["nil", "nil", "nil", "nil"], out.stdout + out.stderr


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("2m", "s", 120),
        ("1500ms", "s", 1.5),
        ("250ms", "s", 0.25),
        ("0.5s", "ms", 500),
        ("1.5h", "m", 90),
        (" 1d ", "s", 86400),
        (30, "s", 30),
        ("1y", "d", 365),
    ],
)
def test_python_parse_duration_accepts_decimals_whitespace_and_numbers(value, unit, expected):
    assert common_utils.parse_duration(value, unit) == expected


@pytest.mark.parametrize(("value", "unit", "expected"), [("0.4ms", "s", 1), ("0.0s", "s", 0), ("1.9s", "s", 1), ("2.5m", "s", 150)])
def test_python_int_floor_keeps_non_zero_values_at_one(value, unit, expected):
    assert common_utils.parse_duration_int(value, unit) == expected


@pytest.mark.parametrize("value", ["1" + "0" * 400, "1e400", "nan", "inf"])
def test_python_parser_rejects_out_of_range_numbers(value):
    with pytest.raises(ValueError):
        common_utils.parse_duration(value, "s")


def test_python_parser_rejects_an_unknown_native_unit():
    with pytest.raises(ValueError):
        common_utils.parse_duration("1d", "x")
