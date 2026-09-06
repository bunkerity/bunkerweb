"""The stream default server: a reserved-service port list, refused on any port a service owns.

PO ruling 6, gate approved 2026-09-02. The default server used to exist only in ``http``: stream
ports are multisite-only and there is no SNI on plain TCP (none at all on UDP), so NGINX picks a
stream block by ``address:port`` alone. That is exactly why a ``default_server`` cannot simply be
added on the service ports -- it would WIN there and answer, then close, the service's traffic.

It therefore listens only on ports the reserved ``default-server`` pseudo-service declares for
itself, and only on those no service claims. That second half is judged TWICE, and both are here:
in the API when the list is saved (``tests/unit/api/test_services_reserved.py``) and again at
generation time, because a service can declare the port afterwards -- there the reserved block is
dropped and the service keeps its port.
"""

import json
from pathlib import Path

import pytest

from default_server import DEFAULT_SERVER_ID, blocked_stream_ports, default_server_stream_listeners  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
MISC_PLUGIN = ROOT / "src" / "common" / "core" / "misc" / "plugin.json"
SETTING = "DEFAULT_SERVER_STREAM_PORTS"
SSL_SETTING = "DEFAULT_SERVER_STREAM_PORTS_SSL"

SERVICE = "app.example.com"


def _stream(tree):
    return tree["stream.conf"]


def _blocks(text):
    """The ``server { … }`` blocks of a rendered stream.conf, brace-matched."""
    blocks = []
    index = 0
    while True:
        start = text.find("server {", index)
        if start < 0:
            return blocks
        depth = 0
        for position in range(start, len(text)):
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : position + 1])  # noqa: E203
                    index = position
                    break
        else:
            raise AssertionError("unbalanced braces in stream.conf")


def _render(render_tree, **overrides):
    variables = {
        "MULTISITE": "yes",
        "SERVER_NAME": f"{SERVICE} {DEFAULT_SERVER_ID}",
        f"{SERVICE}_SERVER_TYPE": "stream",
        f"{SERVICE}_LISTEN_STREAM_PORT": "9000",
        f"{SERVICE}_LISTEN_STREAM_PORT_SSL": "9443",
    }
    variables.update(overrides)
    return _stream(render_tree(**variables))


class TestTheSettingItself:
    def test_it_is_declared_and_empty_by_default(self):
        """Empty is the shipped default: no deployment gains a listener it did not ask for."""
        setting = json.loads(MISC_PLUGIN.read_text())["settings"][SETTING]
        assert setting["context"] == "multisite"
        assert setting["default"] == ""
        assert setting["multiple"]

    def test_the_ssl_list_is_declared_the_same_way(self):
        """Same shape as the port list, its own `multiple` id so the UI renders a second repeatable
        field, and empty by default -- plain TCP unless the operator says otherwise."""
        settings = json.loads(MISC_PLUGIN.read_text())["settings"]
        ssl_setting = settings[SSL_SETTING]
        assert ssl_setting["context"] == "multisite"
        assert ssl_setting["default"] == ""
        assert ssl_setting["regex"] == settings[SETTING]["regex"]
        assert ssl_setting["multiple"] == "default-server-stream-ports-ssl" != settings[SETTING]["multiple"]

    def test_the_regex_accepts_a_port_and_the_empty_value(self):
        from regex import compile as re_compile

        pattern = re_compile(json.loads(MISC_PLUGIN.read_text())["settings"][SETTING]["regex"])
        assert pattern.match("9999")
        assert pattern.match("")
        assert not pattern.match("70000")
        assert not pattern.match("nope")


class TestTheElection:
    """The pure half. ``default_server_stream_listeners`` is what both the API refusal and the
    renderer consult, so a rule proven here is proven for both."""

    def test_a_port_a_stream_service_declares_is_refused_and_named(self):
        ports, _, refused, _ = default_server_stream_listeners(
            {
                DEFAULT_SERVER_ID: {SETTING: "9000", f"{SETTING}_1": "9999"},
                SERVICE: {"SERVER_TYPE": "stream", "LISTEN_STREAM_PORT": "9000"},
            }
        )
        assert ports == ["9999"]
        assert refused == {"9000": SERVICE}

    def test_the_services_ssl_stream_port_counts_as_declared(self):
        _, _, refused, _ = default_server_stream_listeners(
            {
                DEFAULT_SERVER_ID: {SETTING: "9443"},
                SERVICE: {"SERVER_TYPE": "stream", "LISTEN_STREAM_PORT_SSL": "9443"},
            }
        )
        assert refused == {"9443": SERVICE}

    @pytest.mark.parametrize(
        "service_config",
        [{"SERVER_TYPE": "http", "LISTEN_STREAM_PORT": "9000"}, {"SERVER_TYPE": "stream", "LISTEN_STREAM": "no", "LISTEN_STREAM_PORT": "9000"}],
    )
    def test_a_service_whose_block_nginx_never_loads_claims_nothing(self, service_config):
        """`stream.conf` includes a service's `server-stream.conf` only when SERVER_TYPE is stream,
        and `server-stream.conf` renders no listen line at all when LISTEN_STREAM is off. Refusing
        on those would be a refusal the operator cannot act on."""
        ports, _, refused, _ = default_server_stream_listeners({DEFAULT_SERVER_ID: {SETTING: "9000"}, SERVICE: service_config})
        assert ports == ["9000"]
        assert refused == {}

    def test_the_ssl_subset_comes_from_the_reserved_services_own_setting(self):
        ports, ssl_ports, _, orphans = default_server_stream_listeners({DEFAULT_SERVER_ID: {SETTING: "9998", f"{SETTING}_1": "9999", SSL_SETTING: "9999"}})
        assert ports == ["9998", "9999"]
        assert ssl_ports == ["9999"]
        assert orphans == []

    def test_the_services_own_listen_stream_port_ssl_is_no_longer_the_switch(self):
        """The overload this setting replaces. `LISTEN_STREAM_PORT_SSL` belongs to a stream SERVICE,
        defaults to `4242` in the `general` pseudo-plugin and is inherited by every service row, so
        the reserved row carried a value nobody typed and no page offered a field for."""
        _, ssl_ports, _, _ = default_server_stream_listeners({DEFAULT_SERVER_ID: {SETTING: "9999", "LISTEN_STREAM_PORT_SSL": "9999"}})
        assert ssl_ports == []

    def test_an_ssl_port_the_port_list_does_not_carry_is_an_orphan(self):
        """The subset rule, at generation time. There is no listener on 7777 to switch to TLS, so
        the renderer cannot honour it -- it drops it and Templator logs why, rather than leaving an
        operator convinced a port is encrypted."""
        ports, ssl_ports, _, orphans = default_server_stream_listeners({DEFAULT_SERVER_ID: {SETTING: "9999", SSL_SETTING: "7777"}})
        assert ports == ["9999"]
        assert ssl_ports == []
        assert orphans == ["7777"]

    def test_a_refused_port_is_not_reported_as_an_ssl_orphan(self):
        """It IS in the port list; it lost the election. Reporting it twice, with two different
        reasons, is how an operator stops reading the log."""
        _, ssl_ports, refused, orphans = default_server_stream_listeners(
            {
                DEFAULT_SERVER_ID: {SETTING: "9000", SSL_SETTING: "9000"},
                SERVICE: {"SERVER_TYPE": "stream", "LISTEN_STREAM_PORT": "9000"},
            }
        )
        assert refused == {"9000": SERVICE}
        assert ssl_ports == []
        assert orphans == []

    def test_no_reserved_row_means_no_listeners(self):
        assert default_server_stream_listeners({SERVICE: {"SERVER_TYPE": "stream"}}) == ([], [], {}, [])

    def test_the_all_in_one_ports_are_refused_when_the_image_is_all_in_one(self):
        """7000 (the AIO web UI) and 8888 (the AIO API service) are held by supervisord in the SAME
        network namespace as NGINX on that image, so a stream `default_server` there is the same
        "NGINX will not start" class as an HTTP port. `check_ports` already treats them as
        un-takeable for ordinary services; without `all_in_one` this helper did not."""
        config = {"HTTP_PORT": "8080", "HTTPS_PORT": "8443"}
        assert set(blocked_stream_ports(config, {}, all_in_one=True)) >= {"7000", "8888"}
        assert "7000" not in blocked_stream_ports(config, {}, all_in_one=False)

        ports, _, refused, _ = default_server_stream_listeners({DEFAULT_SERVER_ID: {SETTING: "7000"}}, blocked_stream_ports(config, {}, all_in_one=True))
        assert ports == []
        assert refused == {"7000": "the all-in-one web UI"}

    def test_the_http_ports_and_the_product_ports_are_refused(self):
        """The collision that is FATAL rather than merely wrong. `http{}` and `stream{}` open their
        own sockets, so a stream `default_server` on an http port makes NGINX refuse to start
        (`utils/ports.py:24-32`) -- and `DEFAULT_SERVER_STREAM_PORTS=8080` is the shipped
        `HTTP_PORT` default, i.e. the single most likely number an operator types. `check_ports`
        never sees these ports, so nothing else in the product catches it."""
        blocked = blocked_stream_ports({"HTTP_PORT": "8080", "HTTPS_PORT": "8443", "API_HTTP_PORT": "5000"}, {SERVICE: {}})
        assert set(blocked) >= {"8080", "8443", "5000", "6000"}, blocked

        ports, _, refused, _ = default_server_stream_listeners(
            {DEFAULT_SERVER_ID: {SETTING: "8080"}, SERVICE: {}},
            blocked,
        )
        assert ports == []
        assert refused == {"8080": "an HTTP listener"}


class TestWhatAGlobalWriteDoes:
    """The gate said the setting would "only ever exist as `default-server_DEFAULT_SERVER_STREAM_PORTS*`".
    It does not, and this class is here so nobody has to rediscover that from a running instance.

    Both config producers materialise an inherited copy of every multisite setting under every
    service name -- `gen/Configurator.py:387` and `db_methods/config_read.py:219`, with only
    `port_list_setting()` members exempt -- so by the time `Templator` splits the config there is no
    difference between "the reserved service's own key" and "the global value it inherited". A
    global `DEFAULT_SERVER_STREAM_PORTS` therefore DOES open listeners. Rendered here rather than
    argued, and rendered through the real tree rather than through a hand-built argument, because
    that is the only shape either producer emits.
    """

    def test_a_global_write_opens_the_listener(self, render_tree):
        rendered = _render(render_tree, **{SETTING: "9999"})
        assert "listen 0.0.0.0:9999 default_server;" in rendered

    def test_and_it_is_still_refused_on_a_port_a_service_holds(self, render_tree):
        """The refusals do not care where the value came from, which is what keeps the inheritance
        from being dangerous as well as surprising."""
        rendered = _render(render_tree, **{SETTING: "9000"})
        assert "default_server" not in rendered


class TestTheRender:
    def test_nothing_is_rendered_when_the_list_is_empty(self, render_tree):
        """The shipped default. A `default_server` appearing here without an opt-in would take over
        every stream port in the deployment."""
        assert "default_server" not in _render(render_tree)

    def test_a_declared_port_renders_one_answer_and_close_block(self, render_tree):
        rendered = _render(render_tree, **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9999"})
        blocks = [block for block in _blocks(rendered) if "default_server" in block]
        assert len(blocks) == 1
        assert "listen 0.0.0.0:9999 default_server;" in blocks[0]
        # It answers and closes. `return ""` is the content handler: a stream server with none at
        # all is a runtime error, not a closed connection.
        assert 'return "";' in blocks[0]
        assert "proxy_pass" not in blocks[0]

    def test_a_port_a_stream_service_listens_on_is_dropped_at_generation_time(self, render_tree):
        """The half the API cannot cover: the service can declare the port AFTER the list was
        saved. Fails safe towards the real service -- the reserved block goes, the service stays."""
        rendered = _render(render_tree, **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9000", f"{DEFAULT_SERVER_ID}_{SETTING}_1": "9999"})
        listens = [line.strip() for line in rendered.splitlines() if "default_server" in line]
        assert listens == ["listen 0.0.0.0:9999 default_server;"]

    def test_an_ssl_port_presents_the_override_certificate(self, render_tree):
        rendered = _render(
            render_tree,
            **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9999", f"{DEFAULT_SERVER_ID}_{SSL_SETTING}": "9999"},
        )
        block = next(block for block in _blocks(rendered) if "default_server" in block)
        assert "listen 0.0.0.0:9999 ssl default_server;" in block
        # DS-A's override phase, and ONLY it: the shared `ssl_certificate` loop resolves a
        # certificate for a hostname a service owns, which this block never answers for.
        assert 'call_plugin(plugin_obj, "ssl_certificate_default")' in block
        assert 'call_plugin(plugin_obj, "ssl_certificate")' not in block
        # `ngx.shared` is built per subsystem -- the http dict does not exist here.
        assert "ngx.shared.internalstore_stream" in block
        assert "ngx.shared.internalstore," not in block

    def test_a_plain_port_gets_no_tls_at_all(self, render_tree):
        block = next(block for block in _blocks(_render(render_tree, **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9999"})) if "default_server" in block)
        assert " ssl " not in block
        assert "ssl_certificate_by_lua_block" not in block

    def test_an_ssl_port_the_port_list_does_not_carry_renders_nothing(self, render_tree):
        """The subset rule through the real tree: 7777 is not a listener, so it does not become one
        by being named TLS, and 9999 does not silently inherit the flag either."""
        rendered = _render(render_tree, **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9999", f"{DEFAULT_SERVER_ID}_{SSL_SETTING}": "7777"})
        listens = [line.strip() for line in rendered.splitlines() if "default_server" in line]
        assert listens == ["listen 0.0.0.0:9999 default_server;"]

    def test_the_tls_parameters_come_from_the_reserved_service_not_the_globals(self, render_tree):
        """`stream.conf` is a GLOBAL template, so without the derived `DEFAULT_SERVER_TLS_RENDER`
        this block prints the global SSL_* while `default-server-http.conf` prints the reserved
        service's -- one field, one page, two answers, and the operator who hardened the catch-all's
        TLS gets it on the HTTP half only."""
        tree = render_tree(
            **{
                "SERVER_NAME": f"{DEFAULT_SERVER_ID} {SERVICE}",
                "MULTISITE": "yes",
                f"{SERVICE}_SERVER_TYPE": "stream",
                f"{SERVICE}_LISTEN_STREAM_PORT": "9000",
                f"{DEFAULT_SERVER_ID}_{SETTING}": "9999",
                f"{DEFAULT_SERVER_ID}_{SSL_SETTING}": "9999",
                f"{DEFAULT_SERVER_ID}_SSL_PROTOCOLS": "TLSv1.3",
            }
        )
        block = next(block for block in _blocks(_stream(tree)) if "default_server" in block)
        assert "ssl_protocols TLSv1.3;" in block
        # The TLSv1.3-only consequences, so the assertion cannot pass on the string alone.
        assert "ssl_prefer_server_ciphers off;" in block
        assert "ssl_dhparam" not in block
        # And the HTTP half agrees, which is the whole point.
        assert "ssl_protocols TLSv1.3;" in tree["default-server-http.conf"]

    def test_ipv6_adds_the_second_listener(self, render_tree):
        block = next(
            block for block in _blocks(_render(render_tree, USE_IPV6="yes", **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9999"})) if "default_server" in block
        )
        assert "listen [::]:9999 default_server;" in block

    def test_it_renders_with_no_stream_SERVICE_at_all(self, render_tree):
        """Catching stray TCP on a port nothing serves is the point of the feature, so the whole
        stream section -- shared dicts, the LUA init block the certificate runner needs -- has to
        render on `DEFAULT_SERVER_STREAM_PORTS` alone. The gate it hangs off
        (`has_variable(all, "SERVER_TYPE", "stream")`) is false in this deployment."""
        rendered = _render(
            render_tree,
            **{f"{SERVICE}_SERVER_TYPE": "http", f"{DEFAULT_SERVER_ID}_{SETTING}": "9999"},
        )
        assert "listen 0.0.0.0:9999 default_server;" in rendered
        assert "lua_shared_dict internalstore_stream" in rendered
        assert "include /etc/nginx/init-stream-lua.conf;" in rendered

    def test_the_reserved_service_still_gets_no_stream_block_of_its_own(self, render_tree):
        """It renders INTO the default server, never beside it: a second block on the same
        addr:port is what the whole design avoids."""
        rendered = _render(render_tree, **{f"{DEFAULT_SERVER_ID}_{SETTING}": "9999"})
        assert f"include /etc/nginx/{DEFAULT_SERVER_ID}/server-stream.conf;" not in rendered
