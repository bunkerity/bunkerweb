"""The setting regexes of `ALLOWED_METHODS`, `SERVER_NAME` and the multivalue header settings accept what nginx accepts.

`ALLOWED_METHODS` refused WebDAV and custom methods outside a fixed list, `SERVER_NAME` capped the whole
value at 255 characters instead of each domain, and the header lists refused a separator followed by more
than one space. Each value is run through the real `Configurator`, which drops a value the regex refuses and
keeps the default instead (an invalid `SERVER_NAME` is fatal). Refs #504, #534, #3411, #533, #2577.
"""

import pytest

from _t5_helpers import configured  # type: ignore

DEFAULT_METHODS = "GET|POST|HEAD|QUERY"


@pytest.mark.parametrize(
    "value",
    [
        "GET|POST|COPY|LOCK|MKCOL|MOVE|PROPFIND|PROPPATCH|UNLOCK",
        "GET|PUT|DELETE|PATCH|OPTIONS|TRACE|CONNECT",
        "REPORT|MKCALENDAR|PURGE",
        "GET|CCM_POST",
        "M-SEARCH",
    ],
)
def test_allowed_methods_keeps_webdav_and_custom_methods(value):
    assert configured(ALLOWED_METHODS=value)["ALLOWED_METHODS"] == value


@pytest.mark.parametrize("value", ["get|post", "GET||POST", "|GET", "GET|", "GE", "GET POST", "GET;POST", "GET|ccm_post"])
def test_allowed_methods_drops_a_malformed_list(value):
    assert configured(ALLOWED_METHODS=value)["ALLOWED_METHODS"] == DEFAULT_METHODS


def test_server_name_limits_each_domain_not_the_whole_value():
    domains = [".".join(f"{'a' * 60}{chr(97 + i)}" for _ in range(3)) + ".example.com" for i in range(6)]
    value = " ".join(domains)
    assert len(value) > 1000 and all(len(domain) <= 255 for domain in domains)

    assert configured(SERVER_NAME=value)["SERVER_NAME"] == value


def test_server_name_still_refuses_a_domain_over_255_characters():
    too_long = ".".join(["a" * 60] * 5) + ".example.com"
    assert len(too_long) > 255

    with pytest.raises(SystemExit):  # an invalid SERVER_NAME is fatal, the generator has nothing to serve
        configured(SERVER_NAME=f"www.example.com {too_long}")


@pytest.mark.parametrize(
    "setting,value",
    [
        ("REVERSE_PROXY_HEADERS", "X-A  a;  X-B b"),
        ("REVERSE_PROXY_HEADERS", "X-A a;   X-B   b"),
        ("REVERSE_PROXY_HEADERS_CLIENT", "X-A  a;  X-B b"),
        ("GRPC_HEADERS", "X-A  a;  X-B b"),
        ("REVERSE_PROXY_AUTH_REQUEST_SET", "$user  $upstream_http_x_user;  $mail $upstream_http_x_mail"),
    ],
)
def test_header_lists_accept_repeated_separator_spaces(setting, value):
    assert configured(**{setting: value})[setting] == value


@pytest.mark.parametrize("setting", ["REVERSE_PROXY_HEADERS", "REVERSE_PROXY_HEADERS_CLIENT", "GRPC_HEADERS"])
@pytest.mark.parametrize("value", [";X-A a", " X-A a", "X-A  ;", "X-A a;;X-B b"])
def test_header_lists_still_refuse_an_empty_or_misplaced_entry(setting, value):
    assert configured(**{setting: value})[setting] == ""
