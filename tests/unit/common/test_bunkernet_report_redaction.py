"""With ``BUNKERNET_FILTER_HEADERS=yes`` a BunkerNet report drops matched header and cookie values from the ModSecurity reason data.

ModSecurity reasons carry ``matched_vars`` (the request values that tripped rules) next to
``matched_var_names`` (the variables they came from). The report keeps ids, messages, names and
the score, and replaces the value of a request header or cookie match with ``""`` so both lists
stay index-aligned. Argument and body values stay. The reason data other consumers read is left
alone: the report works on a copy.
"""

import json

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore
from test_bunkernet_report_headers import IP, MODULE, STUBS  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

GET_REASON = 'get_reason = function() return "blacklist", { id = "ua", ua = "curl" } end,'
EMIT = "emit({ ret = result.ret, msg = result.msg, key = REPORTS[1] and REPORTS[1].key, report = report, max = GET_HEADERS_MAX })"


def send(reason_data, filter_headers="yes"):
    ctx = {
        "kind": "http",
        "remote_addr": IP,
        "ip_is_global": True,
        "request_method": "GET",
        "request_uri": "/?q=1",
        "server_name": "www.example.com",
    }
    stubs = STUBS.replace(GET_REASON, 'get_reason = function() return "modsecurity", REASON_DATA end,')
    stubs = stubs.replace(EMIT, "emit({ ret = result.ret, key = REPORTS[1] and REPORTS[1].key, report = report, original = REASON_DATA })")
    assert stubs.count("REASON_DATA") == 2
    script = (
        BASE_LUA.replace("function emit(v)", "json_encode, json_decode = json.encode, json.decode\nfunction emit(v)")
        + f"MODULE = {json.dumps(str(MODULE))}\nFILTER = {json.dumps(filter_headers)}\nHEADERS = {{}}\nREASON_DATA = {to_lua(reason_data)}\nCTX = {to_lua(ctx)}\nLOG_METHOD = 'log'\n"
        + stubs
    )
    out = last_json(run_lua(script))
    assert out["ret"] is True and out["key"] == "plugin_bunkernet_reports", out
    return out


def reason(names, values, **extra):
    return {"ids": ["941100", "949110"], "msgs": ["XSS", "Anomaly"], "matched_vars": values, "matched_var_names": names, "anomaly_score": ["5"], **extra}


def test_header_and_cookie_values_are_redacted_and_names_stay():
    data = reason(
        ["REQUEST_HEADERS:User-Agent", "REQUEST_COOKIES:session", "REQUEST_HEADERS:Authorization"],
        ["<script>", "abc123", "Bearer t0ken"],
    )
    sent = send(data)["report"]["data"]
    assert sent["matched_var_names"] == data["matched_var_names"]
    assert sent["matched_vars"] == ["", "", ""]
    assert sent["ids"] == data["ids"] and sent["msgs"] == data["msgs"] and sent["anomaly_score"] == data["anomaly_score"]


def test_argument_and_body_values_are_kept():
    data = reason(["ARGS:q", "ARGS_POST:body", "REQUEST_BODY", "REQUEST_FILENAME"], ["<script>", "x'--", "{}", "/a"])
    assert send(data)["report"]["data"]["matched_vars"] == data["matched_vars"]


def test_only_the_header_and_cookie_entries_are_blanked_and_alignment_holds():
    names = ["ARGS:id", "REQUEST_COOKIES:sid", "ARGS:name", "REQUEST_HEADERS:Cookie"]
    sent = send(reason(names, ["1' or 1=1", "secret", "<b>", "sid=secret"]))["report"]["data"]
    assert sent["matched_var_names"] == names
    assert sent["matched_vars"] == ["1' or 1=1", "", "<b>", ""]


@pytest.mark.parametrize("name", ["REQUEST_HEADERS", "REQUEST_COOKIES", "request_headers:cookie", "Request_Cookies:SID", "&REQUEST_HEADERS"])
def test_bare_and_mixed_case_variable_names_match(name):
    assert send(reason([name], ["value"]))["report"]["data"]["matched_vars"] == [""]


@pytest.mark.parametrize("name", ["REQUEST_HEADERS_NAMES:x", "REQUEST_COOKIES_NAMES:x", "ARGS_NAMES:x", "XML:/a"])
def test_similar_prefixes_are_not_redacted(name):
    assert send(reason([name], ["value"]))["report"]["data"]["matched_vars"] == ["value"]


def test_lists_that_lost_alignment_drop_the_values_altogether():
    sent = send(reason(["REQUEST_HEADERS:Cookie", "ARGS:a"], ["only-one-value"]))["report"]["data"]
    assert "matched_vars" not in sent
    assert sent["matched_var_names"] == ["REQUEST_HEADERS:Cookie", "ARGS:a"]


def test_values_without_names_are_dropped():
    sent = send({"ids": ["1"], "matched_vars": ["v"]})["report"]["data"]
    assert "matched_vars" not in sent and sent["ids"] == ["1"]


def test_reason_data_without_matched_values_is_unchanged():
    data = {"ids": ["949110"], "msgs": ["m"], "anomaly_score": ["5"]}
    assert send(data)["report"]["data"] == data


def test_the_original_reason_data_is_untouched():
    data = reason(["REQUEST_COOKIES:s", "ARGS:a"], ["secret", "v"])
    out = send(data)
    assert out["report"]["data"]["matched_vars"] == ["", "v"]
    assert out["original"] == data


# BUNKERNET_FILTER_HEADERS=no (the default): only the values matched in credential headers and cookies are blanked
# (test_bunkernet_report_credentials.py); the rest of the reason data goes out as ModSecurity produced it.
def test_default_sends_the_other_matched_values():
    data = reason(
        ["REQUEST_HEADERS:User-Agent", "REQUEST_HEADERS:X-Custom", "ARGS:q"],
        ["curl/8", "custom", "<script>"],
    )
    assert send(data, filter_headers="no")["report"]["data"] == data


def test_default_keeps_unaligned_matched_values_without_credential_names():
    data = reason(["ARGS:a", "REQUEST_HEADERS:User-Agent"], ["only-one-value"])
    assert send(data, filter_headers="no")["report"]["data"] == data
