"""BunkerNet's log phase must not call the HTTP-only request API when it runs for a stream service.

``bunkernet:log`` built every report with ``ngx.req.get_headers()``, which does not exist in the stream subsystem, so a
denied stream connection raised an error in ``log_stream`` instead of being reported. The report now carries an empty
header map for non-HTTP requests. This test runs the real ``bunkernet:log_stream`` with ``ngx.req.get_headers`` set to fail
if called, and the HTTP path to prove headers are still reported there.
Refs: #2584, #2516.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HEADER = r"""
package.loaded["resty.http"] = { new = function() return {} end }
VARIABLES = { MAX_HEADERS = "100" }
UTILS = {
    get_reason = function() return "country", { id = "country" }, "block" end,
    is_whitelisted = function() return false end,
    get_variable = function() return "100" end,
}
"""


def report(kind):
    return run_plugin_script(
        "bunkernet",
        f"""
HEADERS_CALLED = 0
ngx.req.get_headers = function() HEADERS_CALLED = HEADERS_CALLED + 1 if "{kind}" == "stream" then error("ngx.req.get_headers is HTTP-only") end return {{ ["user-agent"] = "curl" }} end
ngx.time = function() return 1000 end
local plugin = PLUGIN:new({{ bw = {{ kind = "{kind}", ip_is_global = true, remote_addr = "198.51.100.7", server_name = "app.example.com",
                                      request_method = "GET", request_uri = "/x" }} }})
plugin.bunkernet_id = "instance"
local r = plugin:log(true)
local sent = RPUSHES[1] and json.decode(RPUSHES[1].value) or {{}}
local count = 0
for _ in pairs(sent.headers or {{}}) do count = count + 1 end
emit({{ msg = r.msg, ret = r.ret, headers_called = HEADERS_CALLED, header_count = count, ip = sent.ip or "none", ua = (sent.headers or {{}})["user-agent"] or "none" }})
""",
        header=HEADER,
    )


def test_a_denied_stream_connection_is_reported_without_touching_the_http_request_api():
    out = report("stream")
    assert out["ret"] is True
    assert out["msg"] == "IP added to reports"
    assert out["headers_called"] == 0
    assert out["header_count"] == 0
    assert out["ip"] == "198.51.100.7"


def test_a_denied_http_request_still_reports_its_headers():
    out = report("http")
    assert out["msg"] == "IP added to reports"
    assert out["headers_called"] == 1
    assert out["ua"] == "curl"
