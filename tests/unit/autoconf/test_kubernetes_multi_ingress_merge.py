"""Several Ingresses / Routes for one host are merged into a single service: slots renumbered, namespaces fenced, conflicts reported."""

import logging

import pytest
from _autoconf_helpers import attach_log

from controllers.KubernetesController import KubernetesController

MULTIPLE = {
    "REVERSE_PROXY_HOST": {"multiple": "reverse-proxy"},
    "REVERSE_PROXY_URL": {"multiple": "reverse-proxy"},
    "GRPC_HOST": {"multiple": "grpc"},
    "USE_ANTIBOT": {},
}


class K8s(KubernetesController):
    raw = []

    def _get_controller_services(self):
        return self.raw

    def _to_services(self, controller_service):
        return [dict(controller_service)]


@pytest.fixture
def ctrl(k8s_env):
    c = K8s()
    c._settings = MULTIPLE
    return c


def svc(namespace="prod", host="a.example.com", **settings):
    return {"SERVER_NAME": host, "NAMESPACE": namespace, **settings}


def test_nothing_to_merge(ctrl):
    assert ctrl._merge_services_by_server_name([]) == []


def test_distinct_hosts_pass_through_untouched_and_in_order(ctrl):
    first, second = svc(host="a.example.com"), svc(host="b.example.com")

    assert ctrl._merge_services_by_server_name([first, second]) == [first, second]


def test_lookup_lists_only_settings_that_can_be_repeated(ctrl):
    assert ctrl._build_multiple_groups_lookup() == {"REVERSE_PROXY_HOST": "reverse-proxy", "REVERSE_PROXY_URL": "reverse-proxy", "GRPC_HOST": "grpc"}


def test_slots_of_two_ingresses_are_renumbered_in_a_stable_order(ctrl):
    one = svc(USE_REVERSE_PROXY="yes", REVERSE_PROXY_HOST_1="http://zzz:80", REVERSE_PROXY_URL_1="/z")
    two = svc(USE_REVERSE_PROXY="yes", REVERSE_PROXY_HOST_1="http://aaa:80", REVERSE_PROXY_URL_1="/a")

    # the merge consumes its inputs (slots are removed in place), so each run gets copies
    [merged] = ctrl._merge_services_by_server_name([dict(one), dict(two)])
    [flipped] = ctrl._merge_services_by_server_name([dict(two), dict(one)])

    expected = {
        "SERVER_NAME": "a.example.com",
        "NAMESPACE": "prod",
        "USE_REVERSE_PROXY": "yes",
        "REVERSE_PROXY_HOST_1": "http://aaa:80",
        "REVERSE_PROXY_URL_1": "/a",
        "REVERSE_PROXY_HOST_2": "http://zzz:80",
        "REVERSE_PROXY_URL_2": "/z",
    }
    assert merged == expected
    assert flipped == expected


def test_numbering_starts_at_zero_when_configured(k8s_env):
    k8s_env.setenv("KUBERNETES_REVERSE_PROXY_SUFFIX_START", "0")
    c = K8s()
    c._settings = MULTIPLE
    one = svc(REVERSE_PROXY_HOST_1="http://a:1", REVERSE_PROXY_URL_1="/a")
    two = svc(REVERSE_PROXY_HOST="http://b:1", REVERSE_PROXY_URL="/b")

    [merged] = c._merge_services_by_server_name([one, two])

    assert (merged["REVERSE_PROXY_HOST"], merged["REVERSE_PROXY_HOST_1"]) == ("http://a:1", "http://b:1")


def test_prefixed_slots_keep_their_host_prefix(ctrl):
    one = svc(**{"a.example.com_REVERSE_PROXY_HOST_1": "http://a:1", "a.example.com_REVERSE_PROXY_URL_1": "/a"})
    two = svc(**{"a.example.com_REVERSE_PROXY_HOST": "http://b:1", "a.example.com_REVERSE_PROXY_URL": "/b"})

    [merged] = ctrl._merge_services_by_server_name([one, two])

    assert merged["a.example.com_REVERSE_PROXY_HOST_1"] == "http://a:1"
    assert merged["a.example.com_REVERSE_PROXY_HOST_2"] == "http://b:1"
    assert not any(key.startswith("REVERSE_PROXY") for key in merged)


def test_a_host_owned_by_one_namespace_cannot_be_taken_over_from_another(ctrl):
    """The first Ingress fixes the owning namespace; a second one for the same host elsewhere contributes nothing."""
    owner = svc("prod", REVERSE_PROXY_HOST_1="http://good:80", REVERSE_PROXY_URL_1="/", USE_ANTIBOT="captcha")
    intruder = svc("evil", REVERSE_PROXY_HOST_1="http://evil:80", REVERSE_PROXY_URL_1="/", USE_ANTIBOT="no")
    log = attach_log(ctrl)

    [merged] = ctrl._merge_services_by_server_name([owner, intruder])

    assert merged["NAMESPACE"] == "prod"
    assert merged["USE_ANTIBOT"] == "captcha"
    assert merged["REVERSE_PROXY_HOST_1"] == "http://good:80"
    assert "REVERSE_PROXY_HOST_2" not in merged
    assert log.has("Skipping service for a.example.com from namespace evil: already owned by namespace prod", logging.WARNING)


def test_a_service_with_a_namespace_does_not_merge_with_one_without(ctrl):
    unscoped = {"SERVER_NAME": "a.example.com"}

    [merged] = ctrl._merge_services_by_server_name([unscoped, svc("prod", USE_ANTIBOT="captcha")])

    assert "USE_ANTIBOT" not in merged


def test_or_merge_keys_turn_yes_if_any_ingress_says_yes(ctrl):
    one = svc(USE_REVERSE_PROXY="no", USE_GRPC="no")
    two = svc(USE_REVERSE_PROXY="YES", **{"a.example.com_USE_CUSTOM_SSL": "yes"})

    [merged] = ctrl._merge_services_by_server_name([one, two])

    assert merged["USE_REVERSE_PROXY"] == "yes"
    assert merged["USE_CUSTOM_SSL"] == "yes"
    assert "USE_GRPC" not in merged


def test_scalar_conflicts_are_last_wins_with_a_warning(ctrl):
    ctrl._logger.setLevel(logging.INFO)
    log = attach_log(ctrl)
    ctrl._logger.setLevel(logging.INFO)

    [merged] = ctrl._merge_services_by_server_name([svc(USE_ANTIBOT="captcha"), svc(USE_ANTIBOT="javascript")])

    assert merged["USE_ANTIBOT"] == "javascript"
    assert log.has("Conflicting annotation for a.example.com: USE_ANTIBOT='captcha' overwritten by 'javascript'", logging.WARNING)


def test_prefixed_scalar_conflicts_report_the_bare_setting_name(ctrl):
    ctrl._logger.setLevel(logging.INFO)
    log = attach_log(ctrl)
    ctrl._logger.setLevel(logging.INFO)

    [merged] = ctrl._merge_services_by_server_name([svc(**{"a.example.com_USE_ANTIBOT": "captcha"}), svc(**{"a.example.com_USE_ANTIBOT": "no"})])

    assert merged["a.example.com_USE_ANTIBOT"] == "no"
    assert log.has("Conflicting annotation for a.example.com: USE_ANTIBOT='captcha' overwritten by 'no'", logging.WARNING)


def test_alias_lists_may_differ_without_a_warning(ctrl):
    log = attach_log(ctrl)

    [merged] = ctrl._merge_services_by_server_name([svc(host="a.example.com"), svc(host="a.example.com b.example.com")])

    assert merged["SERVER_NAME"] == "a.example.com b.example.com"
    assert not log.has("Conflicting annotation")


def test_agreeing_values_do_not_warn(ctrl):
    log = attach_log(ctrl)

    ctrl._merge_services_by_server_name([svc(USE_ANTIBOT="captcha"), svc(USE_ANTIBOT="captcha")])

    assert not log.has("Conflicting annotation")


def test_secrets_are_redacted_in_conflict_logs_unless_debugging(ctrl):
    log = attach_log(ctrl)
    ctrl._logger.setLevel(logging.INFO)

    ctrl._merge_services_by_server_name([svc(AUTH_BASIC_PASSWORD="hunter2"), svc(AUTH_BASIC_PASSWORD="hunter3")])

    text = " ".join(log.messages(logging.WARNING))
    assert "'<redacted>' overwritten by '<redacted>'" in text
    assert "hunter" not in text


def test_secrets_are_shown_when_the_logger_is_at_debug(ctrl):
    log = attach_log(ctrl)

    ctrl._merge_services_by_server_name([svc(API_KEY="k1"), svc(API_KEY="k2")])

    assert log.has("API_KEY='k1' overwritten by 'k2'", logging.WARNING)


@pytest.mark.parametrize("key", ["MY_PASSWORD", "x_secret_y", "TOKEN", "API_KEY", "PRIVATE_KEY", "AUTH_BASIC_USER"])
def test_every_sensitive_marker_redacts(ctrl, key):
    ctrl._logger.setLevel(logging.INFO)

    assert ctrl._format_conflict_value(key, "value") == "'<redacted>'"
    assert ctrl._format_conflict_value("USE_ANTIBOT", "value") == "'value'"


def test_extract_slots_removes_what_it_returns_and_keeps_scalars(ctrl):
    service = svc(REVERSE_PROXY_HOST="http://a", REVERSE_PROXY_HOST_3="http://c", GRPC_HOST_1="g", USE_ANTIBOT="captcha", UNKNOWN_2="x", _3="y")

    slots = ctrl._extract_slots(service, ctrl._build_multiple_groups_lookup(), "a.example.com_")

    assert slots == {
        "reverse-proxy": {
            0: {"REVERSE_PROXY_HOST": ("REVERSE_PROXY_HOST", "http://a", False)},
            3: {"REVERSE_PROXY_HOST": ("REVERSE_PROXY_HOST_3", "http://c", False)},
        },
        "grpc": {1: {"GRPC_HOST": ("GRPC_HOST_1", "g", False)}},
    }
    assert service == svc(USE_ANTIBOT="captcha", UNKNOWN_2="x", _3="y")


def test_write_slots_numbers_from_the_configured_start(ctrl):
    out = {}

    ctrl._write_slots(out, {"reverse-proxy": [{"REVERSE_PROXY_HOST": ("k", "a", True)}, {"REVERSE_PROXY_HOST": ("k", "b", False)}]}, "h_")

    assert out == {"h_REVERSE_PROXY_HOST_1": "a", "REVERSE_PROXY_HOST_2": "b"}


def test_get_services_merges_what_the_orchestrator_returns(ctrl):
    ctrl.raw = [
        svc(REVERSE_PROXY_HOST_1="http://b:1", REVERSE_PROXY_URL_1="/b"),
        svc(host="other.example.com"),
        svc(REVERSE_PROXY_HOST_1="http://a:1", REVERSE_PROXY_URL_1="/a"),
    ]

    services = ctrl.get_services()

    assert [s["SERVER_NAME"] for s in services] == ["a.example.com", "other.example.com"]
    assert services[0]["REVERSE_PROXY_HOST_1"] == "http://a:1"
    assert services[0]["REVERSE_PROXY_URL_2"] == "/b"


def test_a_lone_service_is_returned_as_is_even_with_gappy_slots(ctrl):
    only = svc(REVERSE_PROXY_HOST_5="http://a:1")

    assert ctrl._merge_services_by_server_name([only]) == [only]
