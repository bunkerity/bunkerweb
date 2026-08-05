from fixtures.seed import add_global_value, add_service, add_service_setting, add_setting, seed_minimal, session
from model import Plugins, ResourceAttachments, Resources, Upstreams, UpstreamServers  # type: ignore


def _seed_reverse_proxy_plugin(db) -> None:
    """Register the ``reverseproxy`` plugin and the inline settings the mixin inspects.

    The mixin flags this plugin as config-changed on every attachment and reads the inline
    ``REVERSE_PROXY_*`` and ``GRPC_*`` values to detect path conflicts, so a test that skips
    this seed silently exercises the "plugin not installed" degradation instead of the real
    path.
    """
    with session(db) as s:
        s.add(Plugins(id="reverseproxy", name="Reverse proxy", description="Reverse proxy settings.", version="1.0"))
    add_setting(db, "REVERSE_PROXY_HOST", plugin_id="general", context="multisite", multiple="reverse-proxy")
    add_setting(db, "GRPC_HOST", plugin_id="general", context="multisite", multiple="grpc")
    add_setting(db, "GRPC_URL", plugin_id="general", context="multisite", multiple="grpc")


SERVERS = [{"host": "10.0.0.1:8080"}, {"host": "10.0.0.2:8080", "weight": 3, "backup": True}]


def _create(db, *, name="web_pool", servers=None, **kwargs):
    resource_id, error = db.create_upstream(name=name, servers=servers if servers is not None else SERVERS, **kwargs)
    assert error == ""
    return resource_id


def _config_changed(db) -> bool:
    with session(db) as s:
        return bool(s.get(Plugins, "reverseproxy").config_changed)


def test_create_list_and_details(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db, description="Shared app backends", method="least_conn", keepalive=32)

    listing = db.get_upstreams()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["id"] == resource_id
    assert (item["name"], item["method"], item["keepalive"]) == ("web_pool", "least_conn", 32)
    assert [server["host"] for server in item["servers"]] == ["10.0.0.1:8080", "10.0.0.2:8080"]
    assert item["servers"][1]["weight"] == 3 and item["servers"][1]["backup"] is True
    assert item["services"] == []
    assert db.get_upstream_details(resource_id) == item
    assert db.get_upstream_details("missing") is None

    with session(db) as s:
        assert s.get(Resources, resource_id).type == "upstream"
        assert s.get(Upstreams, resource_id).method == "least_conn"
        # Server order is persisted, not incidental: it is the order NGINX receives them in.
        assert [row.order for row in s.query(UpstreamServers).order_by(UpstreamServers.order)] == [0, 1]


def test_create_is_not_a_config_change_until_attached(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    _create(db)
    # A pool attached to nothing renders nothing; flagging it would trigger a pointless
    # generation and reload.
    assert _config_changed(db) is False


def test_duplicate_name_is_refused(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    _create(db)
    _, error = db.create_upstream(name="web_pool", servers=[{"host": "10.0.0.9"}])
    assert "already exists" in error


def test_pool_names_cannot_look_like_hostnames(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    # NGINX resolves a variable proxy_pass against the upstream names first, so a pool named
    # like a host would hijack every proxy_pass to that host.
    _, error = db.create_upstream(name="api.internal", servers=[{"host": "10.0.0.9"}])
    assert "letters, digits" in error.lower()


def test_server_values_are_validated(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)

    _, error = db.create_upstream(name="empty", servers=[])
    assert error == "An upstream needs at least one server"

    _, error = db.create_upstream(name="scheme", servers=[{"host": "http://10.0.0.1"}])
    assert "without a scheme" in error

    _, error = db.create_upstream(name="dupe", servers=[{"host": "10.0.0.1:80"}, {"host": "10.0.0.1:80"}])
    assert "listed twice" in error

    _, error = db.create_upstream(name="badtimeout", servers=[{"host": "10.0.0.1", "fail_timeout": "soon"}])
    assert "fail_timeout" in error

    _, error = db.create_upstream(name="allbackup", servers=[{"host": "10.0.0.1", "backup": True}])
    assert error == "An upstream needs at least one non-backup server"

    _, error = db.create_upstream(name="alldown", servers=[{"host": "10.0.0.1", "down": True}])
    assert error == "At least one server must be up"

    # NGINX itself refuses backup servers with ip_hash, so the combination never reaches a
    # configuration test.
    _, error = db.create_upstream(name="hashbackup", method="ip_hash", servers=SERVERS)
    assert "ip_hash" in error

    _, error = db.create_upstream(name="badmethod", method="magic", servers=[{"host": "10.0.0.1"}])
    assert "Invalid load balancing method" in error

    _, error = db.create_upstream(name="zerokeepalive", keepalive=0, servers=[{"host": "10.0.0.1"}])
    assert "Keepalive" in error

    assert db.get_upstreams()["total"] == 0


def test_ipv6_and_bare_hostnames_are_accepted(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db, name="mixed", servers=[{"host": "[2001:db8::1]:8080"}, {"host": "backend.internal"}])
    assert [server["host"] for server in db.get_upstream_details(resource_id)["servers"]] == ["[2001:db8::1]:8080", "backend.internal"]


def test_attach_share_and_detach(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    add_service(db, "app2.example.com")
    resource_id = _create(db)

    assert db.attach_upstream(resource_id, "app1.example.com") == ""
    assert _config_changed(db) is True
    assert db.attach_upstream(resource_id, "app2.example.com", match_path="/api") == ""
    assert db.get_upstream_details(resource_id)["services"] == [
        {"service_id": "app1.example.com", "match_path": "/"},
        {"service_id": "app2.example.com", "match_path": "/api"},
    ]

    # The same pool serves both services, which is the point of a shared resource.
    service_upstreams = db.get_service_upstreams()
    assert set(service_upstreams) == {"app1.example.com", "app2.example.com"}
    assert service_upstreams["app2.example.com"][0]["match_path"] == "/api"
    assert [server["host"] for server in service_upstreams["app1.example.com"][0]["servers"]] == ["10.0.0.1:8080", "10.0.0.2:8080"]

    assert db.attach_upstream(resource_id, "app1.example.com") == ""  # idempotent
    assert len(db.get_upstream_details(resource_id)["services"]) == 2

    # The same pool on a second path of one service is a different location, not a duplicate.
    assert db.attach_upstream(resource_id, "app1.example.com", match_path="/static") == ""
    assert len(db.get_upstream_details(resource_id)["services"]) == 3

    assert db.detach_upstream(resource_id, "app1.example.com", match_path="/static") == ""
    assert db.detach_upstream(resource_id, "app1.example.com") == ""
    assert db.get_upstream_details(resource_id)["services"] == [{"service_id": "app2.example.com", "match_path": "/api"}]
    assert db.detach_upstream(resource_id, "app1.example.com") == "Upstream attachment not found"


def test_service_upstreams_use_attachment_id_when_timestamps_tie(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    first = _create(db, name="zzz_first")
    second = _create(db, name="aaa_second", servers=[{"host": "10.0.0.3"}])
    assert db.attach_upstream(first, "app1.example.com", match_path="/first") == ""
    assert db.attach_upstream(second, "app1.example.com", match_path="/second") == ""
    with session(db) as db_session:
        attachments = db_session.query(ResourceAttachments).filter_by(service_id="app1.example.com").order_by(ResourceAttachments.id).all()
        attachments[1].creation_date = attachments[0].creation_date

    assert [item["name"] for item in db.get_service_upstreams()["app1.example.com"]] == ["zzz_first", "aaa_second"]


def test_name_only_update_flags_attached_upstream(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db)
    assert db.attach_upstream(resource_id, "app1.example.com") == ""
    with session(db) as db_session:
        db_session.get(Plugins, "reverseproxy").config_changed = False

    assert db.update_upstream(resource_id, name="renamed_pool") == ""
    assert db.get_upstream_details(resource_id)["name"] == "renamed_pool"
    assert _config_changed(db) is True


def test_server_type_flip_is_rejected_while_upstream_is_attached(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    add_setting(db, "SERVER_TYPE", context="multisite", regex="^(http|stream)$", default="http")
    resource_id = _create(db)
    assert db.attach_upstream(resource_id, "app1.example.com") == ""

    result = db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com",
            "app1.example.com_SERVER_TYPE": "stream",
        },
        "ui",
    )

    assert result == "Cannot set app1.example.com_SERVER_TYPE to stream while a http upstream is attached to app1.example.com"


def test_attach_rejects_unknown_service_upstream_and_path(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db)
    assert db.attach_upstream(resource_id, "nope.example.com") == "Service not found"
    assert db.attach_upstream("missing", "app1.example.com") == "Upstream not found"
    assert "must start with /" in db.attach_upstream(resource_id, "app1.example.com", match_path="api")


def test_two_pools_cannot_share_a_path_on_one_service(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    first = _create(db)
    second = _create(db, name="other_pool", servers=[{"host": "10.0.0.3"}])

    assert db.attach_upstream(first, "app1.example.com", match_path="/api") == ""
    error = db.attach_upstream(second, "app1.example.com", match_path="/api")
    assert "already serves /api through the upstream “web_pool”" in error
    # A different path on the same service is fine.
    assert db.attach_upstream(second, "app1.example.com", match_path="/other") == ""


def test_inline_reverse_proxy_blocks_the_same_path(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_HOST", value="http://legacy:8080", suffix=1)
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_URL", value="/legacy", suffix=1)
    resource_id = _create(db)

    assert "already serves /legacy through its own reverse proxy settings" in db.attach_upstream(resource_id, "app1.example.com", match_path="/legacy")
    assert db.attach_upstream(resource_id, "app1.example.com", match_path="/") == ""


def test_a_blanked_inline_backend_does_not_block(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    # An empty host is exactly what the template skips, so its path is free for a pool.
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_HOST", value="", suffix=1)
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_URL", value="/legacy", suffix=1)
    resource_id = _create(db)
    assert db.attach_upstream(resource_id, "app1.example.com", match_path="/legacy") == ""


def test_global_inline_backend_blocks_every_service(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    add_global_value(db, setting_id="REVERSE_PROXY_HOST", value="http://global:8080", suffix=2)
    add_global_value(db, setting_id="REVERSE_PROXY_URL", value="/shared", suffix=2)
    resource_id = _create(db)
    assert "already serves /shared through its own reverse proxy settings" in db.attach_upstream(resource_id, "app1.example.com", match_path="/shared")


def test_update_replaces_servers_and_signals_only_when_attached(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db)

    assert db.update_upstream(resource_id, servers=[{"host": "10.1.0.1:9000"}]) == ""
    assert _config_changed(db) is False  # still attached to nothing
    assert [server["host"] for server in db.get_upstream_details(resource_id)["servers"]] == ["10.1.0.1:9000"]

    assert db.attach_upstream(resource_id, "app1.example.com") == ""
    with session(db) as s:
        s.query(Plugins).filter(Plugins.id == "reverseproxy").update({"config_changed": False})

    assert db.update_upstream(resource_id, method="least_conn", description="now shared") == ""
    assert _config_changed(db) is True
    details = db.get_upstream_details(resource_id)
    assert details["method"] == "least_conn" and details["description"] == "now shared"


def test_update_can_clear_the_keepalive(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db, keepalive=16)
    assert db.update_upstream(resource_id, clear_keepalive=True) == ""
    assert db.get_upstream_details(resource_id)["keepalive"] is None


def test_update_validates_the_new_method_against_the_stored_servers(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db)  # SERVERS carries a backup member
    assert "ip_hash" in db.update_upstream(resource_id, method="ip_hash")
    assert db.get_upstream_details(resource_id)["method"] == "round_robin"


def test_update_rejects_a_duplicate_name_and_unknown_id(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    _create(db)
    other = _create(db, name="other_pool", servers=[{"host": "10.0.0.3"}])
    assert "already exists" in db.update_upstream(other, name="web_pool")
    assert db.update_upstream("missing", name="whatever") == "Upstream not found"


def test_delete_is_refused_while_attached(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db)
    assert db.attach_upstream(resource_id, "app1.example.com") == ""

    assert db.delete_upstream(resource_id) == "Upstream is attached to a service"
    assert db.detach_upstream(resource_id, "app1.example.com") == ""
    assert db.delete_upstream(resource_id) == ""

    with session(db) as s:
        # The registry row, the typed row, its servers and the attachments go together.
        assert s.get(Resources, resource_id) is None
        assert s.get(Upstreams, resource_id) is None
        assert s.query(UpstreamServers).count() == 0
        assert s.query(ResourceAttachments).count() == 0
    assert db.delete_upstream(resource_id) == "Upstream not found"


def test_protocol_and_backend_ssl_round_trip(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db, name="api_pool", protocol="grpc", backend_ssl=True, servers=[{"host": "api.internal:50051"}])
    details = db.get_upstream_details(resource_id)
    assert details["protocol"] == "grpc" and details["backend_ssl"] is True

    _, error = db.create_upstream(name="bad", protocol="carrier_pigeon", servers=[{"host": "10.0.0.1"}])
    assert "Invalid protocol" in error

    # keepalive is an http upstream directive with no stream equivalent.
    _, error = db.create_upstream(name="streamalive", protocol="stream", keepalive=8, servers=[{"host": "10.0.0.1:5432"}])
    assert "Keepalive is not supported" in error


def _make_stream_service(db, service_id="app1.example.com"):
    """A stream upstream only fits a service whose SERVER_TYPE says it speaks TCP/UDP."""
    add_setting(db, "SERVER_TYPE", plugin_id="general", context="multisite")
    add_service_setting(db, service_id=service_id, setting_id="SERVER_TYPE", value="stream")


def test_a_stream_pool_takes_the_whole_service(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    _make_stream_service(db)
    resource_id = _create(db, name="tcp_pool", protocol="stream", servers=[{"host": "10.0.0.1:5432"}])

    # The requested path is dropped: a stream server has nothing to match it against.
    assert db.attach_upstream(resource_id, "app1.example.com", match_path="/ignored") == ""
    assert db.get_upstream_details(resource_id)["services"] == [{"service_id": "app1.example.com", "match_path": ""}]
    assert db.get_service_upstreams()["app1.example.com"][0]["protocol"] == "stream"

    other = _create(db, name="other_tcp", protocol="stream", servers=[{"host": "10.0.0.2:5432"}])
    error = db.attach_upstream(other, "app1.example.com")
    assert "already uses the upstream “tcp_pool”" in error and "Detach it first" in error


def test_protocol_must_match_the_service_kind(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    stream_pool = _create(db, name="tcp_pool", protocol="stream", servers=[{"host": "10.0.0.1:5432"}])
    http_pool = _create(db, name="web_pool2", servers=[{"host": "10.0.0.3"}])

    # app1 is an HTTP service (SERVER_TYPE defaults to http): a stream pool there would render
    # nothing at all.
    error = db.attach_upstream(stream_pool, "app1.example.com")
    assert "it is a http service" in error and "SERVER_TYPE is stream" in error

    # And the reverse is worse than a no-op: an http pool on a stream service puts a scheme in
    # a stream `server` directive, which NGINX refuses outright.
    add_service(db, "db.example.com")
    _make_stream_service(db, "db.example.com")
    error = db.attach_upstream(http_pool, "db.example.com", match_path="/")
    assert "it is a stream service" in error and "SERVER_TYPE is http" in error

    assert db.attach_upstream(stream_pool, "db.example.com") == ""
    assert db.attach_upstream(http_pool, "app1.example.com", match_path="/") == ""


def test_a_stream_pool_refuses_a_service_with_an_inline_backend(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    _make_stream_service(db)
    # On a stream service REVERSE_PROXY_HOST is the backend itself, not a location.
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_HOST", value="10.0.0.9:5432")
    resource_id = _create(db, name="tcp_pool", protocol="stream", servers=[{"host": "10.0.0.1:5432"}])
    error = db.attach_upstream(resource_id, "app1.example.com")
    assert "already has its own backend in REVERSE_PROXY_HOST" in error


def test_grpc_and_http_pools_share_the_location_namespace(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    http_pool = _create(db)
    grpc_pool = _create(db, name="api_pool", protocol="grpc", servers=[{"host": "api.internal:50051"}])

    assert db.attach_upstream(http_pool, "app1.example.com", match_path="/api") == ""
    # NGINX would refuse two location blocks with the same URI, whichever plugin emits them.
    assert "already serves /api through the upstream “web_pool”" in db.attach_upstream(grpc_pool, "app1.example.com", match_path="/api")
    assert db.attach_upstream(grpc_pool, "app1.example.com", match_path="/rpc") == ""


def test_an_inline_grpc_location_blocks_an_http_pool(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="GRPC_HOST", value="grpc://legacy:50051", suffix=1)
    add_service_setting(db, service_id="app1.example.com", setting_id="GRPC_URL", value="/rpc", suffix=1)
    resource_id = _create(db)
    assert "already serves /rpc through its own gRPC settings" in db.attach_upstream(resource_id, "app1.example.com", match_path="/rpc")


def test_protocol_cannot_change_while_attached(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db)
    assert db.attach_upstream(resource_id, "app1.example.com") == ""

    assert "Detach the upstream" in db.update_upstream(resource_id, protocol="stream")
    assert db.detach_upstream(resource_id, "app1.example.com") == ""
    assert db.update_upstream(resource_id, protocol="stream") == ""
    assert db.get_upstream_details(resource_id)["protocol"] == "stream"


def test_update_rejects_a_keepalive_that_the_new_protocol_forbids(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    resource_id = _create(db, keepalive=16)
    # The stored keepalive must be validated against the incoming protocol, not ignored.
    assert "Keepalive is not supported" in db.update_upstream(resource_id, protocol="stream")


def test_search_and_service_filter(db):
    seed_minimal(db)
    _seed_reverse_proxy_plugin(db)
    first = _create(db)
    _create(db, name="api_pool", servers=[{"host": "api.internal:9000"}], description="API tier")
    assert db.attach_upstream(first, "app1.example.com") == ""

    assert [item["name"] for item in db.get_upstreams(search="api")["items"]] == ["api_pool"]
    assert [item["name"] for item in db.get_upstreams(search="api.internal")["items"]] == ["api_pool"]
    assert [item["name"] for item in db.get_upstreams(service_id="app1.example.com")["items"]] == ["web_pool"]
    assert db.get_upstreams(service_id="nope.example.com")["total"] == 0
