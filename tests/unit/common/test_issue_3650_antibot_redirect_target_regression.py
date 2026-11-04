"""The antibot challenge must send a solved client back to the page it asked for, and ignore lists must see the query.

The challenge used to rebuild the destination from the browser ``Referer``, so a missing or cross-origin Referer sent every
solved client to ``/``; the destination now travels as an explicit ``next`` value and the session. The same ``next``
handling must refuse aliases of the challenge URL (dot segments, percent-encoding, fragments), which looped back to the
challenge. ``ANTIBOT_IGNORE_URI`` must also match the query string, and the classic reCAPTCHA verdict must follow the
setting, not a session flag. This test runs the real ``antibot.lua`` methods against recording stand-ins.
Refs: #3650, #3374, #2825.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HEADER = r"""
VARIABLES = { ANTIBOT_URI = "/challenge", ANTIBOT_RECAPTCHA_CLASSIC = "no", ANTIBOT_RECAPTCHA_SCORE = "0.7", ANTIBOT_SUCCESS_URI = "" }
"""

SELF = r"""
local function new(bw, session, vars)
    local v = {}
    for k, val in pairs(VARIABLES) do v[k] = val end
    for k, val in pairs(vars or {}) do v[k] = val end
    return setmetatable({
        variables = v, session_data = session or {}, ctx = { bw = bw },
        logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. ": " .. tostring(msg) end },
        lists = { IGNORE_URI = IGNORE_URI or {} }, set_session_data = function() end,
    }, { __index = PLUGIN })
end
"""


def run(body, header=""):
    return run_plugin_script("antibot", SELF + body, header=HEADER + header)


def original_uri(bw, *, uri_args="{}", post_args="{}", session="{}"):
    bw_lua = ", ".join(f'{key} = "{value}"' for key, value in bw.items())
    return run(f"""
URI_ARGS, POST_ARGS = {uri_args}, {post_args}
local a = new({{ {bw_lua} }}, {session})
emit({{ uri = a:get_original_uri() }})
""")["uri"]


def test_the_requested_uri_with_its_query_is_the_destination_whatever_the_referer_says():
    page = {"uri": "/page", "request_uri": "/page?x=1&y=2", "request_method": "GET", "http_host": "app.example.com"}
    assert original_uri(page) == "/page?x=1&y=2"
    assert original_uri({**page, "http_referer": "https://evil.example/landing"}) == "/page?x=1&y=2"
    assert original_uri({**page, "http_referer": "https://app.example.com/other"}) == "/page?x=1&y=2"


def test_the_challenge_endpoint_recovers_the_destination_from_next():
    bw = {"uri": "/challenge", "request_uri": "/challenge?next=%2Fdeep%2Fpage", "request_method": "GET", "http_referer": "https://evil.example/"}
    assert original_uri(bw, uri_args='{ next = "/deep/page" }') == "/deep/page"


def test_a_failed_solve_posts_next_and_gets_the_session_query_back():
    bw = {"uri": "/challenge", "request_uri": "/challenge", "request_method": "POST"}
    session = '{ original_uri = "/deep/page?x=1" }'
    assert original_uri(bw, post_args='{ next = "/deep/page" }', session=session) == "/deep/page?x=1"
    assert original_uri(bw, post_args='{ next = "/other" }', session=session) == "/other"


@pytest.mark.parametrize("alias", ["/challenge", "/a/../challenge", "/./challenge", "/%63hallenge", "/challenge#x", "/a/%2e%2e/challenge", "/a\\..\\challenge"])
def test_aliases_of_the_challenge_url_are_not_accepted_as_the_next_target(alias):
    bw = {"uri": "/challenge", "request_uri": "/challenge", "request_method": "GET"}
    assert original_uri(bw, uri_args=f'{{ next = "{alias}" }}'.replace("\\", "\\\\")) == "/"


@pytest.mark.parametrize("unsafe", ["//evil.example/x", "/\\\\evil.example", "https://evil.example/", "page"])
def test_unsafe_next_values_fall_back_to_the_root(unsafe):
    bw = {"uri": "/challenge", "request_uri": "/challenge", "request_method": "GET"}
    assert original_uri(bw, uri_args=f'{{ next = "{unsafe}" }}') == "/"


@pytest.mark.parametrize(
    "posted, expected",
    [("/deep/page", "/deep/page?x=1"), ("/other", "/other"), ("/deep/page?leak=1", "/deep/page?x=1")],
)
def test_the_solved_redirect_restores_the_session_query_only_for_the_same_path(posted, expected):
    out = run(f"""
local a = new({{ uri = "/challenge" }}, {{ original_uri = "/deep/page?x=1" }})
emit({{ target = a:resolve_redirect_target({{ next = "{posted}" }}) }})
""")
    assert out["target"] == expected


@pytest.mark.parametrize(
    "request_uri, ignored",
    [("/health?probe=1", True), ("/health?probe=2", False), ("/health", False)],
)
def test_ignore_uri_matches_the_query_string_of_the_request_uri(request_uri, ignored):
    path = request_uri.split("?")[0]
    out = run(f"""
IGNORE_URI = {{ "probe=1" }}
local a = new({{ uri = "{path}", request_uri = "{request_uri}" }})
local ignored = a:is_ignored_uri()
emit({{ ignored = ignored }})
""")
    assert out["ignored"] is ignored


@pytest.mark.parametrize("classic, body, resolved", [("yes", '{"success":true}', True), ("yes", '{"success":false}', False)])
def test_classic_recaptcha_is_decided_by_the_setting_and_a_missing_score_counts_as_passing(classic, body, resolved):
    out = run(
        f"""
POST_ARGS = {{ token = "tok" }}
HTTP_BODY = '{body}'
local a = new({{ remote_addr = "198.51.100.7", uri = "/challenge" }}, {{ prepared = true, type = "recaptcha", random = "r" }},
              {{ ANTIBOT_RECAPTCHA_CLASSIC = "{classic}", ANTIBOT_RECAPTCHA_SECRET = "s", ANTIBOT_RECAPTCHA_JA3 = "", ANTIBOT_RECAPTCHA_JA4 = "" }})
a.resolve_redirect_target = function() return "/" end
local ok, msg = a:check_challenge()
emit({{ ok = ok, msg = msg, url = HTTP_CALLS[1] and HTTP_CALLS[1].url or "none" }})
""",
    )
    assert out["ok"] is resolved
    assert out["url"] == "https://www.google.com/recaptcha/api/siteverify"
