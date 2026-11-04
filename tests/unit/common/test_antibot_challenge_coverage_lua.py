"""Challenge generation, rendering and fail-closed verification through the real antibot module."""

import hashlib
import json
from urllib.parse import parse_qs

import pytest
from _lua_plugin_helpers import CORE, LUA, run_module, to_lua

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "antibot" / "antibot.lua"
KINDS = ["cookie", "javascript", "captcha", "recaptcha", "hcaptcha", "turnstile", "mcaptcha", "capjs"]

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
    }
end }
package.loaded["resty.ipmatcher"] = {}
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


def test_capjs_frame_uses_isolated_template():
    out = run("""
ngx.var.arg_capjs_frame = '1'
local a = new('capjs')
a:display_challenge()
emit(RENDERS)
""")
    assert out[0]["name"] == "capjs_frame.html"


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
        ("captcha", {"captcha": "wrong"}, 8, False, "wrong value, expected AAAAAA"),
        ("captcha", {"captcha": ["AAAAAA", "wrong"]}, 8, True, "resolved"),
        ("captcha", {"captcha": ["wrong", "AAAAAA"]}, 8, False, "wrong value, expected AAAAAA"),
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


@pytest.mark.parametrize("kind", KINDS[1:])
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
