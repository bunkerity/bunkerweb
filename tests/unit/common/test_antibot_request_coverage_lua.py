"""Antibot request lifecycle decisions, using the real module and dependency boundaries."""

import hashlib

import pytest
from _lua_plugin_helpers import CORE, LUA, run_module, to_lua

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "antibot" / "antibot.lua"

PREAMBLE = r"""
VARIABLES = {
    USE_ANTIBOT = "javascript", ANTIBOT_URI = "/challenge", ANTIBOT_SUCCESS_URI = "",
    ANTIBOT_TIME_VALID = "60", ANTIBOT_TIME_RESOLVE = "30",
    ANTIBOT_JAVASCRIPT_DIFFICULTY = "16", ANTIBOT_RDNS_GLOBAL = "yes",
    ANTIBOT_CAPJS_FRONTEND_URL = "https://widget.example", ANTIBOT_MCAPTCHA_URL = "https://captcha.example",
}
SESSION_DATA = nil
SESSION = {
    get = function() return SESSION_DATA end,
    set = function(_, key, value) SESSION_DATA = value end,
}
local utils = package.loaded["bunkerweb.utils"]
utils.get_session = function() if SESSION_ERROR then return nil, SESSION_ERROR end return SESSION end
utils.rand = function(len) return string.rep("n", len) end
ngx.now = function() return NOW end
ngx.escape_uri = function(s)
    return (s:gsub("[^%w%-%._~]", function(c) return string.format("%%%02X", c:byte()) end))
end
ngx.req.get_uri_args = function() return URI_ARGS or {} end
ngx.req.get_post_args = function() return POST_ARGS or {}, POST_ERROR end
package.loaded["base64"] = { encode = function(s) return s end }
package.loaded["antibot.captcha"] = { new = function() error("not a CAPTCHA rendering test") end }
package.loaded["resty.sha256"] = {
    new = function()
        local data = ""
        return { update = function(_, s) data = data .. s end, final = function() return SHA256(data) end }
    end,
}
package.loaded["resty.string"] = {
    to_hex = function(s) return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end)) end,
}
package.loaded["resty.http"] = { new = function() error("no external challenge verification") end }
"""


def run(body, setup=""):
    return run_module(MODULE, body, preamble=PREAMBLE + setup)


def test_initialize_decodes_ignore_lists_and_country_case_before_access():
    out = run(r"""
VARIABLES.ANTIBOT_IGNORE_IP = "1.2.3.4 10.0.0.0/8"
VARIABLES.ANTIBOT_IGNORE_URI = "^/health$ ^/assets/"
VARIABLES.ANTIBOT_IGNORE_RDNS = ".example.test"
VARIABLES.ANTIBOT_IGNORE_ASN = "64500"
VARIABLES.ANTIBOT_IGNORE_USER_AGENT = "trusted"
VARIABLES.ANTIBOT_IGNORE_COUNTRY = "fr de"
VARIABLES.ANTIBOT_ONLY_COUNTRY = "us gb"
COUNTRY = "US"
local a = new_plugin(PLUGIN, { ip_is_global = true })
local result = a:access()
emit({ result = result, lists = a.lists, ignore = a.country_ignore, only = a.country_only })
""")
    assert out["result"]["ret"] is True
    assert out["result"]["msg"] == "IP is ignored (info : ip)"
    assert out["lists"]["IGNORE_IP"] == ["1.2.3.4", "10.0.0.0/8"]
    assert out["lists"]["IGNORE_URI"] == ["^/health$", "^/assets/"]
    assert out["lists"]["IGNORE_RDNS"] == [".example.test"]
    assert out["lists"]["IGNORE_ASN"] == ["64500"]
    assert out["lists"]["IGNORE_USER_AGENT"] == ["trusted"]
    assert out["ignore"] == {"FR": True, "DE": True}
    assert out["only"] == {"US": True, "GB": True}


@pytest.mark.parametrize("error, message", [("HEADER_RULES_ERROR", "invalid rules"), ("STORE_SET_ERROR", "store full"), (None, None)])
def test_init_publishes_header_rules_or_reports_failure(error, message):
    setup = f"{error} = {to_lua(message)}\n" if error else ""
    out = run("PHASE = 'init'; local a = new_plugin(PLUGIN); emit({ result = a:init(), store = STORE })", setup)
    assert out["result"]["ret"] is (error is None)
    if error:
        assert out["result"]["msg"] == message
    else:
        assert out["store"]["plugin_antibot_header_rules"] == {"name": "ANTIBOT_IGNORE_HEADER"}


@pytest.mark.parametrize("method", ["access", "header", "content"])
def test_disabled_antibot_leaves_request_alone(method):
    out = run(f"VARIABLES.USE_ANTIBOT = 'no'; emit(new_plugin(PLUGIN):{method}())")
    assert out == {"ret": True, "msg": "antibot not activated"}


def test_access_redirect_carries_path_only_and_marks_cookie_response_uncacheable():
    out = run(r"""
local a = new_plugin(PLUGIN, { uri = "/private/page", request_uri = "/private/page?token=secret", http_accept = "text/html" })
emit({ result = a:access(), headers = ngx.header, session = SESSION_DATA, bw = a.ctx.bw })
""")
    assert out["result"] == {"ret": True, "msg": "redirecting client to the challenge uri", "redirect": "/challenge?next=%2Fprivate%2Fpage"}
    assert out["headers"]["Cache-Control"] == "no-store"
    assert out["session"]["original_uri"] == "/private/page?token=secret"
    assert out["session"]["prepared"] is True
    assert out["session"]["resolved"] is False
    assert out["bw"]["antibot_session_data"] == out["session"]
    assert out["bw"]["sessions_updated"] is True


def test_static_subrequest_cannot_seed_session_destination():
    out = run(r"""
local a = new_plugin(PLUGIN, { uri = "/favicon.ico", request_uri = "/favicon.ico", http_accept = "image/avif" })
local r = a:access()
emit({ result = r, session = SESSION_DATA })
""")
    assert out["result"]["redirect"] == "/challenge"
    assert out["session"] == {}


def test_ignored_asset_bypasses_challenge_even_when_session_unavailable():
    out = run(r"""
VARIABLES.ANTIBOT_IGNORE_URI = "^/assets/"
SESSION_ERROR = "session offline"
local a = new_plugin(PLUGIN, { uri = "/assets/site.css", request_uri = "/assets/site.css?v=2" })
emit({ result = a:access(), cache = CACHE, ttl = CACHE_TTL })
""")
    assert out["result"]["msg"] == "URI is ignored (info : URI ^/assets/)"
    assert "redirect" not in out["result"]
    assert out["ttl"] == 86400


def test_cache_keys_separate_queries_and_cached_ignores_bypass_session():
    out = run(r"""
local a = new_plugin(PLUGIN, { uri = "/page", request_uri = "/page?x=1", http_user_agent = "agent" })
local key = a:kind_to_ele("URI")
a:add_to_cache(key, "URI cached")
local first = a:access()
a.ctx.bw.request_uri = "/page?x=2"
SESSION_ERROR = "session offline"
local second = a:access()
emit({ key = key, first = first, second = second, ip = a:kind_to_ele("IP"), ua = a:kind_to_ele("UA"), country = a:kind_to_ele("COUNTRY") })
""")
    assert out["key"] == "uri#" + hashlib.sha256(b"/page?x=1").hexdigest()
    assert out["first"]["msg"] == "URI is in cached antibot ignored (info : URI cached)"
    assert out["second"] == {"ret": False, "msg": "can't get session : session offline"}
    assert out["ip"] == "ip1.2.3.4"
    assert out["ua"] == "uaagent"
    assert out["country"] == "country1.2.3.4"


@pytest.mark.parametrize("failure", ["CACHE_ERROR", "CACHE_SET_ERROR"])
def test_cache_errors_do_not_exempt_client_and_log_failure(failure):
    out = run(
        "local a = new_plugin(PLUGIN, { uri = '/private', request_uri = '/private' }); emit({ result = a:access(), logs = LOGS })",
        f"{failure} = 'cache offline'\n",
    )
    assert out["result"]["redirect"] == "/challenge?next=%2Fprivate"
    assert any("cache offline" in msg for _, msg in out["logs"])


def test_request_header_exemption_is_not_cached_for_next_request():
    out = run(r"""
local a = new_plugin(PLUGIN, { uri = "/private", request_uri = "/private" })
HEADER_MATCH = "x-health"
local first = a:access()
HEADER_MATCH = nil
local second = a:access()
emit({ first = first, second = second })
""")
    assert out["first"] == {"ret": True, "msg": "header x-health is ignored"}
    assert out["second"]["redirect"] == "/challenge?next=%2Fprivate"


@pytest.mark.parametrize("uri, target", [("/challenge", "/welcome"), ("/page", None)])
def test_valid_resolved_session_redirects_only_on_challenge_endpoint(uri, target):
    out = run(f"""
SESSION_DATA = {{ prepared = true, resolved = true, time_valid = NOW, original_uri = '/deep?x=1' }}
VARIABLES.ANTIBOT_SUCCESS_URI = '/welcome'
local a = new_plugin(PLUGIN, {{ uri = {to_lua(uri)} }})
emit(a:access())
""")
    assert out["ret"] is True
    assert out["msg"] == "client already resolved the challenge"
    assert out.get("redirect") == target


def test_cookie_challenge_resolves_and_redirects_without_document_headers():
    out = run(r"""
VARIABLES.USE_ANTIBOT = "cookie"
URI_ARGS = { next = "/deep" }
local a = new_plugin(PLUGIN, { uri = "/challenge", request_uri = "/challenge?next=%2Fdeep" })
emit({ result = a:access(), session = SESSION_DATA })
""")
    assert out["result"]["redirect"] == "/deep"
    assert out["session"]["resolved"] is True
    assert out["session"]["time_valid"] == 1000000


@pytest.mark.parametrize(
    "session, expected, cleared",
    [
        ({"original_uri": "/stale"}, "not prepared", True),
        ({"resolved": True, "time_valid": 999939}, "need new resolve", True),
        ({"resolved": True, "time_valid": 1000001}, "need new resolve", True),
        ({"resolved": False, "time_resolve": 999969}, "need new prepare", True),
        ({"resolved": False, "time_resolve": 1000001}, "need new prepare", True),
        ({"resolved": True, "time_valid": 999940}, "valid", False),
        ({"resolved": False, "time_resolve": 999970}, "valid", False),
    ],
)
def test_session_expiration_clears_persisted_and_request_state(session, expected, cleared):
    out = run(f"""
local a = new_plugin(PLUGIN)
a.session = SESSION
a.session_data = {to_lua(session)}
local msg = a:check_session()
emit({{ msg = msg, data = a.session_data, saved = SESSION_DATA, updated = a.ctx.bw.sessions_updated }})
""")
    assert out["msg"] == expected
    assert out["data"] == ({} if cleared else session)
    if cleared:
        assert out["saved"] == {}
        assert out["updated"] is True
    else:
        assert "updated" not in out


@pytest.mark.parametrize("method, status", [("GET", "OK"), ("HEAD", 403), ("DELETE", 403)])
def test_challenge_endpoint_displays_get_and_denies_unsupported_methods(method, status):
    out = run(f"""
local a = new_plugin(PLUGIN, {{ uri = '/challenge', request_method = {to_lua(method)} }})
emit({{ result = a:access(), display = a.ctx.bw.antibot_display_content }})
""")
    assert out["result"]["status"] == status
    assert out.get("display") is (True if method == "GET" else None)
    if method != "GET":
        assert out["result"]["data"] == {"id": "suspicious-method", "method": method}


@pytest.mark.parametrize("outcome", ["wrong", "error", "solved"])
def test_post_challenge_outcome_controls_status_metrics_and_redirect(outcome):
    setup = "VARIABLES.USE_ANTIBOT = 'captcha'\n"
    if outcome == "error":
        setup = "VARIABLES.USE_ANTIBOT = 'unknown'\n"
    answer = "abcdef" if outcome == "solved" else "wrong"
    out = run(
        f"""
SESSION_DATA = {{ prepared = true, resolved = false, time_resolve = NOW, type = VARIABLES.USE_ANTIBOT,
    captcha = 'abcdef', original_uri = '/deep?token=secret' }}
POST_ARGS = {{ captcha = {to_lua(answer)}, next = '/deep' }}
local a = new_plugin(PLUGIN, {{ uri = '/challenge', request_method = 'POST' }})
emit({{ result = a:access(), metrics = METRICS, display = a.ctx.bw.antibot_display_content, session = SESSION_DATA, logs = LOGS }})
""",
        setup,
    )
    if outcome == "error":
        assert out["result"] == {"ret": False, "msg": "check challenge error : unknown", "status": 500}
    elif outcome == "wrong":
        assert out["result"]["status"] == "OK"
        assert out["display"] is True
        assert out["metrics"]["failed_challenges"] == 1
        assert any(level == "WARN" and "client failed challenge" in msg for level, msg in out["logs"])
    else:
        assert out["result"]["redirect"] == "/deep?token=secret"
        assert out["session"]["resolved"] is True
        assert out["metrics"] == {}


@pytest.mark.parametrize(
    "state, message, status, redirect",
    [
        ("no-display", "display content not needed", None, "/"),
        ("no-session", "missing session data", 500, None),
        ("unprepared", "no session", None, "/"),
        ("prepared", "content displayed", None, None),
    ],
)
def test_content_requires_prepared_session_and_generates_nonces(state, message, status, redirect):
    out = run(f"""
local a = new_plugin(PLUGIN)
a.ctx.bw.antibot_display_content = {to_lua(state != 'no-display')}
if {to_lua(state not in ('no-display', 'no-session'))} then
    a.ctx.bw.antibot_session_data = {{ prepared = {to_lua(state != 'unprepared')}, type = 'javascript' }}
end
emit({{ result = a:content(), script = a.ctx.bw.antibot_nonce_script, style = a.ctx.bw.antibot_nonce_style, renders = RENDERS }})
""")
    assert out["result"]["msg"] == message
    assert out["result"].get("status") == status
    assert out["result"].get("redirect") == redirect
    if state == "prepared":
        assert out["script"] == "n" * 32
        assert out["style"] == "n" * 32
        assert out["renders"][0]["name"] == "javascript.html"


@pytest.mark.parametrize("kind", ["javascript", "recaptcha", "hcaptcha", "turnstile", "mcaptcha", "capjs"])
def test_header_nonce_csp_is_uncacheable_and_provider_scoped(kind):
    out = run(f"""
local a = new_plugin(PLUGIN, {{ uri = '/challenge', scheme = 'https' }})
a.ctx.bw.antibot_session_data = {{ type = {to_lua(kind)} }}
a.ctx.bw.antibot_nonce_script = 'script-nonce'
a.ctx.bw.antibot_nonce_style = 'style-nonce'
a.ctx.bw.antibot_display_content = true
ngx.header['Permissions-Policy'] = {{ 'camera=()', 'picture-in-picture=()', 'microphone=()' }}
emit({{ result = a:header(), headers = ngx.header }})
""")
    assert out["result"]["ret"] is True
    headers = out["headers"]
    assert headers["Cache-Control"] == "no-store"
    directives = dict(item.strip().split(" ", 1) for item in headers["Content-Security-Policy"].split(";") if " " in item.strip())
    assert directives["default-src"] == "'none'"
    assert "'nonce-script-nonce'" in directives["script-src"]
    assert "'nonce-style-nonce'" in directives["style-src"]
    assert directives["require-trusted-types-for"] == "'script'"
    assert "upgrade-insecure-requests;" in headers["Content-Security-Policy"]
    if kind == "javascript":
        assert directives["worker-src"] == "blob:"
    elif kind == "recaptcha":
        assert "https://www.google.com/recaptcha/" in directives["connect-src"]
    elif kind == "hcaptcha":
        assert "https://*.hcaptcha.com" in directives["style-src"]
    elif kind == "turnstile":
        assert directives["frame-src"] == "https://challenges.cloudflare.com"
        assert headers["Permissions-Policy"] == "camera=(), microphone=()"
    elif kind == "mcaptcha":
        assert directives["frame-src"] == "https://captcha.example"
    else:
        assert directives["script-src"] == "'nonce-script-nonce'"
        assert directives["frame-src"] == "'self'"


def test_capjs_iframe_relaxes_only_widget_csp():
    out = run(r"""
ngx.var.arg_capjs_frame = "1"
local a = new_plugin(PLUGIN, { uri = "/challenge" })
a.ctx.bw.antibot_session_data = { type = "capjs" }
a.ctx.bw.antibot_nonce_script, a.ctx.bw.antibot_nonce_style = "s", "t"
a.ctx.bw.antibot_display_content = true
a:header()
emit(ngx.header)
""")
    csp = out["Content-Security-Policy"]
    assert "'unsafe-eval'" in csp and "'wasm-unsafe-eval'" in csp
    assert "worker-src blob: https://widget.example;" in csp
    assert "frame-ancestors 'self';" in csp
    assert "require-trusted-types-for" not in csp


@pytest.mark.parametrize("state", ["other-uri", "no-session", "resolved", "no-nonces", "error"])
def test_header_preserves_existing_csp_when_challenge_not_displayed(state):
    out = run(f"""
local a = new_plugin(PLUGIN, {{ uri = {to_lua('/page' if state == 'other-uri' else '/challenge')} }})
ngx.header['Content-Security-Policy'] = 'existing-policy'
if {to_lua(state != 'no-session')} then
    a.ctx.bw.antibot_session_data = {{ resolved = {to_lua(state == 'resolved')}, original_uri = '//evil.example' }}
end
if {to_lua(state != 'no-nonces')} then a.ctx.bw.antibot_nonce_script, a.ctx.bw.antibot_nonce_style = 's', 't' end
emit({{ result = a:header(), headers = ngx.header }})
""")
    assert out["headers"]["Content-Security-Policy"] == "existing-policy"
    assert "Cache-Control" not in out["headers"]
    if state == "resolved":
        assert out["result"]["redirect"] == "/"


@pytest.mark.parametrize(
    "mode, dest, accept, expected",
    [
        ("navigate", "empty", None, True),
        ("cors", "document", None, True),
        ("cors", "image", "text/html", False),
        (None, None, "text/html,application/xhtml+xml", True),
        (None, None, "*/*", False),
        (None, None, None, False),
    ],
)
def test_navigation_metadata_beats_accept_fallback(mode, dest, accept, expected):
    out = run(f"""
ngx.var.http_sec_fetch_mode = {to_lua(mode)}
ngx.var.http_sec_fetch_dest = {to_lua(dest)}
ngx.var.http_accept = {to_lua(accept)}
emit(new_plugin(PLUGIN):is_navigation_request())
""")
    assert out is expected


@pytest.mark.parametrize(
    "referer, expected",
    [
        (None, "/"),
        ("", "/"),
        ("nonsense", "/"),
        ("https://other.example/deep", "/"),
        ("https://app.example:8443/deep?x=1", "/deep?x=1"),
        ("/relative", "/relative"),
        ("/asset.css", "/"),
        ("//evil.example", "/"),
    ],
)
def test_static_original_uri_uses_only_safe_same_host_document_referer(referer, expected):
    out = run(f"""
local a = new_plugin(PLUGIN, {{ uri = '/app.JS', request_uri = '/app.JS?v=1', http_host = 'app.example:443', http_referer = {to_lua(referer)} }})
emit(a:get_original_uri())
""")
    assert out == expected


@pytest.mark.parametrize(
    "target",
    [
        True,
        [True],
        "",
        "relative",
        "//evil.example",
        "/\\evil.example",
        "/x?u=https://evil.example",
        "/x\r\nLocation:y",
        "/%63hallenge",
        "/a/../challenge",
        "/challenge#x",
    ],
)
def test_unsafe_success_target_logs_warning_and_falls_back_without_echoing_value(target):
    out = run(f"""
VARIABLES.ANTIBOT_SUCCESS_URI = {to_lua(target)}
local a = new_plugin(PLUGIN)
a.session_data = {{ original_uri = '/deep?x=1' }}
emit({{ target = a:resolve_redirect_target({{ next = {{ '/other?secret=drop', '/ignored' }} }}), logs = LOGS }})
""")
    assert out["target"] == "/other"
    if target == "":
        assert out["logs"] == {}
    else:
        assert out["logs"] == [["WARN", "ignoring unsafe ANTIBOT_SUCCESS_URI, redirecting to the original destination instead"]]


@pytest.mark.parametrize("target", ["/done", "/done/", "/one/./two", "/one/../two", "/done?x=1"])
def test_safe_success_uri_overrides_posted_and_session_destinations(target):
    out = run(f"""
VARIABLES.ANTIBOT_SUCCESS_URI = {to_lua(target)}
local a = new_plugin(PLUGIN)
a.session_data = {{ original_uri = '/session' }}
emit(a:resolve_redirect_target({{ next = '/posted' }}))
""")
    assert out == target


@pytest.mark.parametrize(
    "country, global_ip, only, ignore, expected",
    [
        ("fr", True, "", "FR", True),
        ("US", True, "FR", "", True),
        ("FR", True, "FR", "", False),
        (None, True, "FR", "", False),
        (None, False, "FR", "", True),
        (None, False, "", "FR", False),
        ("FR", True, "", "", False),
    ],
)
def test_country_ignore_and_only_filters(country, global_ip, only, ignore, expected):
    out = run(f"""
COUNTRY = {to_lua(country)}
VARIABLES.ANTIBOT_ONLY_COUNTRY, VARIABLES.ANTIBOT_IGNORE_COUNTRY = {to_lua(only)}, {to_lua(ignore)}
local a = new_plugin(PLUGIN, {{ ip_is_global = {to_lua(global_ip)} }})
local ok, reason = a:is_ignored('COUNTRY')
emit({{ ok = ok, reason = reason, logs = LOGS }})
""")
    assert out["ok"] is expected
    assert (out["reason"] != "ko") is expected
    if country is None and global_ip:
        assert "can't get country" in out["logs"][0][1]


@pytest.mark.parametrize(
    "case, expected", [("ip", "ip"), ("rdns", "rDNS .example.test"), ("asn", "ASN 64500"), ("unconfirmed", "ko"), ("local", "ko"), ("lookup-failure", "ko")]
)
def test_ip_ignore_requires_network_match_confirmed_rdns_or_asn(case, expected):
    out = run(f"""
local case = {to_lua(case)}
if case == 'ip' then VARIABLES.ANTIBOT_IGNORE_IP = '1.2.3.4' end
VARIABLES.ANTIBOT_IGNORE_RDNS = '.example.test'
VARIABLES.ANTIBOT_IGNORE_ASN = '64500'
RDNS = case ~= 'lookup-failure' and {{ 'crawler.example.test' }} or nil
FCRDNS = case == 'rdns'
ASN = case == 'asn' and 64500 or nil
local a = new_plugin(PLUGIN, {{ ip_is_global = case ~= 'local' }})
local ok, reason = a:is_ignored('IP')
emit({{ ok = ok, reason = reason, logs = LOGS }})
""")
    assert out["ok"] is (expected != "ko")
    assert out["reason"] == expected
    if case == "lookup-failure":
        assert any("error while getting rdns" in msg for _, msg in out["logs"])


@pytest.mark.parametrize("network, client, error", [("broken", "1.2.3.4", "invalid address broken"), ("1.2.3.4", "broken", "invalid client address")])
def test_ip_matcher_errors_are_reported_without_ignoring_client(network, client, error):
    out = run(f"""
VARIABLES.ANTIBOT_IGNORE_IP = {to_lua(network)}
local a = new_plugin(PLUGIN, {{ remote_addr = {to_lua(client)} }})
local ok, reason = a:is_ignored_ip()
emit({{ ok = ok, reason = reason }})
""")
    assert "ok" not in out
    assert out["reason"] == error


@pytest.mark.parametrize("agent, ignored", [("trusted-client", True), ("other-client", False)])
def test_user_agent_ignore_dispatch(agent, ignored):
    out = run(f"""
VARIABLES.ANTIBOT_IGNORE_USER_AGENT = '^trusted'
local a = new_plugin(PLUGIN, {{ http_user_agent = {to_lua(agent)} }})
local ok, reason = a:is_ignored('UA')
local unknown, err = a:is_ignored('OTHER')
emit({{ ok = ok, reason = reason, unknown = unknown, err = err }})
""")
    assert out["ok"] is ignored
    assert out["reason"] == ("UA ^trusted" if ignored else "ko")
    assert out["unknown"] is False
    assert out["err"] == "unknown kind OTHER"
