"""Run the real metrics query method against values containing pane separators."""

import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import pytest

LUA = shutil.which("lua") or shutil.which("luajit")
METRICS = Path(__file__).resolve().parents[3] / "src/common/core/metrics/metrics.lua"


@pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
@pytest.mark.parametrize("protocol", ["http", "tcp", "udp"])
def test_instance_query_keeps_encoded_separators_inside_values(protocol):
    value = "/path,a;b?x=<tag>&literal=%3B+é"
    source = re.search(r"^function metrics:api_requests_query\(\).*?^end$", METRICS.read_text(), re.M | re.S).group()
    script = """
local metrics = {}
local table_insert = table.insert
local HTTP_OK = 200
local function unescape_uri(value)
    return (value:gsub('%%(%x%x)', function(hex) return string.char(tonumber(hex, 16)) end))
end
local args = { search_panes = [==[url:PANE]==] }
local ngx = { req = { get_uri_args = function() return args end } }
local row = { id = 'keep', date = 1, protocol = 'PROTOCOL', url = [==[VALUE]==] }
local function collect_buffered_requests() return { row } end
local function is_report() return true end
""".replace("PANE", quote(value, safe="")).replace("PROTOCOL", protocol).replace("VALUE", value)
    script += source + """
local result = metrics.api_requests_query({ ret = function(_, _, msg) return msg end })
assert(result.filtered == 1, 'pane value split or decoded before splitting')
assert(result.data[1].url == row.url)
assert(result.pane_counts.url[row.url].count == 1)
"""
    result = subprocess.run([LUA, "-"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
