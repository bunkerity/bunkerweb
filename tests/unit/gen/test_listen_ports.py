"""Rendered listen directives supported by dev."""

import re
from pathlib import Path

import pytest

from _listen_helpers import included_blocks, listen_lines, socket_of  # type: ignore

_HOST_PORT_RX = re.compile(r"^(?:\[[0-9a-fA-F:]*\]|[0-9.]*):\d+$")


@pytest.fixture(scope="module")
def render(render_tree):
    return render_tree


@pytest.fixture(scope="module", autouse=True)
def default_server_certificate():
    """Exercise HTTPS listeners without requiring a root-owned certificate cache."""
    import os.path

    isfile = os.path.isfile
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os.path, "isfile", lambda path: path == "/var/cache/bunkerweb/misc/default-server-cert.pem" or isfile(path))
        yield


def sockets_with_reuseport(tree, name="server-stream.conf"):
    return [(path, line.split()[1].rstrip(";")) for path, line in listen_lines(tree, name) if "reuseport" in line]


@pytest.mark.parametrize(
    "overrides",
    [
        {"a.example.com_SERVER_TYPE": "http"},
        {"a.example.com_LISTEN_STREAM": "no"},
    ],
)
def test_an_unloaded_or_disabled_stream_block_cannot_claim_reuseport(render, overrides):
    tree = render(**(STREAM | overrides))
    assert [(path, addr) for path, addr in sockets_with_reuseport(tree) if path.startswith("b.example.com/")] == [
        ("b.example.com/server-stream.conf", "0.0.0.0:1337")
    ]


STREAM = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com", "a.example.com_SERVER_TYPE": "stream", "b.example.com_SERVER_TYPE": "stream"}


class TestStreamReuseportIsEmittedOncePerSocket:
    def test_a_single_stream_service_still_carries_reuseport(self, render):
        tree = render(MULTISITE="no", SERVER_NAME="a.example.com", SERVER_TYPE="stream")
        assert [line for _, line in listen_lines(tree, "server-stream.conf")] == ["listen 0.0.0.0:1337 reuseport;"]

    def test_two_services_two_ports_both_keep_the_option(self, render):
        tree = render(**STREAM, **{"b.example.com_LISTEN_STREAM_PORT": "1338"})
        assert sorted(addr for _, addr in sockets_with_reuseport(tree)) == ["0.0.0.0:1337", "0.0.0.0:1338"]

    def test_tcp_and_udp_on_one_port_are_two_sockets_and_keep_both(self, render):
        tree = render(**STREAM, **{"a.example.com_USE_UDP": "no", "b.example.com_USE_TCP": "no", "b.example.com_USE_UDP": "yes"})
        listens = sorted(line for _, line in listen_lines(tree, "server-stream.conf"))
        assert listens == ["listen 0.0.0.0:1337 reuseport;", "listen 0.0.0.0:1337 udp reuseport;"]

    def test_a_shared_ssl_stream_port_carries_no_reuseport_at_all(self, render):
        tree = render(
            **STREAM,
            **{"a.example.com_LISTEN_STREAM_PORT": "", "b.example.com_LISTEN_STREAM_PORT": ""},
        )
        assert sockets_with_reuseport(tree) == []
        assert [line for _, line in listen_lines(tree, "ssl-certificate-stream-lua.conf")] == ["listen 0.0.0.0:4242 ssl;"] * 2

    def test_two_default_stream_services_share_1337_with_one_reuseport(self, render):
        """PO-QUEUE 30. Nothing is overridden: 1337 is the default of a multisite setting, so this
        configuration is reachable on a fresh install. Before the fix both blocks carried the
        option and NGINX refused to start."""
        tree = render(**STREAM)
        assert sorted(line for _, line in listen_lines(tree, "server-stream.conf")) == ["listen 0.0.0.0:1337 reuseport;", "listen 0.0.0.0:1337;"]
        assert len(sockets_with_reuseport(tree)) == 1

    def test_ipv6_and_ipv4_of_one_owner_both_carry_it(self, render):
        """Different families are different sockets; the owning block emits both of its lines."""
        tree = render(**STREAM, USE_IPV6="yes")
        assert sorted(addr for _, addr in sockets_with_reuseport(tree)) == ["0.0.0.0:1337", "[::]:1337"]

    def test_the_derived_variable_reaches_every_server_render(self, tmp_path, monkeypatch):
        """Guards the wiring itself. The template falls back to "owns nothing" when the variable is
        missing, which is the safe failure (NGINX still starts) but silently drops the option on
        every deployment -- so the wiring needs its own assertion."""
        import Templator as T  # type: ignore

        monkeypatch.setattr(T, "sep", str(tmp_path))
        config = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com"}
        templator = T.Templator(
            str(Path(__file__).resolve().parents[3] / "src" / "common" / "confs"),
            str(Path(__file__).resolve().parents[3] / "src" / "common" / "core"),
            str(tmp_path / "plugins"),
            str(tmp_path / "pro-plugins"),
            str(tmp_path / "out"),
            "/etc/nginx",
            config,
            {},
            dict(config),
        )
        assert set(templator._stream_reuseport_ports) == {"a.example.com", "b.example.com"}


class TestOneDefaultServerPerSocket:
    def test_a_mono_site_service_still_owns_default_server_when_not_loading(self, render):
        tree = render(MULTISITE="no", SERVER_NAME="a.example.com")
        included = included_blocks(tree)
        assert "server.conf" in included and "default-server-http.conf" not in included, included
        assert any("default_server" in line for _, line in listen_lines(tree, "server.conf"))

    def test_a_mono_site_loading_render_does_not_declare_the_flag_twice(self, render):
        """``server.conf:29`` claimed ``default_server`` on ``MULTISITE=no`` +
        ``DISABLE_DEFAULT_SERVER=no`` alone, but ``http.conf:91-93`` also includes the default
        server when ``IS_LOADING=yes``, so both blocks claimed ``0.0.0.0:8080``. The QUIC guard at
        ``ssl-certificate-lua.conf:57`` already carried all three terms; this one did not.

        The boot path never reached it -- the entrypoint renders its loading config with an empty
        SERVER_NAME (``src/bw/entrypoint.sh:69``), so no server block is included -- but
        ``IS_LOADING`` is a declared setting (``settings.json:2``) and anything else that sets it
        lands here."""
        tree = render(MULTISITE="no", SERVER_NAME="a.example.com", IS_LOADING="yes")
        included = included_blocks(tree)
        assert "default-server-http.conf" in included and "server.conf" in included, included
        claims = {}
        for path in included:
            for _, line in listen_lines({path: tree[path]}):
                if "default_server" in line:
                    claims.setdefault(socket_of(line), []).append(path)
        assert {socket: paths for socket, paths in claims.items() if len(paths) > 1} == {}, claims


class TestEmptyPortRendersNoListen:
    def test_every_rendered_listen_has_a_real_port(self, render):
        tree = render(**STREAM)
        for path, line in listen_lines(tree):
            addr = line.split()[1].rstrip(";")
            assert addr.startswith("unix:") or _HOST_PORT_RX.match(addr), (path, line)

    @pytest.mark.parametrize("disabled", ["HTTP_PORT", "HTTPS_PORT"])
    def test_disabling_a_port_removes_the_default_server_listen_instead_of_emptying_it(self, render, disabled):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", **{disabled: ""})
        default_server = tree["default-server-http.conf"]
        assert "listen 0.0.0.0:;" not in default_server
        for line in default_server.splitlines():
            if line.strip().startswith("listen "):
                assert _HOST_PORT_RX.match(line.split()[1].rstrip(";")), line
        kept = "8443" if disabled == "HTTP_PORT" else "8080"
        assert f"listen 0.0.0.0:{kept}" in default_server, "disabling one protocol must not disable the other"

    def test_an_ordinary_deployment_still_includes_it(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com")
        assert "default-server-http.conf" in included_blocks(tree)

    def test_the_quic_loop_is_guarded_too(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", HTTPS_PORT="")
        assert "quic" not in tree["default-server-http.conf"]

    def test_disabling_both_ports_drops_the_default_server_instead_of_leaving_it_portless(self, render):
        """A ``server{}`` with no ``listen`` is not inert: NGINX gives it an implicit ``*:80``. So
        the configuration that asks for no HTTP listener at all was the one that silently took
        port 80 -- on the host, in a Linux install. The block is not included at all now."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", HTTP_PORT="", HTTPS_PORT="")
        assert [line for line in tree["default-server-http.conf"].splitlines() if line.strip().startswith("listen ")] == []
        assert "default-server-http.conf" not in included_blocks(tree)

    def test_a_stream_only_deployment_does_not_include_the_default_server_either(self, render):
        """Same silent ``*:80``, reached the other way: a stream service renders no http block, so
        the union is empty even though nobody wrote ``HTTP_PORT=""``."""
        tree = render(**STREAM, HTTP_PORT="", HTTPS_PORT="")
        assert "default-server-http.conf" not in included_blocks(tree)
