import pytest

from upstream_resolver import (  # type: ignore
    UpstreamConflictError,
    expand_service_upstreams,
    inline_upstream_conflict,
    server_directive,
)


class FakeDB:
    def __init__(self, service_upstreams):
        self.service_upstreams = service_upstreams

    def get_service_upstreams(self):
        return self.service_upstreams


class BrokenDB:
    def get_service_upstreams(self):
        raise RuntimeError("database unavailable")


def pool(name, match_path="/", servers=None, method="round_robin", keepalive=None, protocol="http", backend_ssl=False):
    return {
        "name": name,
        "match_path": match_path if protocol != "stream" else "",
        "protocol": protocol,
        "backend_ssl": backend_ssl,
        "method": method,
        "keepalive": keepalive,
        "servers": servers if servers is not None else [{"host": "10.0.0.1:8080"}],
    }


def multisite(**extra):
    return {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "REVERSE_PROXY_HOST": "", "REVERSE_PROXY_URL": "/", **extra}


def test_no_attachment_leaves_the_config_untouched():
    config = multisite()
    assert expand_service_upstreams(config, FakeDB({})) == config
    assert expand_service_upstreams(config, None) == config


def test_a_database_failure_degrades_instead_of_breaking_generation():
    # A transient DB problem must not take configuration generation down with it.
    config = multisite()
    assert expand_service_upstreams(config, BrokenDB()) == config


def test_attachment_fills_the_first_free_suffix_and_declares_the_pool():
    out = expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("web_pool")]}))

    assert out["app1.example.com_REVERSE_PROXY_URL"] == "/"
    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "http://web_pool"
    # Without this the whole reverse-proxy template is skipped and the attachment renders
    # nothing at all.
    assert out["app1.example.com_USE_REVERSE_PROXY"] == "yes"
    assert out["UPSTREAM_NAME_0"] == "web_pool"
    assert out["UPSTREAM_METHOD_0"] == "round_robin"
    assert out["UPSTREAM_SERVERS_0"] == "10.0.0.1:8080"
    assert out["UPSTREAM_KEEPALIVE_0"] == ""


def test_inline_locations_keep_their_suffixes():
    config = multisite(**{"app1.example.com_REVERSE_PROXY_HOST": "http://legacy", "app1.example.com_REVERSE_PROXY_URL": "/legacy"})
    out = expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool")]}))

    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "http://legacy"
    assert out["app1.example.com_REVERSE_PROXY_URL"] == "/legacy"
    assert out["app1.example.com_REVERSE_PROXY_HOST_1"] == "http://web_pool"
    assert out["app1.example.com_REVERSE_PROXY_URL_1"] == "/"


def test_a_global_inline_location_is_not_overwritten():
    # Templator merges globals under server-specific settings, so scanning only the prefixed
    # keys would hand the pool the suffix the global rule renders on and drop it silently.
    config = multisite(REVERSE_PROXY_HOST="http://global", REVERSE_PROXY_URL="/global")
    out = expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool")]}))

    assert out["REVERSE_PROXY_HOST"] == "http://global"
    assert out["app1.example.com_REVERSE_PROXY_HOST_1"] == "http://web_pool"


def test_a_blank_inline_host_frees_its_suffix():
    config = multisite(**{"app1.example.com_REVERSE_PROXY_HOST": "", "app1.example.com_REVERSE_PROXY_URL": "/legacy"})
    out = expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool", match_path="/legacy")]}))
    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "http://web_pool"


def test_a_pool_shared_by_two_services_is_declared_once():
    shared = pool("web_pool")
    out = expand_service_upstreams(
        {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com app2.example.com"},
        FakeDB({"app1.example.com": [shared], "app2.example.com": [shared]}),
    )

    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "http://web_pool"
    assert out["app2.example.com_REVERSE_PROXY_HOST"] == "http://web_pool"
    assert out["UPSTREAM_NAME_0"] == "web_pool"
    assert "UPSTREAM_NAME_1" not in out


def test_pool_declarations_are_ordered_by_name_for_a_stable_config_hash():
    first = expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("zeta", "/z"), pool("alpha", "/a")]}))
    second = expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("zeta", "/z"), pool("alpha", "/a")]}))
    assert first == second
    assert (first["UPSTREAM_NAME_0"], first["UPSTREAM_NAME_1"]) == ("alpha", "zeta")


def test_only_attached_pools_are_declared():
    # NGINX resolves upstream server names at load, so declaring a pool nothing uses would let
    # a stale backend fail the reload of a configuration that does not even reference it.
    out = expand_service_upstreams({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com"}, FakeDB({"app2.example.com": [pool("orphan")]}))
    assert not any(key.startswith("UPSTREAM_NAME") for key in out)


def test_conflicting_paths_abort_generation():
    with pytest.raises(UpstreamConflictError, match="another upstream"):
        expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("web_pool"), pool("other_pool")]}))

    config = multisite(**{"app1.example.com_REVERSE_PROXY_HOST": "http://legacy", "app1.example.com_REVERSE_PROXY_URL": "/"})
    with pytest.raises(UpstreamConflictError, match="its own inline backend"):
        expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool")]}))


def test_a_grpc_pool_drives_the_grpc_settings():
    out = expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("api_pool", "/rpc", protocol="grpc")]}))

    assert out["app1.example.com_GRPC_URL"] == "/rpc"
    assert out["app1.example.com_GRPC_HOST"] == "grpc://api_pool"
    assert out["app1.example.com_USE_GRPC"] == "yes"
    # The reverse proxy plugin must not be turned on for a gRPC-only service.
    assert f"app1.example.com_{'USE_REVERSE_PROXY'}" not in out
    assert out["UPSTREAM_PROTOCOL_0"] == "grpc"


def test_http_and_grpc_pools_use_separate_suffixes_but_one_path_namespace():
    # Both plugins emit a `location` into the same server, so NGINX would refuse two blocks
    # with the same URI outright — the paths must not collide even though the settings do not.
    out = expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("web_pool", "/"), pool("api_pool", "/rpc", protocol="grpc")]}))
    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "http://web_pool"
    assert out["app1.example.com_GRPC_HOST"] == "grpc://api_pool"
    assert out["app1.example.com_GRPC_URL"] == "/rpc"

    with pytest.raises(UpstreamConflictError, match="another upstream"):
        expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("web_pool", "/"), pool("api_pool", "/", protocol="grpc")]}))


def test_an_inline_grpc_location_reserves_its_path_for_http_pools_too():
    config = multisite(**{"app1.example.com_GRPC_HOST": "grpc://legacy:50051", "app1.example.com_GRPC_URL": "/rpc"})
    with pytest.raises(UpstreamConflictError, match="its own inline backend"):
        expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool", "/rpc")]}))


def test_backend_ssl_picks_the_tls_scheme():
    out = expand_service_upstreams(
        multisite(), FakeDB({"app1.example.com": [pool("web_pool", "/", backend_ssl=True), pool("api_pool", "/rpc", protocol="grpc", backend_ssl=True)]})
    )
    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "https://web_pool"
    assert out["app1.example.com_GRPC_HOST"] == "grpcs://api_pool"


def test_a_stream_pool_replaces_the_implicit_per_service_upstream():
    out = expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("tcp_pool", protocol="stream")]}))

    # Prefixed so it can never collide with the per-service upstream stream.conf names after
    # the service; the operator never sees this name.
    assert out["app1.example.com_REVERSE_PROXY_UPSTREAM"] == "bw_stream_tcp_pool"
    assert out["app1.example.com_USE_REVERSE_PROXY"] == "yes"
    assert out["UPSTREAM_NAME_0"] == "bw_stream_tcp_pool"
    assert out["UPSTREAM_PROTOCOL_0"] == "stream"
    # A stream server has no location, so no per-service path settings are written at all.
    assert not any(key.startswith("app1.example.com_REVERSE_PROXY_URL") for key in out)
    assert not any(key.startswith("app1.example.com_REVERSE_PROXY_HOST") for key in out)


def test_a_service_cannot_have_two_stream_pools():
    with pytest.raises(UpstreamConflictError, match="two stream upstreams"):
        expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("tcp_pool", protocol="stream"), pool("other_pool", protocol="stream")]}))


def test_a_stream_pool_coexists_with_http_pools_on_other_services():
    out = expand_service_upstreams(
        {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com app2.example.com"},
        FakeDB({"app1.example.com": [pool("web_pool", "/")], "app2.example.com": [pool("tcp_pool", protocol="stream")]}),
    )
    assert out["app1.example.com_REVERSE_PROXY_HOST"] == "http://web_pool"
    assert out["app2.example.com_REVERSE_PROXY_UPSTREAM"] == "bw_stream_tcp_pool"
    assert {out["UPSTREAM_PROTOCOL_0"], out["UPSTREAM_PROTOCOL_1"]} == {"http", "stream"}


def test_a_redirect_on_the_same_path_aborts_generation():
    # redirect renders `location <path> { return 3xx; }` into the same server as proxy_pass, and
    # NGINX refuses two locations with the same URI. Redirects are already flattened into
    # REDIRECT_* by the time this resolver runs, so both inline and resource-backed ones count.
    config = multisite(**{"app1.example.com_REDIRECT_TO": "https://x.example.com", "app1.example.com_REDIRECT_FROM": "/"})
    with pytest.raises(UpstreamConflictError, match="already served by its redirect configuration"):
        expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool", "/")]}))

    # A different path is fine.
    out = expand_service_upstreams(config, FakeDB({"app1.example.com": [pool("web_pool", "/api")]}))
    assert out["app1.example.com_REVERSE_PROXY_URL"] == "/api"


def test_conflict_messages_say_what_to_do():
    with pytest.raises(UpstreamConflictError) as excinfo:
        expand_service_upstreams(multisite(), FakeDB({"app1.example.com": [pool("web_pool"), pool("other_pool")]}))
    message = str(excinfo.value)
    assert "other_pool" in message and "/" in message and "app1.example.com" in message
    assert "Detach one of them, or move one to another path" in message


def test_single_site_uses_unprefixed_keys():
    out = expand_service_upstreams({"MULTISITE": "no", "SERVER_NAME": "app1.example.com"}, FakeDB({"app1.example.com": [pool("web_pool")]}))
    assert out["REVERSE_PROXY_HOST"] == "http://web_pool"
    assert out["USE_REVERSE_PROXY"] == "yes"


def test_server_directive_omits_defaults():
    assert server_directive({"host": "10.0.0.1:8080"}) == "10.0.0.1:8080"
    assert server_directive({"host": "10.0.0.1", "weight": 1, "max_fails": 1, "fail_timeout": "10s"}) == "10.0.0.1"
    assert (
        server_directive({"host": "10.0.0.1", "weight": 3, "max_fails": 2, "fail_timeout": "30s", "backup": True, "down": True})
        == "10.0.0.1 weight=3 max_fails=2 fail_timeout=30s backup down"
    )


def test_servers_are_joined_for_the_template():
    out = expand_service_upstreams(
        multisite(),
        FakeDB({"app1.example.com": [pool("web_pool", servers=[{"host": "10.0.0.1"}, {"host": "10.0.0.2", "backup": True}], keepalive=8)]}),
    )
    assert out["UPSTREAM_SERVERS_0"] == "10.0.0.1;10.0.0.2 backup"
    assert out["UPSTREAM_KEEPALIVE_0"] == "8"


def test_inline_conflict_helper_mirrors_the_resolver():
    config = multisite(**{"app1.example.com_REVERSE_PROXY_HOST": "http://legacy", "app1.example.com_REVERSE_PROXY_URL": "/api"})
    error = inline_upstream_conflict(config, "app1.example.com", ["/api"])
    assert "already serves /api through an attached resource" in error and "use a different path here" in error
    assert inline_upstream_conflict(config, "app1.example.com", ["/other"]) == ""
    assert inline_upstream_conflict(config, "app1.example.com", []) == ""
