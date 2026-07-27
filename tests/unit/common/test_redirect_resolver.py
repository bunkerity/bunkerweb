import pytest

from redirect_resolver import (  # type: ignore
    RedirectConflictError,
    config_servers,
    expand_service_redirects,
    inline_redirect_conflict,
    scan_prefixes,
)


class FakeDB:
    def __init__(self, service_redirects):
        self.service_redirects = service_redirects

    def get_service_redirects(self):
        return self.service_redirects


class BrokenDB:
    def get_service_redirects(self):
        raise RuntimeError("database unavailable")


def rule(name, from_path, to_url, status_code="301", append_request_uri=False):
    return {"name": name, "from_path": from_path, "to_url": to_url, "status_code": status_code, "append_request_uri": append_request_uri}


def multisite(**extra):
    return {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "REDIRECT_TO": "", "REDIRECT_FROM": "/", **extra}


def test_config_servers_and_scan_prefixes():
    assert config_servers({"MULTISITE": "yes", "SERVER_NAME": "a.com b.com"}) == ["a.com", "b.com"]
    assert config_servers({"MULTISITE": "no", "SERVER_NAME": "solo.com"}) == ["solo.com"]
    assert config_servers({"MULTISITE": "yes", "SERVER_NAME": "  "}) == []
    # A multisite service inherits unprefixed globals, so both prefixes must be scanned.
    assert scan_prefixes("a.com", True) == ["", "a.com_"]
    assert scan_prefixes("a.com", False) == [""]


def test_rules_take_the_first_free_suffix():
    config = multisite()
    snapshot = dict(config)
    out = expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com", "308", True)]}))
    assert out["app1.example.com_REDIRECT_FROM"] == "/docs"
    assert out["app1.example.com_REDIRECT_TO"] == "https://docs.example.com"
    assert out["app1.example.com_REDIRECT_TO_STATUS_CODE"] == "308"
    assert out["app1.example.com_REDIRECT_TO_REQUEST_URI"] == "yes"
    assert config == snapshot  # the caller's dict is never mutated in place


def test_inline_rules_keep_their_suffix():
    config = multisite(**{"app1.example.com_REDIRECT_FROM": "/old", "app1.example.com_REDIRECT_TO": "https://inline.example.com"})
    out = expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))
    assert out["app1.example.com_REDIRECT_TO"] == "https://inline.example.com"
    assert out["app1.example.com_REDIRECT_FROM_1"] == "/docs"
    assert out["app1.example.com_REDIRECT_TO_1"] == "https://docs.example.com"


def test_a_global_inline_rule_occupies_the_suffix_it_renders_on():
    # Without this the resource would take suffix 0 on the service and shadow the inherited
    # global rule, silently dropping it from the rendered configuration.
    config = multisite(**{"REDIRECT_FROM": "/global", "REDIRECT_TO": "https://global.example.com"})
    out = expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))
    assert "app1.example.com_REDIRECT_TO" not in out
    assert out["app1.example.com_REDIRECT_TO_1"] == "https://docs.example.com"


def test_a_service_specific_blank_frees_an_inherited_suffix():
    config = multisite(**{"REDIRECT_FROM": "/global", "REDIRECT_TO": "https://global.example.com", "app1.example.com_REDIRECT_TO": ""})
    out = expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))
    assert out["app1.example.com_REDIRECT_TO"] == "https://docs.example.com"


def test_suffixed_lookalike_settings_are_not_mistaken_for_rules():
    # REDIRECT_TO_REQUEST_URI and REDIRECT_TO_STATUS_CODE both start with REDIRECT_TO.
    config = multisite(**{"app1.example.com_REDIRECT_TO_REQUEST_URI": "yes", "app1.example.com_REDIRECT_TO_STATUS_CODE": "302"})
    out = expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))
    assert out["app1.example.com_REDIRECT_TO"] == "https://docs.example.com"


def test_order_is_stable_and_expansion_is_idempotent():
    config = multisite()
    rules = [rule("a", "/1", "https://one.example.com"), rule("b", "/2", "https://two.example.com")]
    first = expand_service_redirects(config, FakeDB({"app1.example.com": rules}))
    second = expand_service_redirects(config, FakeDB({"app1.example.com": rules}))
    assert first == second
    assert first["app1.example.com_REDIRECT_FROM"] == "/1"
    assert first["app1.example.com_REDIRECT_FROM_1"] == "/2"


def test_non_multisite_uses_unprefixed_keys():
    config = {"MULTISITE": "no", "SERVER_NAME": "solo.example.com", "REDIRECT_TO": ""}
    out = expand_service_redirects(config, FakeDB({"solo.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))
    assert out["REDIRECT_FROM"] == "/docs"
    assert out["REDIRECT_TO"] == "https://docs.example.com"


def test_conflict_with_an_inline_rule_aborts_generation():
    config = multisite(**{"app1.example.com_REDIRECT_FROM": "/docs", "app1.example.com_REDIRECT_TO": "https://inline.example.com"})
    with pytest.raises(RedirectConflictError, match="its own inline redirect"):
        expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))


def test_conflict_between_two_resources_aborts_generation():
    rules = [rule("a", "/dup", "https://one.example.com"), rule("b", "/dup", "https://two.example.com")]
    with pytest.raises(RedirectConflictError, match="another redirect"):
        expand_service_redirects(multisite(), FakeDB({"app1.example.com": rules}))


def test_conflict_with_a_proxied_location_aborts_generation():
    # reverseproxy and grpc render a `location` into the same server as redirect does, so a
    # path they already serve is not available to a redirect either.
    for host_setting, url_setting, label in (
        ("app1.example.com_REVERSE_PROXY_HOST", "app1.example.com_REVERSE_PROXY_URL", "reverse proxy"),
        ("app1.example.com_GRPC_HOST", "app1.example.com_GRPC_URL", "gRPC"),
    ):
        config = multisite(**{host_setting: "http://backend", url_setting: "/docs"})
        with pytest.raises(RedirectConflictError, match=f"already served by its {label} configuration"):
            expand_service_redirects(config, FakeDB({"app1.example.com": [rule("docs", "/docs", "https://docs.example.com")]}))


def test_untouched_when_nothing_applies():
    config = multisite()
    assert expand_service_redirects(config, None) == config
    assert expand_service_redirects(config, FakeDB({})) == config
    assert expand_service_redirects(config, FakeDB({"other.example.com": [rule("docs", "/docs", "https://x.example.com")]})) == config


def test_a_database_failure_degrades_instead_of_aborting(quiet_logger):
    # A transient database problem must not take configuration generation down; only a real
    # conflict does.
    config = multisite()
    assert expand_service_redirects(config, BrokenDB(), quiet_logger) == config


def test_inline_redirect_conflict_mirrors_the_resource_side_check():
    config = {"MULTISITE": "yes", "app1.example.com_REDIRECT_FROM": "/docs", "app1.example.com_REDIRECT_TO": "https://inline.example.com"}
    assert "already serves /docs through an attached resource" in inline_redirect_conflict(config, "app1.example.com", ["/docs"])
    assert inline_redirect_conflict(config, "app1.example.com", ["/other"]) == ""
    assert inline_redirect_conflict(config, "app1.example.com", []) == ""
