"""Challenge generation, rendering and fail-closed verification through the real antibot module."""

import hashlib
import json
from urllib.parse import parse_qs

import pytest
from _lua_plugin_helpers import CORE, LUA, ROOT, run_module, to_lua

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "antibot" / "antibot.lua"
KINDS = ["cookie", "javascript", "captcha", "recaptcha", "hcaptcha", "turnstile", "mcaptcha", "capjs", "altcha"]

PREAMBLE = r"""
package.loaded["cjson"] = json
ngx.now = function() return NOW end
ngx.escape_uri = function(v)
    return (v:gsub("[^%w%-%._~]", function(c) return string.format("%%%02X", c:byte()) end))
end
POST_ARGS, POST_ERR = {}, nil
ngx.req.get_post_args = function(limit) assert(limit == 8) return POST_ARGS, POST_ERR end
local utils = package.loaded["bunkerweb.utils"]
utils.rand = function(len, letters, alphabet)
    RAND_ARGS = { len = len, letters = letters, alphabet = alphabet }
    return string.rep(letters and "A" or "r", len)
end
package.loaded["base64"] = { encode = function(v) return "encoded:" .. v end }
CAPTCHA = {}
package.loaded["antibot.captcha"] = { new = function()
    return {
        font = function(_, v) CAPTCHA.font = v end,
        string = function(_, v) CAPTCHA.text = v end,
        generate = function() CAPTCHA.generated = true end,
        jpegStr = function(_, quality) CAPTCHA.quality = quality return "jpeg" end,
    }
end }
package.loaded["resty.sha256"] = { new = function()
    local input = ""
    return { update = function(_, v) input = input .. v end, final = function() return SHA256(input) end }
end }
package.loaded["resty.string"] = { to_hex = function(v) return v end }
HTTP_CALLS, CLOSED = {}, 0
LIVE_THREADS = 0
local function resume_thread(thread)
    local ok, value = coroutine.resume(thread.co)
    if coroutine.status(thread.co) == "dead" then
        thread.result = { ok, value }
    else
        thread.ready = NOW + value
    end
end
local function retire_thread(thread)
    if thread.live then
        thread.live = false
        LIVE_THREADS = LIVE_THREADS - 1
    end
end
ngx.sleep = function(seconds) coroutine.yield(seconds) end
ngx.thread = {
    spawn = function(fn, ...)
        local args = { ... }
        local thread = { live = true, co = coroutine.create(function() return fn(unpack(args)) end) }
        LIVE_THREADS = LIVE_THREADS + 1
        resume_thread(thread)
        return thread
    end,
    wait = function(first, second)
        while not first.result and not second.result do
            local next_thread = first.ready < second.ready and first or second
            NOW = next_thread.ready
            resume_thread(next_thread)
        end
        local winner = first.result and first or second
        retire_thread(winner)
        return winner.result[1], winner.result[2]
    end,
    kill = retire_thread,
}
local function http_delay(stage)
    local seconds = HTTP_DELAYS and HTTP_DELAYS[stage]
    if seconds then
        local thread, main = coroutine.running()
        if thread and not main then
            ngx.sleep(seconds)
        else
            NOW = NOW + seconds
        end
    end
end
package.loaded["resty.http"] = { new = function()
    if HTTP_NEW_ERR then return nil, HTTP_NEW_ERR end
    return {
        set_timeouts = function(_, a, b, c) assert(a == 5000 and b == 5000 and c == 5000) end,
        close = function() CLOSED = CLOSED + 1 end,
        request_uri = function(_, url, opts)
            HTTP_CALLS[#HTTP_CALLS + 1] = { url = url, body = opts.body, headers = opts.headers, method = opts.method }
            if HTTP_ERR then return nil, HTTP_ERR end
            return { body = HTTP_BODY or "{}" }
        end,
        connect = function(_, options)
            CONNECT = options
            http_delay("dns")
            http_delay("tcp")
            http_delay("tls")
            if HTTP_ERR then return nil, HTTP_ERR end
            return true
        end,
        request = function(_, options)
            HTTP_CALLS[#HTTP_CALLS + 1] = options
            http_delay("send")
            http_delay("status")
            http_delay("headers")
            local body = HTTP_BODY or "{}"
            return { status = HTTP_STATUS or 200, headers = { ["Content-Length"] = HTTP_LENGTH }, body_reader = function(limit)
                assert(limit > 0 and limit <= 32769)
                if HTTP_READ_ERR then return nil, HTTP_READ_ERR end
                if #body == 0 then return nil end
                http_delay("body")
                local chunk = body:sub(1, limit)
                body = body:sub(limit + 1)
                if HTTP_CLOSE and #body == 0 then return chunk, "closed" end
                return chunk
            end }
        end,
        set_timeout = function(_, timeout) assert(timeout > 0 and timeout <= 5000) end,
    }
end }
package.loaded["resty.ipmatcher"] = {}
local view = package.loaded["resty.template"]
view.new = function() return { render_file = view.render } end
"""

SELF = r"""
local function new(kind)
    return setmetatable({
        variables = {
            USE_ANTIBOT = kind, ANTIBOT_URI = "/challenge", ANTIBOT_SUCCESS_URI = "",
            ANTIBOT_JAVASCRIPT_DIFFICULTY = "8", ANTIBOT_CAPTCHA_ALPHABET = "ABC",
            ANTIBOT_RECAPTCHA_CLASSIC = "yes", ANTIBOT_RECAPTCHA_SCORE = "0.7",
            ANTIBOT_RECAPTCHA_SITEKEY = "recaptcha-site", ANTIBOT_RECAPTCHA_SECRET = "recaptcha-secret",
            ANTIBOT_RECAPTCHA_PROJECT_ID = "project", ANTIBOT_RECAPTCHA_API_KEY = "api-key",
            ANTIBOT_RECAPTCHA_JA3 = "ja3", ANTIBOT_RECAPTCHA_JA4 = "ja4",
            ANTIBOT_HCAPTCHA_SITEKEY = "hcaptcha-site", ANTIBOT_HCAPTCHA_SECRET = "hcaptcha-secret",
            ANTIBOT_TURNSTILE_SITEKEY = "turnstile-site", ANTIBOT_TURNSTILE_SECRET = "turnstile-secret",
            ANTIBOT_MCAPTCHA_SITEKEY = "mcaptcha-site", ANTIBOT_MCAPTCHA_SECRET = "mcaptcha-secret",
            ANTIBOT_MCAPTCHA_URL = "https://mcaptcha.example",
            ANTIBOT_CAPJS_FRONTEND_URL = "https://capjs.example/", ANTIBOT_CAPJS_BACKEND_URL = "",
            ANTIBOT_CAPJS_SITEKEY = "capjs-site", ANTIBOT_CAPJS_SECRET = "capjs-secret",
            ANTIBOT_ALTCHA_FRONTEND_URL = "https://altcha.example", ANTIBOT_ALTCHA_BACKEND_URL = "",
            ANTIBOT_ALTCHA_SITEKEY = "altcha-site", ANTIBOT_ALTCHA_SECRET = "altcha-secret",
        },
        ctx = { bw = { uri = "/challenge", remote_addr = "198.51.100.7", http_user_agent = "browser",
                       antibot_nonce_script = "script-nonce", antibot_nonce_style = "style-nonce" } },
        session_data = { prepared = true, resolved = false, type = kind, random = string.rep("r", 20),
                         difficulty = 8, captcha = "AAAAAA", original_uri = "/private?secret=value" },
        logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = { level, msg } end },
        saves = 0,
        set_session_data = function(self)
            self.saves = self.saves + 1
            self.saved = {}
            for k, v in pairs(self.session_data) do self.saved[k] = v end
        end,
    }, { __index = PLUGIN })
end
"""


def run(body):
    return run_module(MODULE, SELF + body, preamble=PREAMBLE)


@pytest.mark.parametrize("kind", KINDS)
def test_preparation_records_kind_deadline_and_only_cookie_is_already_resolved(kind):
    out = run(f"""
local a = new({to_lua(kind)})
a.session_data = {{}}
a.get_original_uri = function() return '/private?secret=value' end
a:prepare_challenge()
local first_saves = a.saves
a:prepare_challenge()
emit({{ session = a.session_data, saved = a.saved, saves = a.saves, first_saves = first_saves, rand = RAND_ARGS }})
""")
    session = out["session"]
    assert session == out["saved"]
    assert session["prepared"] is True
    assert session["resolved"] is (kind == "cookie")
    assert session["type"] == kind
    assert session["time_resolve"] == 1000000
    assert session["original_uri"] == "/private?secret=value"
    assert out["saves"] == out["first_saves"] == 1
    if kind == "cookie":
        assert session["time_valid"] == 1000000
    else:
        assert "time_valid" not in session
    if kind == "javascript":
        assert session["random"] == "r" * 20
        assert session["difficulty"] == 8
    elif kind == "captcha":
        assert session["captcha"] == "AAAAAA"
        assert out["rand"] == {"len": 6, "letters": True, "alphabet": "ABC"}


def test_preparation_uses_legacy_pow_difficulty_for_old_configuration():
    out = run("""
local a = new('javascript')
a.session_data = {}
a.variables.ANTIBOT_JAVASCRIPT_DIFFICULTY = nil
a.get_original_uri = function() return '/' end
a:prepare_challenge()
emit(a.session_data)
""")
    assert out["difficulty"] == 16


def test_speculative_request_cannot_prepare_or_leak_control_bytes_into_logs():
    out = run(r"""
local a = new('captcha')
a.session_data = {}
a.ctx.bw.uri = '/asset\r\n.js'
ngx.var.http_sec_fetch_mode = 'no-cors'
a:prepare_challenge()
emit({ session = a.session_data, saves = a.saves, logs = LOGS })
""")
    assert not out["session"]
    assert out["saves"] == 0
    assert out["logs"] == [["INFO", "skipping challenge prepare for non-navigation request : /asset??.js"]]


@pytest.mark.parametrize("kind", KINDS)
def test_display_renders_kind_specific_payload_without_session_query(kind):
    out = run(f"""
local a = new({to_lua(kind)})
local ok, msg = a:display_challenge()
emit({{ ok = ok, msg = msg, renders = RENDERS, captcha = CAPTCHA }})
""")
    assert out["ok"] is True
    assert out["msg"] == "displayed challenge"
    assert len(out["renders"]) == 1
    render = out["renders"][0]
    assert render["name"] == kind + ".html"
    payload = render["data"]
    assert payload["next"] == "/private"
    assert payload["antibot_uri"] == "/challenge"
    assert payload["nonce_script"] == "script-nonce"
    assert payload["nonce_style"] == "style-nonce"
    if kind == "javascript":
        assert payload["random"] == "r" * 20
        assert payload["antibot_difficulty"] == 8
    elif kind == "captcha":
        assert payload["captcha"] == "encoded:jpeg"
        assert out["captcha"] == {"font": "/usr/share/bunkerweb/core/antibot/files/font.ttf", "text": "AAAAAA", "generated": True, "quality": 70}
    elif kind in ("recaptcha", "hcaptcha", "turnstile", "mcaptcha"):
        assert payload[kind + "_sitekey"] == kind + "-site"
        if kind == "recaptcha":
            assert payload["recaptcha_classic"] is True
        elif kind == "mcaptcha":
            assert payload["mcaptcha_url"] == "https://mcaptcha.example"
    elif kind == "capjs":
        assert payload["capjs_url"] == "https://capjs.example/"
        assert payload["capjs_sitekey"] == "capjs-site"
    elif kind == "altcha":
        assert payload["altcha_url"] == "https://altcha.example"
        assert payload["altcha_sitekey"] == "altcha-site"
        assert "altcha-secret" not in json.dumps(payload)


def test_capjs_frame_uses_isolated_template():
    out = run("""
ngx.var.arg_capjs_frame = '1'
local a = new('capjs')
a:display_challenge()
emit(RENDERS)
""")
    assert out[0]["name"] == "capjs_frame.html"


@pytest.mark.parametrize("method,template", [("GET", "altcha_frame.html"), ("POST", "altcha.html")])
def test_altcha_frame_template_is_only_for_get(method, template):
    out = run(f"""
ngx.var.arg_altcha_frame = '1'
local a = new('altcha')
a.ctx.bw.request_method = {to_lua(method)}
a:display_challenge()
emit(RENDERS)
""")
    assert out[0]["name"] == template


def test_altcha_bundled_views_render_with_an_older_pro_template_root(tmp_path):
    (tmp_path / "javascript.html").write_text("<title>Custom JavaScript challenge</title>", encoding="utf-8")
    engine = ROOT / "src/deps/src/lua-resty-template/lib/resty/template.lua"
    out = run(f"""
ngx.get_phase = function() return "content" end
ngx.config.prefix = function() return "/" end
ngx.location = {{ capture = function() error("no template_location configured") end }}
ngx.print = function(html) SAID[#SAID + 1] = html end
ngx.var.template_root = {to_lua(str(tmp_path))}
local open = io.open
io.open = function(path, ...)
    if path:find("/usr/share/bunkerweb/core/antibot/files/", 1, true) == 1 then
        path = {to_lua(str(CORE / "antibot" / "files"))} .. "/" .. path:match("[^/]+$")
    end
    return open(path, ...)
end
local template = dofile({to_lua(str(engine))})
package.loaded["resty.template"] = template
PLUGIN = dofile({to_lua(str(MODULE))})
local a = new('altcha')
a.ctx.bw.request_method = "GET"
a:display_challenge()
ngx.var.arg_altcha_frame = "1"
a:display_challenge()
new('javascript'):display_challenge()
emit({{ parent = SAID[1]:find("altcha-frame", 1, true) ~= nil,
    frame = SAID[2]:find("<altcha-widget", 1, true) ~= nil, existing = SAID[3], template_root = ngx.var.template_root,
    shared_instance_unchanged = template.root == nil }})
""")
    assert out["parent"] and out["frame"]
    assert out["existing"] == "<title>Custom JavaScript challenge</title>"
    assert out["template_root"] == str(tmp_path)
    assert out["shared_instance_unchanged"] is True


@pytest.mark.parametrize(
    "frontend,backend,scheme,host,port",
    [
        ("https://altcha.example", "", "https", "altcha.example", 443),
        ("https://altcha.example", "https://verifier.example.:8443", "https", "verifier.example.", 8443),
        ("https://altcha.example", "http://verifier:8000", "http", "verifier", 8000),
        ("https://altcha.example", "http://192.0.2.27:8000", "http", "192.0.2.27", 8000),
    ],
)
@pytest.mark.parametrize("close_delimited", [True, False])
def test_altcha_verifies_and_resolves_the_session(frontend, backend, scheme, host, port, close_delimited):
    out = run(f"""
local a = new('altcha')
a.variables.ANTIBOT_ALTCHA_FRONTEND_URL = {to_lua(frontend)}
a.variables.ANTIBOT_ALTCHA_BACKEND_URL = {to_lua(backend)}
BODY = 'altcha=YWJjZA%3D%3D&next=%2Fprivate'
POST_ARGS = {{ altcha = 'YWJjZA==', next = '/private' }}
HTTP_BODY = '{{"verified":true,"apiKey":"altcha-site"}}'
HTTP_CLOSE = {to_lua(close_delimited)}
local ok, _, redirect = a:check_challenge()
emit({{ ok = ok, redirect = redirect, session = a.saved, calls = HTTP_CALLS, connection = CONNECT, closed = CLOSED, threads = LIVE_THREADS }})
""")
    assert out["ok"] is True
    assert out["redirect"] == "/private?secret=value"
    assert out["session"]["resolved"] is True
    assert out["session"]["time_valid"] == 1000000
    assert out["connection"]["scheme"] == scheme
    assert out["connection"]["host"] == host
    assert out["connection"]["port"] == port
    assert out["connection"]["ssl_verify"] is True
    assert out["connection"].get("ssl_server_name") == (host.removesuffix(".") if scheme == "https" else None)
    assert out["closed"] == 1
    assert out["threads"] == 0
    (call,) = out["calls"]
    assert call["path"] == "/v1/verify/signature"
    assert call["method"] == "POST"
    assert call["headers"]["Content-Type"] == "application/json"
    assert json.loads(call["body"]) == {"payload": "YWJjZA==", "secret": "altcha-secret"}


@pytest.mark.parametrize(
    "delays,elapsed,accepted",
    [
        ({"dns": 8}, 5, False),
        ({"dns": 2, "tcp": 4}, 5, False),
        ({"tcp": 2, "tls": 4}, 5, False),
        ({"tls": 2, "send": 4}, 5, False),
        ({"send": 2, "status": 4}, 5, False),
        ({"status": 2, "headers": 4}, 5, False),
        ({"headers": 2, "body": 4}, 5, False),
        ({"headers": 2, "body": 3}, 5, False),
        ({"dns": 1, "tcp": 0.5, "tls": 0.5, "headers": 1, "body": 1.5}, 4.5, True),
    ],
)
def test_altcha_verifier_shares_one_deadline_and_cleans_up(delays, elapsed, accepted):
    out = run(f"""
local a = new('altcha')
BODY = 'altcha=YWJjZA%3D%3D'
POST_ARGS = {{ altcha = 'YWJjZA==' }}
HTTP_BODY = '{{"verified":true,"apiKey":"altcha-site"}}'
HTTP_DELAYS = {to_lua(delays)}
local start = NOW
local ok, _, redirect = a:check_challenge()
emit({{ ok = ok, redirect = redirect, elapsed = NOW - start, resolved = a.session_data.resolved,
    saves = a.saves, closed = CLOSED, threads = LIVE_THREADS }})
""")
    assert out["elapsed"] == elapsed
    assert out["ok"] is out["resolved"] is accepted
    assert out.get("redirect") == ("/private?secret=value" if accepted else None)
    assert out["saves"] == int(accepted)
    assert out["closed"] == 1
    assert out["threads"] == 0


@pytest.mark.parametrize(
    "response",
    [
        """HTTP_BODY = '{"verified":false,"apiKey":"altcha-site"}'""",
        """HTTP_BODY = '{"verified":"true","apiKey":"altcha-site"}'""",
        """HTTP_BODY = '{"verified":true,"apiKey":"other-site"}'""",
        """HTTP_BODY = '{"verified":true,"apiKey":42}'""",
        """HTTP_BODY = '{"verified":true}'""",
        """HTTP_BODY = 'true'""",
        """HTTP_BODY = '{'""",
        """HTTP_BODY = string.rep('x', 32769)""",
        """HTTP_BODY, HTTP_STATUS = '{"verified":true,"apiKey":"altcha-site"}', 302""",
        """HTTP_BODY, HTTP_LENGTH = '{"verified":true,"apiKey":"altcha-site"}', '-1'""",
        """HTTP_BODY, HTTP_LENGTH = '{"verified":true,"apiKey":"altcha-site"}', '32769'""",
        """HTTP_BODY, HTTP_LENGTH, HTTP_CLOSE = '{"verified":true,"apiKey":"altcha-site"}', '100', true""",
        """HTTP_ERR = 'unavailable: altcha-secret'""",
        """HTTP_NEW_ERR = 'cannot connect: altcha-secret'""",
        """HTTP_READ_ERR = 'timeout: altcha-secret'""",
    ],
)
def test_altcha_verifier_failure_leaves_session_unresolved_for_manual_retry(response):
    out = run(f"""
local a = new('altcha')
BODY = 'altcha=YWJjZA%3D%3D'
POST_ARGS = {{ altcha = 'YWJjZA==' }}
{response}
local ok, msg, redirect = a:check_challenge()
emit({{ ok = ok, msg = msg, redirect = redirect, session = a.session_data, saves = a.saves, closed = CLOSED, threads = LIVE_THREADS }})
""")
    assert out["ok"] is False
    assert out["session"]["resolved"] is False and out["session"]["prepared"] is True
    assert out["saves"] == 0
    assert out["closed"] == (0 if response.startswith("HTTP_NEW_ERR") else 1)
    assert out["threads"] == 0
    assert "redirect" not in out
    assert "altcha-secret" not in json.dumps(out)


@pytest.mark.parametrize(
    "request_setup",
    [
        "POST_ARGS.altcha = nil",
        "POST_ARGS.altcha = true",
        "POST_ARGS.altcha = {'first', 'second'}",
        "POST_ARGS.altcha = ''",
        "POST_ARGS.altcha = string.rep('a', 8193)",
        "POST_ERR = 'truncated'",
        "BODY = string.rep('a', 16385)",
        "BODY = nil",
    ],
)
def test_altcha_invalid_form_never_reaches_verifier(request_setup):
    out = run(f"""
local a = new('altcha')
BODY = 'altcha=YWJjZA%3D%3D'
POST_ARGS = {{ altcha = 'YWJjZA==' }}
{request_setup}
local ok = a:check_challenge()
emit({{ ok = ok, calls = HTTP_CALLS, saves = a.saves }})
""")
    assert out["ok"] is False
    assert not out["calls"]
    assert out["saves"] == 0


def test_display_legacy_difficulty_enterprise_widget_and_unsafe_next():
    out = run("""
local a = new('javascript')
a.session_data.difficulty = nil
a.session_data.original_uri = '//evil.example'
a:display_challenge()
a.session_data.type = 'recaptcha'
a.variables.ANTIBOT_RECAPTCHA_CLASSIC = 'no'
a:display_challenge()
emit(RENDERS)
""")
    assert out[0]["data"]["antibot_difficulty"] == 16
    assert out[0]["data"]["next"] == "/"
    assert out[1]["data"]["recaptcha_classic"] is False


def test_unprepared_challenge_cannot_render_or_validate():
    out = run("""
local a = new('captcha')
a.session_data.prepared = false
local display, dm = a:display_challenge()
local check, cm = a:check_challenge()
emit({ display = display, dm = dm, check = check == nil, cm = cm, renders = #RENDERS, saves = a.saves })
""")
    assert out == {"display": False, "dm": "challenge not prepared", "check": True, "cm": "challenge not prepared", "renders": 0, "saves": 0}


@pytest.mark.parametrize(
    "kind,args,difficulty,expected,message",
    [
        ("captcha", {"captcha": "AAAAAA"}, 8, True, "resolved"),
        ("captcha", {"captcha": "wrong"}, 8, False, "wrong value"),
        ("captcha", {"captcha": ["AAAAAA", "wrong"]}, 8, True, "resolved"),
        ("captcha", {"captcha": ["wrong", "AAAAAA"]}, 8, False, "wrong value"),
        ("javascript", {"challenge": "970"}, 8, True, "resolved"),
        ("javascript", {"challenge": "2"}, 8, False, "wrong value"),
        ("javascript", {"challenge": "112697"}, 17, False, "solution below configured difficulty, challenge page may be outdated"),
        ("javascript", {"challenge": ["970", "2"]}, 8, True, "resolved"),
        ("javascript", {"challenge": "112697"}, None, True, "resolved"),
    ],
)
def test_local_answers_only_persist_a_valid_solution(kind, args, difficulty, expected, message):
    if kind == "javascript":
        nonce = args["challenge"]
        nonce = nonce[0] if isinstance(nonce, list) else nonce
        bits = 256 - int.from_bytes(hashlib.sha256(("r" * 20 + nonce).encode()).digest(), "big").bit_length()
        assert (bits >= (difficulty or 16)) is expected
    out = run(f"""
local a = new({to_lua(kind)})
a.session_data.difficulty = {to_lua(difficulty)}
POST_ARGS = {to_lua({**args, 'next': '/private'})}
local ok, msg, target = a:check_challenge()
emit({{ ok = ok, msg = msg, target = target, session = a.session_data, saves = a.saves, updated = a.session_updated }})
""")
    assert out["ok"] is expected
    assert out["msg"] == message
    assert "AAAAAA" not in out["msg"], "the expected answer must never reach the logs"
    assert out["session"]["prepared"] is False
    assert out["updated"] is True
    assert out["session"]["resolved"] is expected
    assert out["saves"] == int(expected)
    if expected:
        assert out["session"]["time_valid"] == 1000000
        assert out["target"] == "/private?secret=value"
    else:
        assert "time_valid" not in out["session"]
        assert "target" not in out


@pytest.mark.parametrize("kind", [kind for kind in KINDS if kind not in ("cookie", "altcha")])
@pytest.mark.parametrize("bad_args,error", [({}, None), ({"invalid": True}, None), (None, None), ({"valid": True}, "truncated")])
def test_missing_invalid_and_truncated_answers_never_validate(kind, bad_args, error):
    field = {"javascript": "challenge", "captcha": "captcha", "mcaptcha": "mcaptcha__token"}.get(kind, "token")
    args: dict | None = None if bad_args is None else ({field: 123} if "invalid" in bad_args else {field: "AAAAAA"} if "valid" in bad_args else {})
    out = run(f"""
local a = new({to_lua(kind)})
POST_ARGS, POST_ERR = {to_lua(args)}, {to_lua(error)}
local ok, msg = a:check_challenge()
emit({{ ok = ok, msg = msg, session = a.session_data, saves = a.saves, calls = #HTTP_CALLS }})
""")
    assert out["ok"] is False
    assert out["msg"] == "missing or invalid challenge arg"
    assert out["session"]["resolved"] is False
    assert out["session"]["prepared"] is False
    assert "time_valid" not in out["session"]
    assert out["saves"] == out["calls"] == 0


@pytest.mark.parametrize("kind", ["recaptcha", "enterprise", "hcaptcha", "turnstile", "mcaptcha", "capjs"])
@pytest.mark.parametrize("response", ["success", "refusal", "malformed", "transport", "client"])
def test_provider_verdict_and_errors_never_validate_failed_answers(kind, response):
    enterprise = kind == "enterprise"
    actual_kind = "recaptcha" if enterprise else kind
    accepted = response == "success"
    body = {"tokenProperties": {"valid": accepted}, "riskAnalysis": {"score": 0.9}} if enterprise else {"valid" if kind == "mcaptcha" else "success": accepted}
    out = run(f"""
local a = new({to_lua(actual_kind)})
a.variables.ANTIBOT_RECAPTCHA_CLASSIC = {to_lua('no' if enterprise else 'yes')}
POST_ARGS = {{ token = {{ 'answer +&', 'ignored' }}, mcaptcha__token = {{ 'answer +&', 'ignored' }}, next = '/private' }}
HTTP_BODY = {to_lua('not-json' if response == 'malformed' else json.dumps(body))}
HTTP_ERR = {to_lua('offline' if response == 'transport' else None)}
HTTP_NEW_ERR = {to_lua('no socket' if response == 'client' else None)}
local ok, msg, target = a:check_challenge()
emit({{ verdict = ok == nil and 'error' or tostring(ok), msg = msg, target = target,
        session = a.session_data, saved = a.saved, saves = a.saves, calls = HTTP_CALLS, closed = CLOSED }})
""")
    assert out["verdict"] == ("true" if accepted else "false" if response == "refusal" else "error")
    assert out["session"]["resolved"] is accepted
    assert out["session"]["prepared"] is False
    assert out["saves"] == int(accepted)
    assert out["closed"] == (0 if response == "client" else 1)
    if accepted:
        assert out["msg"] == "resolved"
        assert out["session"] == out["saved"]
        assert out["session"]["time_valid"] == 1000000
        assert out["target"] == "/private?secret=value"
    else:
        assert "time_valid" not in out["session"]
        assert "target" not in out
        assert {"refusal": "client failed challenge", "malformed": "error while decoding JSON", "transport": "offline", "client": "no socket"}[response] in out[
            "msg"
        ]
    if response == "client":
        assert not out["calls"]
        return
    request = out["calls"][0]
    assert len(out["calls"]) == 1
    assert request["method"] == "POST"
    assert (
        request["url"]
        == {
            "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
            "enterprise": "https://recaptchaenterprise.googleapis.com/v1/projects/project/assessments?key=api-key",
            "hcaptcha": "https://hcaptcha.com/siteverify",
            "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            "mcaptcha": "https://mcaptcha.example/api/v1/pow/siteverify",
            "capjs": "https://capjs.example/capjs-site/siteverify",
        }[kind]
    )
    if enterprise:
        assert json.loads(request["body"]) == {
            "event": {
                "token": "answer +&",
                "expectedAction": "CAPTCHA",
                "siteKey": "recaptcha-site",
                "userIpAddress": "198.51.100.7",
                "userAgent": "browser",
                "ja3": "ja3",
                "ja4": "ja4",
            }
        }
    elif kind == "mcaptcha":
        assert json.loads(request["body"]) == {"token": "answer +&", "key": "mcaptcha-site", "secret": "mcaptcha-secret"}
    else:
        expected_body = {"secret": [kind + "-secret"], "response": ["answer +&"]}
        if kind != "capjs":
            expected_body["remoteip"] = ["198.51.100.7"]
        assert parse_qs(request["body"]) == expected_body


@pytest.mark.parametrize("backend", [None, "https://verify.example///"])
def test_capjs_backend_override_and_frontend_fallback(backend):
    out = run(f"""
local a = new('capjs')
a.variables.ANTIBOT_CAPJS_BACKEND_URL = {to_lua(backend)}
POST_ARGS = {{ token = 'token' }}
HTTP_BODY = '{{"success":true}}'
local ok = a:check_challenge()
emit({{ ok = ok, calls = HTTP_CALLS }})
""")
    assert out["ok"] is True
    assert out["calls"][0]["url"] == ("https://verify.example" if backend else "https://capjs.example") + "/capjs-site/siteverify"


@pytest.mark.parametrize("classic", [True, False])
@pytest.mark.parametrize("score", [0, 0.69, 0.7, 0.9, None])
def test_recaptcha_score_threshold_including_absent_score(classic, score):
    body: dict = {"success": True} if classic else {"tokenProperties": {"valid": True}, "riskAnalysis": {"invalidReason": "low-trust"}}
    if score is not None:
        (body if classic else body["riskAnalysis"])["score"] = score
    expected = (score if score is not None else 1 if classic else 0) >= 0.7
    out = run(f"""
local a = new('recaptcha')
a.variables.ANTIBOT_RECAPTCHA_CLASSIC = {to_lua('yes' if classic else 'no')}
a.variables.ANTIBOT_RECAPTCHA_JA3, a.variables.ANTIBOT_RECAPTCHA_JA4 = '', ''
a.ctx.bw.http_user_agent = ''
POST_ARGS = {{ token = 'token' }}
HTTP_BODY = {to_lua(json.dumps(body))}
local ok, msg = a:check_challenge()
emit({{ ok = ok, msg = msg, session = a.session_data, saves = a.saves }})
""")
    assert out["ok"] is expected
    assert out["session"]["resolved"] is expected
    assert out["saves"] == int(expected)
    if not expected:
        assert out["msg"].startswith("client failed challenge with score ")
        if not classic:
            assert out["msg"].endswith(" : low-trust")


def test_unknown_kind_cannot_validate_a_session():
    out = run("""
local a = new('unknown')
local ok, msg = a:check_challenge()
emit({ error = ok == nil, msg = msg, session = a.session_data, saves = a.saves })
""")
    assert out["error"] is True
    assert out["msg"] == "unknown"
    assert out["session"]["resolved"] is False
    assert out["saves"] == 0
