"""Listen-port inventory, ``reuseport`` ownership and conflict report (``utils/ports.py``).

The module exists because two NGINX rules are about the SET of server blocks sharing an
``addr:port``, which no Jinja template can see -- it only ever renders one block:

  * a listen OPTION set by two blocks on one ``addr:port`` is fatal ("duplicate listen options",
    ``ngx_stream.c:489-497``), and ``reuseport`` is such an option;
  * ``ssl`` / ``proxy_protocol`` / ``http2`` are NOT, they are unioned silently
    (``ngx_http.c:1320-1352``) -- a warning, never a refusal.

The matrix below is the one in the conception (§8), including the case that made this a *live*
defect rather than a design nicety: two stream services that override nothing at all collide,
because ``LISTEN_STREAM_PORT`` defaults to 1337 and is multisite.
"""

import json
from pathlib import Path

import pytest

from ports import (  # type: ignore
    FATAL,
    HEALTHCHECK_PORT,
    PRIVILEGED_PORT_CEILING,
    WARNING,
    check_ports,
    collect_ports,
    drop_inherited_ports,
    http01_refusals,
    inventory,
    list_moved,
    parse_port,
    port_list_keys,
    port_list_setting,
    reserved_ports,
    services_from_config,
    stream_reuseport_owners,
    union_ports,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

HTTP = {"SERVER_TYPE": "http", "LISTEN_HTTP": "yes", "HTTP_PORT": "8080", "HTTPS_PORT": "8443"}
STREAM = {"SERVER_TYPE": "stream", "LISTEN_STREAM": "yes", "USE_TCP": "yes", "USE_UDP": "no", "LISTEN_STREAM_PORT": "1337"}


def levels(issues):
    return [issue.level for issue in issues]


class TestParsePort:
    @pytest.mark.parametrize("value,expected", [("8080", 8080), ("0", 0), ("65535", 65535), (" 8080 ", 8080)])
    def test_accepted(self, value, expected):
        assert parse_port(value) == expected

    @pytest.mark.parametrize("value", ["", "   ", "65536", "999999", "http", "-1", "80.5", None])
    def test_rejected(self, value):
        """Empty is "no listener", not an error -- every port setting documents it
        (settings.json:23). Out of range and non-numeric are simply not ports."""
        assert parse_port(value) is None


class TestCollectPorts:
    def test_base_and_numeric_suffixes_in_declaration_order(self):
        config = {"HTTP_PORT": "8080", "HTTP_PORT_1": "8081", "HTTP_PORT_2": "8082"}
        assert collect_ports(config, "HTTP_PORT") == ["8080", "8081", "8082"]

    def test_the_order_is_the_suffix_order_not_the_dict_order(self):
        """``list_moved`` and the Lua side both compare ORDERED sequences, and dict order is not a
        property of the configuration: a database read whose ``order_by`` has no suffix tiebreak
        returns whatever the engine gives back, and ``services_from_config`` APPENDS a service key
        that the globals did not carry. Lua's ``port_list`` has always sorted numerically; this is
        the same rule on the Python side."""
        assert collect_ports({"HTTP_PORT_1": "8081", "HTTP_PORT": "8080"}, "HTTP_PORT") == ["8080", "8081"]
        assert collect_ports({"HTTP_PORT_2": "8082", "HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}, "HTTP_PORT") == ["8080", "8081", "8082"]

    def test_suffixes_are_ordered_numerically_not_lexically(self):
        """``"10" < "2"`` as strings. Suffixes need not be contiguous either."""
        assert collect_ports({"HTTP_PORT": "8080", "HTTP_PORT_10": "8090", "HTTP_PORT_2": "8082"}, "HTTP_PORT") == ["8080", "8082", "8090"]

    def test_empty_values_are_dropped(self):
        """The ``and port`` guard of the per-service templates (server.conf:24), expressed once.
        The list-replacement rule of the conception (§2.2) NEEDS to write empty values, because
        ``dict.update`` can overwrite but never delete an inherited ``_N`` key."""
        assert collect_ports({"HTTP_PORT": "", "HTTP_PORT_1": "8081"}, "HTTP_PORT") == ["8081"]

    def test_the_ssl_stream_setting_is_not_a_repetition_of_the_plain_one(self):
        """``LISTEN_STREAM_PORT_SSL`` starts with ``LISTEN_STREAM_PORT_``. Requiring a numeric
        suffix is what keeps them apart; server-stream.conf:24 needs a second ``startswith`` for
        the same reason."""
        config = {"LISTEN_STREAM_PORT": "1337", "LISTEN_STREAM_PORT_SSL": "4242", "LISTEN_STREAM_PORT_SSL_1": "4243"}
        assert collect_ports(config, "LISTEN_STREAM_PORT") == ["1337"]
        assert collect_ports(config, "LISTEN_STREAM_PORT_SSL") == ["4242", "4243"]

    def test_a_lookalike_key_is_not_a_port(self):
        assert collect_ports({"HTTP_PORTS": "1", "HTTP_PORT_X": "2"}, "HTTP_PORT") == []


class TestStreamReuseportOwners:
    def test_a_single_service_owns_all_its_ports(self):
        """The byte-identity guarantee: a mono-service deployment renders exactly what the
        unconditional ``reuseport`` used to render."""
        owners = stream_reuseport_owners({"a": {**STREAM, "LISTEN_STREAM_PORT": "1337", "LISTEN_STREAM_PORT_1": "1338"}})
        assert owners["a"] == frozenset({"tcp:1337", "tcp:1338"})

    def test_default_configuration_two_stream_services_collide_on_1337(self):
        """PO-QUEUE 30, the live half of the defect: nothing is overridden here. Before the fix
        both blocks emitted ``reuseport`` and NGINX refused to start."""
        owners = stream_reuseport_owners({"a": dict(STREAM), "b": dict(STREAM)})
        assert owners["a"] == frozenset({"tcp:1337"})
        assert owners["b"] == frozenset()

    def test_tcp_and_udp_are_different_sockets(self):
        """``ngx_stream.c:414-416`` keys the port list on (port, type, family): UDP does not
        collide with TCP, so both may keep the option."""
        owners = stream_reuseport_owners({"a": {**STREAM, "USE_UDP": "no"}, "b": {**STREAM, "USE_TCP": "no", "USE_UDP": "yes"}})
        assert owners["a"] == frozenset({"tcp:1337"})
        assert owners["b"] == frozenset({"udp:1337"})

    def test_the_ssl_stream_port_is_never_owned(self):
        """ssl-certificate-stream-lua.conf:40 emits no ``reuseport``, so nothing to arbitrate --
        which is why two services may share LISTEN_STREAM_PORT_SSL today and start fine."""
        owners = stream_reuseport_owners({"a": {**STREAM, "LISTEN_STREAM_PORT": "", "LISTEN_STREAM_PORT_SSL": "4242"}})
        assert owners["a"] == frozenset()

    def test_an_http_service_keeps_owning_its_unused_stream_block(self):
        """Templator renders a server-stream.conf for an HTTP service too, but ``stream.conf:52``
        never includes it. That file cannot collide with anything, so it must render byte for byte
        what it rendered before -- and it must not steal the claim from a block that IS loaded."""
        owners = stream_reuseport_owners({"http-service": {**HTTP, "LISTEN_STREAM_PORT": "1337"}, "stream-service": dict(STREAM)})
        assert owners["http-service"] == frozenset({"tcp:1337"})
        assert owners["stream-service"] == frozenset({"tcp:1337"})

    def test_two_http_services_both_keep_their_unused_stream_block_intact(self):
        owners = stream_reuseport_owners({"a": {**HTTP, "LISTEN_STREAM_PORT": "1337"}, "b": {**HTTP, "LISTEN_STREAM_PORT": "1337"}})
        assert owners["a"] == owners["b"] == frozenset({"tcp:1337"})

    def test_listen_stream_no_renders_no_listener_so_owns_nothing(self):
        """server-stream.conf:27 gates the whole listen block on it; a service that renders no
        socket must not hold the option hostage for one that does."""
        owners = stream_reuseport_owners({"a": {**STREAM, "LISTEN_STREAM": "no"}, "b": dict(STREAM)})
        assert owners["a"] == frozenset()
        assert owners["b"] == frozenset({"tcp:1337"})

    def test_ownership_follows_declaration_order_and_is_stable(self):
        owners = stream_reuseport_owners({"b": dict(STREAM), "a": dict(STREAM)})
        assert owners["b"] == frozenset({"tcp:1337"})
        assert owners["a"] == frozenset()


class TestUnionPorts:
    def test_global_only_configuration_returns_the_global_list_unchanged(self):
        """This is what makes the default-server rendering byte-identical after the union
        replaces ``all.items()``: same values, same order."""
        assert union_ports({"HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}, {}, "HTTP_PORT") == ["8080", "8081"]

    def test_service_ports_are_appended_once_after_the_global_ones(self):
        services = {"a": {"HTTP_PORT": "9000"}, "b": {"HTTP_PORT": "9000", "HTTP_PORT_1": "9001"}}
        assert union_ports({"HTTP_PORT": "8080"}, services, "HTTP_PORT") == ["8080", "9000", "9001"]

    def test_a_service_port_equal_to_the_global_one_does_not_duplicate(self):
        assert union_ports({"HTTP_PORT": "8080"}, {"a": {"HTTP_PORT": "8080"}}, "HTTP_PORT") == ["8080"]


class TestInventory:
    def test_http_service_yields_its_plain_and_tls_listeners(self):
        got = {(listener.port, listener.ssl) for listener in inventory({"a": dict(HTTP)})}
        assert got == {(8080, False), (8443, True)}

    def test_listen_http_no_drops_the_plain_listener_only(self):
        got = {(listener.port, listener.ssl) for listener in inventory({"a": {**HTTP, "LISTEN_HTTP": "no"}})}
        assert got == {(8443, True)}

    def test_stream_service_yields_one_listener_per_protocol(self):
        got = {(listener.port, listener.proto) for listener in inventory({"a": {**STREAM, "USE_UDP": "yes"}})}
        assert got == {(1337, "tcp"), (1337, "udp")}

    def test_the_ssl_stream_listener_is_tcp_only(self):
        listeners = inventory({"a": {**STREAM, "USE_UDP": "yes", "LISTEN_STREAM_PORT_SSL": "4242"}})
        assert {listener.proto for listener in listeners if listener.port == 4242} == {"tcp"}

    def test_an_out_of_range_port_is_not_a_listener(self):
        assert inventory({"a": {**HTTP, "HTTP_PORT": "99999", "HTTPS_PORT": ""}}) == []


class TestCheckPorts:
    def test_two_http_services_may_share_a_port(self):
        """The normal multisite case: name-based virtual hosting on one port."""
        assert check_ports({"a": dict(HTTP), "b": dict(HTTP)}) == []

    def test_two_stream_services_on_one_tcp_port_are_no_longer_a_conflict(self):
        """Once ``reuseport`` is emitted once per addr:port, sharing is legal and SNI separates
        the services (``ngx_stream_core_module.c:80`` supports ``server_name``)."""
        assert check_ports({"a": dict(STREAM), "b": dict(STREAM)}) == []

    def test_http_and_stream_on_the_same_port_is_fatal(self):
        issues = check_ports({"a": {**HTTP, "HTTP_PORT": "1337", "HTTPS_PORT": ""}, "b": dict(STREAM)})
        assert levels(issues) == [FATAL]
        assert "port 1337/tcp is used by HTTP service(s) a and by stream service(s) b" in issues[0].message

    def test_udp_stream_does_not_conflict_with_an_http_port(self):
        """Different socket type, so no bind clash -- the report must not cry wolf."""
        stream_udp = {**STREAM, "USE_TCP": "no", "USE_UDP": "yes", "LISTEN_STREAM_PORT": "8080"}
        assert check_ports({"a": {**HTTP, "HTTPS_PORT": ""}, "b": stream_udp}) == []

    def test_a_reserved_product_port_is_fatal(self):
        reserved = reserved_ports({"API_HTTP_PORT": "5000", "API_HTTPS_PORT": "5443"})
        issues = check_ports({"a": {**HTTP, "HTTP_PORT": "5000", "HTTPS_PORT": ""}}, reserved=reserved)
        assert levels(issues) == [FATAL]
        assert "reserved for the internal API (HTTP)" in issues[0].message

    def test_the_healthcheck_port_is_reserved(self):
        issues = check_ports({"a": {**HTTP, "HTTP_PORT": str(HEALTHCHECK_PORT), "HTTPS_PORT": ""}}, reserved=reserved_ports({}))
        assert levels(issues) == [FATAL]

    def test_moving_the_api_frees_its_default_port_and_reserves_the_new_one(self):
        """The API ports are settings, not constants: reading them from the configuration is the
        difference between a rule and a hardcoded annoyance."""
        reserved = reserved_ports({"API_HTTP_PORT": "5001", "API_HTTPS_PORT": "5443"})
        assert check_ports({"a": {**HTTP, "HTTP_PORT": "5000", "HTTPS_PORT": ""}}, reserved=reserved) == []
        assert levels(check_ports({"a": {**HTTP, "HTTP_PORT": "5001", "HTTPS_PORT": ""}}, reserved=reserved)) == [FATAL]

    def test_all_in_one_reserves_the_ui_and_api_service_ports(self):
        assert 7000 not in reserved_ports({})
        assert reserved_ports({}, all_in_one=True)[7000] == "the all-in-one web UI"
        assert reserved_ports({}, all_in_one=True)[8888] == "the all-in-one API service"

    def test_privileged_port_warns_in_a_container_only(self):
        """Linux runs NGINX as root then drops (start.sh:132-133) so 80 is fine there; the images
        run as ``nginx`` (src/bw/Dockerfile:138) and cannot bind it."""
        service = {"a": {**HTTP, "HTTP_PORT": "80", "HTTPS_PORT": ""}}
        assert check_ports(service, containerized=False) == []
        issues = check_ports(service, containerized=True)
        assert levels(issues) == [WARNING]
        assert f"below {PRIVILEGED_PORT_CEILING}" in issues[0].message

    def test_mixing_tls_and_plain_on_one_port_warns(self):
        """NGINX unions listen options instead of failing (ngx_http.c:1320-1352), so the plain
        service silently starts speaking TLS. Silent is exactly why it is worth a line."""
        services = {"a": {**HTTP, "HTTP_PORT": "8443", "HTTPS_PORT": ""}, "b": {**HTTP, "HTTP_PORT": "", "HTTPS_PORT": "8443"}}
        issues = check_ports(services)
        assert WARNING in levels(issues)
        assert any("both with and without TLS" in issue.message for issue in issues)

    def test_divergent_http2_on_a_shared_port_warns(self):
        services = {"a": {**HTTP, "HTTPS_PORT": "", "HTTP2": "yes"}, "b": {**HTTP, "HTTPS_PORT": "", "HTTP2": "no"}}
        issues = check_ports(services)
        assert any("different HTTP2 settings" in issue.message for issue in issues)

    def test_fatal_issues_are_reported_before_warnings(self):
        services = {"a": {**HTTP, "HTTP_PORT": "80", "HTTPS_PORT": ""}, "b": {**STREAM, "LISTEN_STREAM_PORT": "80"}}
        assert levels(check_ports(services, containerized=True))[0] == FATAL


class TestServicesFromConfig:
    def test_multisite_splits_and_keeps_globals_as_the_default(self):
        config = {
            "MULTISITE": "yes",
            "SERVER_NAME": "a.example.com b.example.com",
            "HTTP_PORT": "8080",
            "a.example.com_HTTP_PORT": "9000",
        }
        services = services_from_config(config)
        assert services["a.example.com"]["HTTP_PORT"] == "9000"
        assert services["b.example.com"]["HTTP_PORT"] == "8080"

    def test_a_service_name_that_prefixes_another_does_not_steal_its_keys(self):
        config = {"MULTISITE": "yes", "SERVER_NAME": "app app_2", "app_2_HTTP_PORT": "9002", "app_HTTP_PORT": "9001"}
        services = services_from_config(config)
        assert services["app_2"]["HTTP_PORT"] == "9002"
        assert services["app"]["HTTP_PORT"] == "9001"

    def test_a_declaring_service_does_not_keep_the_inherited_repetitions(self):
        """Same replacement the renderer applies, so the write-path refusals and the conflict
        report see the ports the service will really listen on."""
        config = {"MULTISITE": "yes", "SERVER_NAME": "a b", "HTTP_PORT": "8080", "HTTP_PORT_1": "8081", "a_HTTP_PORT": "9000"}
        services = services_from_config(config)
        assert collect_ports(services["a"], "HTTP_PORT") == ["9000"]
        assert collect_ports(services["b"], "HTTP_PORT") == ["8080", "8081"]

    def test_the_multisite_override_wins_over_the_configuration(self):
        """The write paths need it: a snapshot they are about to persist already carries prefixed
        keys, and reading MULTISITE out of it would make the answer depend on a setting the very
        same request may be changing."""
        config = {"MULTISITE": "no", "SERVER_NAME": "a b", "a_HTTP_PORT": "9000"}
        services = services_from_config(config, ["a", "b"], multisite=True)
        assert list(services) == ["a", "b"]
        assert services["a"]["HTTP_PORT"] == "9000"

    def test_non_multisite_yields_the_single_service(self):
        services = services_from_config({"MULTISITE": "no", "SERVER_NAME": "a.example.com", "HTTP_PORT": "8080"})
        assert list(services) == ["a.example.com"]
        assert services["a.example.com"]["HTTP_PORT"] == "8080"


class TestPortListKeys:
    @pytest.mark.parametrize(
        "key,expected",
        [
            ("HTTP_PORT", "HTTP_PORT"),
            ("HTTP_PORT_1", "HTTP_PORT"),
            ("HTTP_PORT_12", "HTTP_PORT"),
            ("HTTPS_PORT", "HTTPS_PORT"),
            ("HTTPS_PORT_3", "HTTPS_PORT"),
            # Not members: a stream port (deliberately still unioned), a lookalike, and the
            # control plane's own ports -- which carry the setting name as a SUFFIX.
            ("LISTEN_STREAM_PORT", None),
            ("HTTP_PORTX", None),
            ("HTTP_PORT_X", None),
            ("API_HTTP_PORT", None),
        ],
    )
    def test_membership(self, key, expected):
        assert port_list_setting(key) == expected

    def test_keys_come_back_in_insertion_order(self):
        config = {"HTTP_PORT_1": "8081", "HTTP_PORT": "8080", "HTTPS_PORT": "8443"}
        assert port_list_keys(config, "HTTP_PORT") == ["HTTP_PORT_1", "HTTP_PORT"]


class TestDropInheritedPorts:
    """§2.2. ``multiple`` settings merge as a union and ``dict.update`` cannot remove a key, so
    "this service listens on 9000" would otherwise still mean "and on the inherited 8081"."""

    GLOBAL = {"HTTP_PORT": "8080", "HTTP_PORT_1": "8081", "HTTPS_PORT": "8443", "OTHER": "keep"}

    def test_a_declared_base_port_removes_the_inherited_repetitions(self):
        merged = dict(self.GLOBAL, HTTP_PORT="9000")
        drop_inherited_ports(merged, {"HTTP_PORT": "9000"})
        assert collect_ports(merged, "HTTP_PORT") == ["9000"]

    def test_a_declared_repetition_alone_removes_the_inherited_base(self):
        """Replacement is about the LIST, not about the base key."""
        merged = dict(self.GLOBAL, HTTP_PORT_1="9001")
        drop_inherited_ports(merged, {"HTTP_PORT_1": "9001"})
        assert collect_ports(merged, "HTTP_PORT") == ["9001"]

    def test_declaring_nothing_leaves_the_configuration_untouched(self):
        """The half that makes the flip invisible to every existing deployment."""
        merged = dict(self.GLOBAL)
        drop_inherited_ports(merged, {"SERVER_TYPE": "http"})
        assert merged == self.GLOBAL

    def test_the_two_settings_do_not_leak_into_each_other(self):
        merged = dict(self.GLOBAL, HTTP_PORT="9000")
        drop_inherited_ports(merged, {"HTTP_PORT": "9000"})
        assert merged["HTTPS_PORT"] == "8443"
        assert merged["OTHER"] == "keep"

    def test_an_explicitly_empty_declaration_still_replaces(self):
        """``HTTP_PORT=""`` is the documented "no listener" value (settings.json:23). It has to
        beat the inherited list, or disabling a service's HTTP listener would be impossible."""
        merged = dict(self.GLOBAL, HTTP_PORT="")
        drop_inherited_ports(merged, {"HTTP_PORT": ""})
        assert collect_ports(merged, "HTTP_PORT") == []


class TestListMoved:
    """Lot C's discriminator. Equal list means the published-port contract still holds --
    ``misc/integrations/docker.yml:16-18`` publishes ``80:8080``, so the RENDERED port is not the
    reachable one and no absolute URL may carry it. A different list means the operator moved this
    service off the published port, and the rendered port is then the only one that reaches it.

    The Python side answers this question for ``http01_refusals``; the port an absolute URL
    actually carries is decided in Lua (``utils.listen_port_override``), which reads
    ``variables.env`` at request time.
    """

    GLOBAL = {"HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}

    def test_the_same_list_is_not_a_move(self):
        assert list_moved(dict(self.GLOBAL), self.GLOBAL, "HTTP_PORT") is False

    def test_a_different_value_is_a_move(self):
        assert list_moved({"HTTP_PORT": "9000"}, self.GLOBAL, "HTTP_PORT") is True

    def test_the_same_ports_in_a_different_order_are_a_move(self):
        """Order decides which port an absolute URL gets, so it is part of the identity. Sorting is
        by SUFFIX, never by value, which is what keeps this a move: the two ports are assigned to
        different repetitions."""
        service = {"HTTP_PORT": "8081", "HTTP_PORT_1": "8080"}
        assert list_moved(service, self.GLOBAL, "HTTP_PORT") is True

    def test_a_restated_list_is_not_a_move_whatever_order_the_keys_arrive_in(self):
        """The shape that reached the HTTP-01 gate: a fleet carrying a row for ``HTTP_PORT_1``
        alone, and a service restating ``8080 8081``. Both sides of this comparison are built by
        merging dicts, so both had their base appended last — the refusal it caused was a
        dict-ordering artefact, not a moved service."""
        merged_backwards = {"HTTP_PORT_1": "8081", "HTTP_PORT": "8080"}
        assert list_moved(merged_backwards, self.GLOBAL, "HTTP_PORT") is False
        assert list_moved(dict(self.GLOBAL), merged_backwards, "HTTP_PORT") is False

    def test_a_service_that_disabled_its_listener_moved_the_list(self):
        """``HTTP_PORT=""`` is an empty list, which is not the fleet's list."""
        assert list_moved({"HTTP_PORT": ""}, self.GLOBAL, "HTTP_PORT") is True


class TestHttp01Refusals:
    """An ACME server only ever contacts public port 80 and follows no redirect to get there. A
    service that listens somewhere else can never pass an http-01 challenge, so the save is refused
    with the two ways out rather than issuing a certificate request that will fail later."""

    GLOBAL = {"HTTP_PORT": "8080", "AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http"}

    def refusal(self, **service):
        services = {"b": dict(self.GLOBAL, **service)}
        return http01_refusals(services, self.GLOBAL).get("b")

    def test_a_moved_service_is_refused(self):
        message = self.refusal(HTTP_PORT="9080")
        assert message and "9080" in message and "8080" in message

    def test_the_message_names_both_ways_out(self):
        message = self.refusal(HTTP_PORT="9080")
        assert "LETS_ENCRYPT_CHALLENGE=dns" in message
        assert "HTTP_PORT" in message

    def test_the_global_clause_is_dropped_when_the_snapshot_has_no_global_row(self):
        """A write path hands over the NON-default settings, so a global port left at its default
        is simply absent. Printing "(none)" there says the fleet has no HTTP port, which is false
        and points the operator at the wrong thing."""
        message = http01_refusals({"b": {"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http", "HTTP_PORT": "9080"}}, {})["b"]
        assert "(none)" not in message
        assert "instead of the global one, and" in message

    def test_a_plural_global_list_is_named_in_full(self):
        message = http01_refusals({"b": dict(self.GLOBAL, HTTP_PORT="9080")}, dict(self.GLOBAL, HTTP_PORT_1="8081"))["b"]
        assert "global ones (8080, 8081)" in message

    def test_a_service_on_the_global_ports_is_not_refused(self):
        assert self.refusal() is None

    def test_the_dns_challenge_is_never_refused(self):
        assert self.refusal(HTTP_PORT="9080", LETS_ENCRYPT_CHALLENGE="dns") is None

    def test_lets_encrypt_off_is_never_refused(self):
        assert self.refusal(HTTP_PORT="9080", AUTO_LETS_ENCRYPT="no") is None

    def test_passthrough_is_never_refused(self):
        """The challenge is answered upstream, so this instance's ports do not decide it."""
        assert self.refusal(HTTP_PORT="9080", LETS_ENCRYPT_PASSTHROUGH="yes") is None


class TestSettingsDeclaration:
    """The regex is the first gate an operator meets; it used to accept ``999999``."""

    @pytest.fixture(scope="class")
    def settings(self):
        return json.loads((_REPO_ROOT / "src" / "common" / "settings.json").read_text())

    @pytest.mark.parametrize("setting", ["HTTP_PORT", "HTTPS_PORT", "LISTEN_STREAM_PORT", "LISTEN_STREAM_PORT_SSL"])
    @pytest.mark.parametrize(
        "value,accepted", [("", True), ("80", True), ("8080", True), ("65535", True), ("65536", False), ("999999", False), ("http", False)]
    )
    def test_every_data_plane_port_setting_is_range_checked(self, settings, setting, value, accepted):
        import re

        assert bool(re.search(settings[setting]["regex"], value)) is accepted, (setting, value)
