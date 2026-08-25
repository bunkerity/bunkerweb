"""Rendered ``listen`` directives: the two live defects of the ports conception, end to end.

These render the REAL tree -- ``Configurator.get_config`` then ``Templator.render`` -- because
both defects live in the seam between them: a template only ever sees one server block, while
both rules are about the set of blocks sharing an ``addr:port``.

**Constat B / PO-QUEUE 30** -- ``server-stream/server-stream.conf:36`` emitted ``reuseport`` on
every block. ``reuseport`` sets ``lsopt.set`` (``ngx_stream_core_module.c:1192-1196``) and a
second block setting a listen option on one ``addr:port`` is fatal:
``NGX_LOG_EMERG "duplicate listen options for %V"`` then ``NGX_ERROR``
(``ngx_stream.c:489-497``). ``LISTEN_STREAM_PORT`` defaults to ``1337`` and is multisite, so two
stream services that override **nothing** were enough to stop NGINX from starting. There was
zero coverage of this: ``grep LISTEN_STREAM_PORT tests/`` was empty before this file.

**Constat C / PO-QUEUE 31** -- the three default-server loops iterated without the ``and port``
guard that ``server-http/server.conf:24`` has, so ``HTTP_PORT=""`` -- a documented way to disable
HTTP listening (``settings.json:23``) -- rendered ``listen 0.0.0.0: default_server;``, which NGINX
rejects (``"invalid port"``, ``ngx_inet.c:846``).

The fix keeps ``reuseport`` (PO decision 5) rather than dropping it: dropping it would change
connection distribution on every existing stream deployment. Exactly one block per ``addr:port``
emits it, so a single-service deployment renders byte for byte what it rendered before.
"""

import re
from pathlib import Path

import pytest

from _listen_helpers import included_blocks, listen_lines, socket_of  # type: ignore  (tests/unit/gen is on the path)

# `listen <addr>;` where addr is a host:port pair. A unix socket has no port and is skipped.
_HOST_PORT_RX = re.compile(r"^(?:\[[0-9a-fA-F:]*\]|[0-9.]*):\d+$")


@pytest.fixture(scope="module")
def render(render_tree):
    """Short alias for the shared harness (conftest.render_tree)."""
    return render_tree


def sockets_with_reuseport(tree, name="server-stream.conf"):
    """``[(file, addr)]`` for every rendered ``listen`` carrying ``reuseport``, in the stream
    service blocks by default. The internal API (``api.conf:17``) and the default server's QUIC
    listener legitimately carry it on their own sockets."""
    return [(path, line.split()[1].rstrip(";")) for path, line in listen_lines(tree, name) if "reuseport" in line]


STREAM = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com", "a.example.com_SERVER_TYPE": "stream", "b.example.com_SERVER_TYPE": "stream"}


class TestStreamReuseportIsEmittedOncePerSocket:
    def test_two_default_stream_services_share_1337_with_one_reuseport(self, render):
        """PO-QUEUE 30. Nothing is overridden: 1337 is the default of a multisite setting, so this
        configuration is reachable on a fresh install. Before the fix both blocks carried the
        option and NGINX refused to start."""
        tree = render(**STREAM)
        assert sorted(line for _, line in listen_lines(tree, "server-stream.conf")) == ["listen 0.0.0.0:1337 reuseport;", "listen 0.0.0.0:1337;"]
        assert len(sockets_with_reuseport(tree)) == 1

    def test_a_single_stream_service_still_carries_reuseport(self, render):
        """The byte-identity half of the fix: the option is KEPT, so a mono-service deployment --
        every existing one -- renders exactly what it rendered before."""
        tree = render(MULTISITE="no", SERVER_NAME="a.example.com", SERVER_TYPE="stream")
        assert [line for _, line in listen_lines(tree, "server-stream.conf")] == ["listen 0.0.0.0:1337 reuseport;"]

    def test_two_services_two_ports_both_keep_the_option(self, render):
        """Ownership is per socket, not per service: distinct ports must not lose anything."""
        tree = render(**STREAM, **{"b.example.com_LISTEN_STREAM_PORT": "1338"})
        assert sorted(addr for _, addr in sockets_with_reuseport(tree)) == ["0.0.0.0:1337", "0.0.0.0:1338"]

    def test_tcp_and_udp_on_one_port_are_two_sockets_and_keep_both(self, render):
        """``ngx_stream.c:414-416`` keys the port list on (port, type, family), so a UDP listener
        never collides with a TCP one -- suppressing its option would be a needless regression."""
        tree = render(**STREAM, **{"a.example.com_USE_UDP": "no", "b.example.com_USE_TCP": "no", "b.example.com_USE_UDP": "yes"})
        listens = sorted(line for _, line in listen_lines(tree, "server-stream.conf"))
        assert listens == ["listen 0.0.0.0:1337 reuseport;", "listen 0.0.0.0:1337 udp reuseport;"]

    def test_ipv6_and_ipv4_of_one_owner_both_carry_it(self, render):
        """Different families are different sockets; the owning block emits both of its lines."""
        tree = render(**STREAM, USE_IPV6="yes")
        assert sorted(addr for _, addr in sockets_with_reuseport(tree)) == ["0.0.0.0:1337", "[::]:1337"]

    def test_a_shared_ssl_stream_port_carries_no_reuseport_at_all(self, render):
        """``ssl-certificate-stream-lua.conf:40`` never emitted the option, which is why sharing
        LISTEN_STREAM_PORT_SSL already worked. Nothing here may start emitting it."""
        tree = render(
            **STREAM,
            **{"a.example.com_LISTEN_STREAM_PORT": "", "b.example.com_LISTEN_STREAM_PORT": ""},
        )
        assert sockets_with_reuseport(tree) == []
        assert [line for _, line in listen_lines(tree, "ssl-certificate-stream-lua.conf")] == ["listen 0.0.0.0:4242 ssl;"] * 2

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
    """``default_server`` is unique per ``addr:port`` and duplicating it is fatal --
    "a duplicate default server for %V" (``ngx_http.c:1308-1315``), verified against the vendored
    NGINX 1.30.4 binary itself:

        $ nginx -t   # two blocks, both `listen 0.0.0.0:8080 default_server;`
        nginx: [emerg] a duplicate default server for 0.0.0.0:8080
        nginx: configuration file test failed
    """

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

    def test_a_mono_site_service_still_owns_default_server_when_not_loading(self, render):
        """The guard must not cost the normal case its default server: outside loading the default
        server is not included at all (``http.conf:91-93``), so the service block is the only one
        that can carry the flag."""
        tree = render(MULTISITE="no", SERVER_NAME="a.example.com")
        included = included_blocks(tree)
        assert "server.conf" in included and "default-server-http.conf" not in included, included
        assert any("default_server" in line for _, line in listen_lines(tree, "server.conf"))


class TestEmptyPortRendersNoListen:
    """Constat C / PO-QUEUE 31 -- and the prerequisite of the list-replacement rule (§2.2), which
    can only express "the service replaces the inherited list" by writing empty ``_N`` values."""

    def test_every_rendered_listen_has_a_real_port(self, render):
        """The general form of the defect, over the whole tree rather than the three known loops."""
        tree = render(**STREAM)
        for path, line in listen_lines(tree):
            addr = line.split()[1].rstrip(";")
            assert addr.startswith("unix:") or _HOST_PORT_RX.match(addr), (path, line)

    @pytest.mark.parametrize("disabled", ["HTTP_PORT", "HTTPS_PORT"])
    def test_disabling_a_port_removes_the_default_server_listen_instead_of_emptying_it(self, render, disabled):
        """``settings.json:23`` documents the empty value as the way to disable listening. The
        default server rendered ``listen 0.0.0.0: default_server;`` for it, which NGINX rejects
        outright, so the documented behaviour took the whole instance down."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", **{disabled: ""})
        default_server = tree["default-server-http.conf"]
        assert "listen 0.0.0.0:;" not in default_server
        for line in default_server.splitlines():
            if line.strip().startswith("listen "):
                assert _HOST_PORT_RX.match(line.split()[1].rstrip(";")), line
        kept = "8443" if disabled == "HTTP_PORT" else "8080"
        assert f"listen 0.0.0.0:{kept}" in default_server, "disabling one protocol must not disable the other"

    def test_disabling_both_ports_leaves_the_default_server_with_no_listen(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", HTTP_PORT="", HTTPS_PORT="")
        assert [line for line in tree["default-server-http.conf"].splitlines() if line.strip().startswith("listen ")] == []

    def test_the_quic_loop_is_guarded_too(self, render):
        """The third unguarded loop (``:80``) only renders with HTTP3 on, which is the default."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", HTTPS_PORT="")
        assert "quic" not in tree["default-server-http.conf"]
