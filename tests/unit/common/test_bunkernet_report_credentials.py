"""A BunkerNet report never carries credential headers or the values matched in them, whatever ``BUNKERNET_FILTER_HEADERS`` says.

``Cookie``, ``Authorization`` and ``Proxy-Authorization`` are dropped from the report headers, and a ModSecurity
match on a cookie or one of those headers keeps its variable name but not its value. Every other header, the
query string and the argument and body values stay. With ``BUNKERNET_FILTER_HEADERS=yes`` the allowlist and the
blanking of every matched header and cookie value apply as before. Same Lua harness as
``test_bunkernet_report_headers.py``.
"""

import pytest
from _lua_state_helpers import LUA  # type: ignore
from test_bunkernet_report_headers import send as send_headers  # type: ignore
from test_bunkernet_report_redaction import reason, send as send_reason  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

CREDENTIALS = {"Cookie": "session=abc", "Authorization": "Bearer t0ken", "Proxy-Authorization": "Basic Zm9v"}
OTHERS = {"User-Agent": "Mozilla/5.0", "X-Api-Key": "k", "Referer": "https://example.com/private", "Host": "www.example.com"}


@pytest.mark.parametrize("filter_headers", ["no", "yes"])
def test_credential_headers_are_never_reported(filter_headers):
    headers = send_headers({**OTHERS, **CREDENTIALS}, filter_headers=filter_headers)["report"]["headers"]
    for name in CREDENTIALS:
        assert name.lower() not in headers


def test_other_headers_stay_when_the_filter_is_off():
    headers = send_headers({**OTHERS, **CREDENTIALS}, filter_headers="no")["report"]["headers"]
    assert headers == {name.lower(): value for name, value in OTHERS.items()}


def test_the_filter_keeps_its_allowlist():
    headers = send_headers({**OTHERS, **CREDENTIALS}, filter_headers="yes")["report"]["headers"]
    assert headers == {"user-agent": "Mozilla/5.0"}


def test_credential_names_match_whatever_their_case_and_multi_values_go_too():
    headers = send_headers({"COOKIE": ["a=1", "b=2"], "aUtHoRiZaTiOn": "x", "proxy-authorization": "y", "Accept": "*/*"}, filter_headers="no")["report"][
        "headers"
    ]
    assert headers == {"accept": "*/*"}


def test_only_credentials_means_an_empty_object():
    assert send_headers(CREDENTIALS, filter_headers="no")["report"]["headers"] == {}


def test_the_query_string_and_the_other_fields_stay():
    report = send_headers({**OTHERS, **CREDENTIALS}, filter_headers="no")["report"]
    assert report["url"] == "/login?next=%2Fadmin"
    assert (report["ip"], report["reason"], report["method"], report["server_name"]) == ("203.0.113.5", "blacklist", "POST", "www.example.com")


NAMES = [
    "REQUEST_COOKIES:session",
    "REQUEST_HEADERS:Authorization",
    "REQUEST_HEADERS:proxy-authorization",
    "REQUEST_HEADERS:Cookie",
    "REQUEST_HEADERS:User-Agent",
    "ARGS:q",
    "ARGS_POST:body",
    "REQUEST_BODY",
]
VALUES = ["abc123", "Bearer t0ken", "Basic Zm9v", "session=abc", "curl/8", "<script>", "x'--", "{}"]


def test_values_matched_in_credential_headers_are_blanked_without_the_filter():
    sent = send_reason(reason(NAMES, VALUES), filter_headers="no")["report"]["data"]
    assert sent["matched_var_names"] == NAMES
    assert sent["matched_vars"] == ["", "", "", "", "curl/8", "<script>", "x'--", "{}"]


def test_the_filter_still_blanks_every_header_and_cookie_value():
    sent = send_reason(reason(NAMES, VALUES), filter_headers="yes")["report"]["data"]
    assert sent["matched_vars"] == ["", "", "", "", "", "<script>", "x'--", "{}"]


@pytest.mark.parametrize("name", ["REQUEST_COOKIES", "REQUEST_HEADERS", "request_cookies:SID", "request_headers:COOKIE", "&REQUEST_HEADERS:Authorization"])
def test_credential_variable_names_match_in_any_case_and_the_whole_collections_count(name):
    assert send_reason(reason([name], ["value"]), filter_headers="no")["report"]["data"]["matched_vars"] == [""]


@pytest.mark.parametrize(
    "name", ["REQUEST_HEADERS:User-Agent", "REQUEST_HEADERS:X-Custom", "REQUEST_HEADERS_NAMES:x", "REQUEST_COOKIES_NAMES:x", "ARGS_NAMES:x", "REQUEST_URI"]
)
def test_other_variables_keep_their_value_without_the_filter(name):
    assert send_reason(reason([name], ["value"]), filter_headers="no")["report"]["data"]["matched_vars"] == ["value"]


def test_unpaired_values_are_dropped_when_a_credential_name_is_listed():
    sent = send_reason(reason(["REQUEST_HEADERS:Cookie", "ARGS:a"], ["only-one-value"]), filter_headers="no")["report"]["data"]
    assert "matched_vars" not in sent
    assert sent["matched_var_names"] == ["REQUEST_HEADERS:Cookie", "ARGS:a"]


def test_unpaired_values_stay_when_no_credential_name_is_listed():
    data = reason(["ARGS:a", "ARGS:b"], ["only-one-value"])
    assert send_reason(data, filter_headers="no")["report"]["data"] == data


def test_values_without_names_are_dropped():
    sent = send_reason({"ids": ["1"], "matched_vars": ["v"]}, filter_headers="no")["report"]["data"]
    assert "matched_vars" not in sent and sent["ids"] == ["1"]


def test_reason_data_without_matched_values_is_unchanged():
    data = {"ids": ["949110"], "msgs": ["m"], "anomaly_score": ["5"]}
    assert send_reason(data, filter_headers="no")["report"]["data"] == data


def test_the_original_reason_data_is_untouched():
    data = reason(["REQUEST_COOKIES:s", "ARGS:a"], ["secret", "v"])
    out = send_reason(data, filter_headers="no")
    assert out["report"]["data"]["matched_vars"] == ["", "v"]
    assert out["original"] == data
