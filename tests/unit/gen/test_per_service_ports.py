"""Per-service HTTP/HTTPS listen ports: the context flip and everything it drags with it.

``HTTP_PORT`` and ``HTTPS_PORT`` were ``global``. Two locks read that same
``bw_settings.context`` column -- generation (``Configurator.py:390-391``, "context of X isn't
multisite") and the write paths (``config_read.py:58-59``, "not multisite") -- so one flip opens
both. What the flip needs around it is what this file covers:

* **List replacement.** ``multiple`` settings merge as a UNION and Templator builds a service view
  with ``copy()`` + ``update()`` (``Templator.py:646-648``), which can overwrite a key but never
  remove one. A service declaring ``HTTP_PORT=9000`` would keep listening on an inherited
  ``HTTP_PORT_1=8081``. Replacement is applied where the two generation paths converge, in
  ``Templator._get_server_config`` (``ports.drop_inherited_ports``): the inherited members are
  removed from the merged view when -- and only when -- the service declares a member of its own.
  Presence of the key is therefore the declaration, which is why ``Configurator`` stops
  materialising an inherited copy of a port under every service name.
* **The default server's union.** It renders once, globally, so it used to listen on the global
  ports only. A port only one service declares would then have no ``default_server``, and the first
  block on it silently becomes the implicit default. Measured in spike S2 against the vendored
  NGINX 1.30.4: an unknown SNI on such a port completed the handshake with that service's
  certificate instead of being refused, and an unknown Host reached that service. Both
  ``DISABLE_DEFAULT_SERVER`` and the strict-SNI rejection stop applying there.
* **Byte-identity.** A configuration that overrides nothing must render exactly as before. Proven
  mechanically by rendering the whole tree from two full ``src/common`` checkouts (HEAD and the
  working tree) and ``diff -r``-ing them -- see ``ports-build-report.md``. The invariant that makes
  it hold is pinned below so it cannot rot: with no override, the default server's ports ARE the
  global list, same values, same order.
"""

import json
import logging
from pathlib import Path

import pytest

from _listen_helpers import listen_addresses, listen_lines, socket_of  # type: ignore  (tests/unit/gen is on the path)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SERVER = "default-server-http.conf"


@pytest.fixture(scope="module")
def render(render_tree):
    """Short alias for the shared harness (conftest.render_tree)."""
    return render_tree


def ports_of(tree, name):
    return [address.rsplit(":", 1)[1] for address in listen_addresses(tree, name)]


class TestTheSettingIsMultisite:
    def test_both_port_settings_are_declared_multisite(self):
        """The flip itself. Both locks read this one column, so this is the whole unlock."""
        settings = json.loads((_REPO_ROOT / "src" / "common" / "settings.json").read_text())
        assert settings["HTTP_PORT"]["context"] == "multisite"
        assert settings["HTTPS_PORT"]["context"] == "multisite"
        # The multiple-ness and the defaults are unchanged: an existing global value keeps meaning
        # "the default of every service" (Configurator.py:344-360), so nothing has to be migrated.
        assert settings["HTTP_PORT"]["multiple"] == "listen-http-ports"
        assert settings["HTTPS_PORT"]["multiple"] == "listen-https-ports"
        assert settings["HTTP_PORT"]["default"] == "8080"
        assert settings["HTTPS_PORT"]["default"] == "8443"

    def test_a_prefixed_write_is_accepted_by_the_generation_lock(self, render):
        """``Configurator.__check_var`` used to answer "context of <svc>_HTTPS_PORT isn't
        multisite" and drop the value with a warning -- the service silently kept the global port."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com", **{"a.example.com_HTTPS_PORT": "9443"})
        assert ports_of(tree, "a.example.com/ssl-certificate-lua.conf") == ["9443", "9443"]  # TLS + QUIC
        assert ports_of(tree, "b.example.com/ssl-certificate-lua.conf") == ["8443", "8443"]

    def test_a_service_can_move_its_plain_http_port_too(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com", **{"a.example.com_HTTP_PORT": "9080"})
        assert ports_of(tree, "a.example.com/server.conf") == ["9080"]
        assert ports_of(tree, "b.example.com/server.conf") == ["8080"]

    def test_the_ports_are_allowed_by_the_pro_quota_classifier(self):
        """C8. Classification refuses any setting outside its allowlist, and these two just became
        per-service: without the entries, a redirect-only service that merely moved to another port
        would be classified `invalid` and start counting against the quota."""
        import sys

        sys.path.insert(0, str(_REPO_ROOT / "src" / "common" / "utils"))
        from service_classification import ALLOWED_SETTINGS  # type: ignore

        assert "HTTP_PORT" in ALLOWED_SETTINGS
        assert "HTTPS_PORT" in ALLOWED_SETTINGS


class TestListReplacement:
    """A declared list REPLACES the inherited one instead of adding to it."""

    GLOBAL_TWO = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com", "HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}

    def test_a_service_that_declares_the_base_port_drops_the_inherited_repetitions(self, render):
        """Without the rule the service would listen on 9000 AND on the inherited 8081, because
        ``dict.update`` cannot delete a key."""
        tree = render(**self.GLOBAL_TWO, **{"a.example.com_HTTP_PORT": "9000"})
        assert ports_of(tree, "a.example.com/server.conf") == ["9000"]

    def test_a_service_that_declares_only_a_repetition_drops_the_inherited_base(self, render):
        """Replacement is about the LIST, not about the base key: declaring ``_1`` alone means
        "my list is [that]", not "the global base plus mine"."""
        tree = render(**self.GLOBAL_TWO, **{"a.example.com_HTTP_PORT_1": "9001"})
        assert ports_of(tree, "a.example.com/server.conf") == ["9001"]

    def test_a_service_can_declare_several_ports_of_its_own(self, render):
        tree = render(**self.GLOBAL_TWO, **{"a.example.com_HTTP_PORT": "9000", "a.example.com_HTTP_PORT_1": "9001"})
        assert ports_of(tree, "a.example.com/server.conf") == ["9000", "9001"]

    def test_a_service_that_declares_nothing_keeps_the_whole_global_list_in_order(self, render):
        """The other half of the rule, and the one that makes the flip invisible to existing
        deployments."""
        tree = render(**self.GLOBAL_TWO, **{"a.example.com_HTTP_PORT": "9000"})
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]

    def test_an_explicitly_empty_port_disables_listening_for_that_service_alone(self, render):
        """``HTTP_PORT=""`` is documented as "disable HTTP listening" (settings.json:23). Declaring
        it per service must disable that service only -- and must not render a portless listen."""
        tree = render(**self.GLOBAL_TWO, **{"a.example.com_HTTP_PORT": ""})
        assert ports_of(tree, "a.example.com/server.conf") == []
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]

    def test_the_api_ports_are_not_read_as_a_service_declaration(self, render):
        """``_HTTP_PORT`` is a substring of ``API_HTTP_PORT``. Matching on the setting name alone
        made the control plane look like a service called "API", and the replacement rule then
        blanked its port -- api.conf rendered ``listen 0.0.0.0: reuseport;``, which NGINX rejects.
        The service prefix has to be a real service name.

        The API ports are left at their defaults on purpose: declaring them explicitly made this
        test pass for the wrong reason -- the old guard was bypassed and the assertion still held
        (mutation-verified)."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com")
        addresses = listen_addresses(tree, "api.conf")
        assert "0.0.0.0:" not in addresses and "127.0.0.1:" not in addresses, addresses
        assert "127.0.0.1:5000" in addresses, addresses

    def test_replacement_does_not_leak_across_the_two_settings(self, render):
        """Declaring an HTTP port must not silently drop the service's inherited HTTPS ports."""
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com",
            HTTP_PORT="8080",
            HTTP_PORT_1="8081",
            HTTPS_PORT="8443",
            HTTPS_PORT_1="8444",
            **{"a.example.com_HTTP_PORT": "9000"},
        )
        assert ports_of(tree, "a.example.com/server.conf") == ["9000"]
        assert ports_of(tree, "a.example.com/ssl-certificate-lua.conf") == ["8443", "8444", "8443", "8444"]

    def test_stream_ports_keep_their_union_semantics(self, render):
        """Deliberate asymmetry, called out in the docs. ``LISTEN_STREAM_PORT`` has been multisite
        and unioned since 1.6.0; making it replace instead would silently drop ports from
        deployments built on the current behaviour."""
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com",
            SERVER_TYPE="stream",
            LISTEN_STREAM_PORT="1337",
            LISTEN_STREAM_PORT_1="1338",
            **{"a.example.com_LISTEN_STREAM_PORT": "2337"},
        )
        assert ports_of(tree, "a.example.com/server-stream.conf") == ["2337", "1338"]


class TestDefaultServerUnion:
    """C5: the default server must cover every port any block listens on."""

    def test_a_service_only_port_gains_a_default_server(self, render):
        """Spike S2 measured what happens without this: on such a port an unknown SNI completed the
        handshake with the service's own certificate, and an unknown Host reached that service --
        DISABLE_DEFAULT_SERVER and the strict-SNI rejection both stopped applying."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com", **{"a.example.com_HTTPS_PORT": "9443"})
        # HTTP loop, then the TLS loop, then the QUIC loop -- each over the same union.
        assert ports_of(tree, DEFAULT_SERVER) == ["8080", "8443", "9443", "8443", "9443"]
        assert all("default_server" in line for _, line in listen_lines(tree, DEFAULT_SERVER))

    def test_the_union_puts_the_global_ports_first_and_keeps_their_order(self, render):
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            HTTP_PORT="8080",
            HTTP_PORT_1="8081",
            **{"a.example.com_HTTP_PORT": "9000", "b.example.com_HTTP_PORT": "9100"},
        )
        http_lines = [line for _, line in listen_lines(tree, DEFAULT_SERVER) if "ssl" not in line and "quic" not in line]
        assert [line.split()[1].rstrip(";").rsplit(":", 1)[1] for line in http_lines] == ["8080", "8081", "9000", "9100"]

    def test_a_service_port_equal_to_a_global_one_is_not_listed_twice(self, render):
        """A duplicated ``listen`` on the default server would be a duplicate ``default_server``,
        which NGINX refuses outright."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", **{"a.example.com_HTTP_PORT": "8080"})
        assert ports_of(tree, DEFAULT_SERVER).count("8080") == 1

    def test_default_server_and_quic_reuseport_stay_once_per_socket(self, render):
        """Both are listen OPTIONS, so both are fatal in duplicate (``ngx_http.c:1294-1315``)."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com", **{"a.example.com_HTTPS_PORT": "9443"})
        claimed = {}
        for _, line in listen_lines(tree, DEFAULT_SERVER):
            claimed.setdefault(socket_of(line), []).append(line)
        assert {socket: lines for socket, lines in claimed.items() if len(lines) > 1} == {}

    def test_a_stream_services_http_port_is_not_added_to_the_http_union(self, render):
        """The union and the inventory have to read the same gates or they contradict each other.

        A stream service renders no http block (``http.conf:107``) but still carries ``HTTP_PORT``
        like every other service. Counting its port in the default server's union makes http{}
        bind a port ``server-stream.conf`` already binds -- plain ``EADDRINUSE``, NGINX refuses to
        start, and ``check_ports`` reports nothing because it reports on the inventory the union
        would be contradicting."""
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{
                "a.example.com_SERVER_TYPE": "stream",
                "a.example.com_LISTEN_STREAM_PORT": "1337",
                "a.example.com_HTTP_PORT": "1337",
            },
        )
        assert "1337" not in ports_of(tree, DEFAULT_SERVER)
        assert ports_of(tree, "a.example.com/server-stream.conf") == ["1337"]

    def test_a_service_that_does_not_listen_on_http_is_not_added_either(self, render):
        """``LISTEN_HTTP=no`` renders no HTTP listen (``server.conf:27``), so its port is not a
        port anything binds."""
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{"a.example.com_LISTEN_HTTP": "no", "a.example.com_HTTP_PORT": "9000"},
        )
        assert "9000" not in ports_of(tree, DEFAULT_SERVER)
        # ...and its HTTPS port still is: only the HTTP family is gated by LISTEN_HTTP.
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{"a.example.com_LISTEN_HTTP": "no", "a.example.com_HTTPS_PORT": "9443"},
        )
        assert "9443" in ports_of(tree, DEFAULT_SERVER)

    def test_a_default_configuration_still_lists_exactly_the_global_ports(self, render):
        """The byte-identity invariant, pinned. The mechanical `diff -r` proof compares two full
        checkouts and cannot live in the suite (once committed, HEAD would contain the change and
        the comparison becomes a tautology); this is the property that made it hold."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com")
        assert ports_of(tree, DEFAULT_SERVER) == ["8080", "8443", "8443"]

    def test_the_derived_port_lists_reach_the_global_render(self, tmp_path, monkeypatch):
        """Wiring guard. Unlike the reuseport variable, these have no safe fallback: an undefined
        name would either raise or leave the default server with no ``listen`` at all -- and a
        server block without one silently listens on :80."""
        import Templator as T  # type: ignore

        monkeypatch.setattr(T, "sep", str(tmp_path))
        config = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com", "HTTP_PORT": "8080", "HTTPS_PORT": "8443"}
        templator = T.Templator(
            str(_REPO_ROOT / "src" / "common" / "confs"),
            str(_REPO_ROOT / "src" / "common" / "core"),
            str(tmp_path / "plugins"),
            str(tmp_path / "pro-plugins"),
            str(tmp_path / "out"),
            "/etc/nginx",
            config,
            {},
            dict(config),
        )
        assert templator._all_http_ports == ["8080"]
        assert templator._all_https_ports == ["8443"]


class TestOverridePositionIsPreserved:
    def test_overriding_an_existing_key_does_not_reorder_the_service_view(self, render):
        """``dict.update`` keeps the position of a key that already exists, so a per-service
        override lands where the global key was. Only a genuinely NEW repetition appends. That is
        what bounds the byte-identity check to the new-key case instead of the whole render."""
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com",
            HTTP_PORT="8080",
            HTTP_PORT_1="8081",
            **{"a.example.com_HTTP_PORT_1": "9081"},
        )
        # 8080 is blanked by the replacement rule; 9081 stays in HTTP_PORT_1's position.
        assert ports_of(tree, "a.example.com/server.conf") == ["9081"]

    def test_a_new_repetition_is_appended_after_the_inherited_ones(self, render):
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com",
            HTTP_PORT="8080",
            **{"a.example.com_HTTP_PORT": "9080", "a.example.com_HTTP_PORT_1": "9081"},
        )
        assert ports_of(tree, "a.example.com/server.conf") == ["9080", "9081"]


class TestTheSchedulerRenderPath:
    """The path almost every real port declaration takes, and the one the rule first missed.

    ``scheduler/main.py:427-441`` runs ``gen/main.py`` with no ``--variables``, so
    ``Configurator.get_config`` is never called: ``gen/main.py:128`` renders straight from
    ``db.get_non_default_settings()``. Anything declared through the UI, the API or autoconf
    arrives that way. A replacement rule that lived in Configurator therefore applied to
    environment-declared ports only -- the service listened on its own port AND on every inherited
    repetition, which is the union the rule exists to prevent.
    """

    GLOBAL_TWO = {"HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}

    def test_a_ui_declared_port_replaces_the_inherited_list(self, render_db_tree):
        tree = render_db_tree(self.GLOBAL_TWO, {"a.example.com": {"HTTP_PORT": "9000"}, "b.example.com": {}})
        assert ports_of(tree, "a.example.com/server.conf") == ["9000"]

    def test_a_service_that_declared_nothing_still_inherits_the_whole_list(self, render_db_tree):
        """The half that must not regress: ``config_read.py:190`` materialises an inherited copy of
        every multisite setting per service, so "the key is present" cannot be read off the full
        config -- only off the non-default one."""
        tree = render_db_tree(self.GLOBAL_TWO, {"a.example.com": {"HTTP_PORT": "9000"}, "b.example.com": {}})
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]

    def test_the_default_server_covers_the_declared_port_on_this_path_too(self, render_db_tree):
        """C5 again: the union is computed from the same merged views, so it has to see the
        replacement as well or the default server keeps offering 8081 that nothing serves."""
        tree = render_db_tree(self.GLOBAL_TWO, {"a.example.com": {"HTTP_PORT": "9000"}, "b.example.com": {}})
        http_ports = [address.rsplit(":", 1)[1] for address in listen_addresses(tree, DEFAULT_SERVER) if "8443" not in address]
        assert http_ports == ["8080", "8081", "9000"]

    def test_a_service_that_disabled_its_http_listener_keeps_no_inherited_repetition(self, render_db_tree):
        """``HTTP_PORT=""`` is the DOCUMENTED way to disable HTTP listening (``settings.json:23``),
        and it only means that if the inherited repetitions go with it. This shape needs more than
        one global port to fail, which is exactly what Lot D documents for the first time."""
        tree = render_db_tree(self.GLOBAL_TWO, {"a.example.com": {"HTTP_PORT": ""}, "b.example.com": {}})
        assert ports_of(tree, "a.example.com/server.conf") == []
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]

    def test_declaring_only_a_repetition_replaces_the_whole_inherited_list(self, render_db_tree):
        """A declaration is a declaration whichever member of the list carries it. Read off the
        NON-default view, ``a`` declared ``HTTP_PORT_1`` alone -- so the inherited ``HTTP_PORT``
        goes, and the service listens on 9081 and nothing else."""
        # 8090, not the declared default 8080: `save_config` writes no row for a value equal to
        # the default, and a global with no row materialises no inherited copy either -- so the
        # default would hide the very leak this pins.
        tree = render_db_tree({"HTTP_PORT": "8090"}, {"a.example.com": {"HTTP_PORT_1": "9081"}, "b.example.com": {}})
        assert ports_of(tree, "a.example.com/server.conf") == ["9081"]
        assert ports_of(tree, "b.example.com/server.conf") == ["8090"]

    PARTIAL_DEFAULT = {"HTTP_PORT_1": "8081"}
    """The fleet on its declared default plus one repetition — so ``HTTP_PORT`` has NO row.

    ``save_config`` writes no row for a value equal to the declared default, so this is what every
    fleet that added a second port without moving the first one looks like in the database. It is
    also the shape a write path cannot see: ``routers/services.py:62`` hands over
    ``get_non_default_settings()``, where the fleet's main port is simply absent.
    """

    def test_a_service_restating_the_fleets_effective_list_declares_nothing(self, render_db_tree, db):
        """The per-service form renders the fleet's EFFECTIVE list and posts it back. Deciding
        member by member dropped the base (it equals the declared default) and kept the repetition
        (it does not), so the service ended up declaring ``HTTP_PORT_1`` alone and the replacement
        rule took the fleet's main port away from a service that asked for nothing."""
        tree = render_db_tree(self.PARTIAL_DEFAULT, {"a.example.com": {"HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}, "b.example.com": {}})
        assert ports_of(tree, "a.example.com/server.conf") == ["8080", "8081"]
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]
        stored = db.get_non_default_settings(with_drafts=True)
        assert not [key for key in stored if key.startswith("a.example.com_HTTP_PORT")]

    def test_changing_one_member_persists_the_whole_posted_list(self, render_db_tree, db):
        """The other half of the same atomicity. The service changes the repetition only; the base
        it posts is the fleet's, so member-by-member dropped it and the service declared the
        repetition alone — losing the base it had just been shown."""
        tree = render_db_tree(self.PARTIAL_DEFAULT, {"a.example.com": {"HTTP_PORT": "8080", "HTTP_PORT_1": "9081"}, "b.example.com": {}})
        assert ports_of(tree, "a.example.com/server.conf") == ["8080", "9081"]
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]
        stored = db.get_non_default_settings(with_drafts=True)
        assert stored["a.example.com_HTTP_PORT"] == "8080" and stored["a.example.com_HTTP_PORT_1"] == "9081"

    def test_putting_a_moved_service_back_on_the_fleets_list_removes_its_rows(self, render_db_tree, db):
        """Two saves, which is the shape none of the other cases here exercise -- and the only one
        that reaches the DELETE side.

        A member sitting on the fleet's own value never CHANGES, so the update branch (which needs
        `value_changed`) could not remove its row. Undoing a move therefore left exactly that row
        behind, and its bare presence is what `drop_inherited_ports` reads as "this whole list is
        mine": the service that had just been put back on the fleet's ports lost every one of them
        but the first."""
        fleet = {"HTTP_PORT_1": "8081"}
        moved = render_db_tree(fleet, {"a.example.com": {"HTTP_PORT": "8080", "HTTP_PORT_1": "8082"}})
        assert ports_of(moved, "a.example.com/server.conf") == ["8080", "8082"]

        # The undo: the operator puts the service back on the list the fleet uses.
        restored = render_db_tree(fleet, {"a.example.com": {"HTTP_PORT": "8080", "HTTP_PORT_1": "8081"}})
        assert ports_of(restored, "a.example.com/server.conf") == ["8080", "8081"]
        stored = db.get_non_default_settings(with_drafts=True)
        assert not [key for key in stored if key.startswith("a.example.com_HTTP_PORT")]

    def test_a_move_survives_the_fleet_converging_onto_it(self, render_db_tree, db):
        """Two saves. A service really moves to 9000; the fleet later converges onto 9000 and adds
        a repetition of its own. The next unrelated write re-posts the full snapshot — that is what
        ``PATCH /services`` sends — and the service must still be listening where it was put.

        Deciding member by member answered "not moved" here, because the one key the service posts
        matches the fleet's base. As a LIST it is a move: the service asks for one port and the
        fleet has two. The row was deleted and the service silently gained 9001."""
        moved = render_db_tree({"HTTP_PORT_1": "9001"}, {"a.example.com": {"HTTP_PORT": "9000"}})
        assert ports_of(moved, "a.example.com/server.conf") == ["9000"]

        still_moved = render_db_tree({"HTTP_PORT": "9000", "HTTP_PORT_1": "9001"}, {"a.example.com": {"HTTP_PORT": "9000"}})
        assert ports_of(still_moved, "a.example.com/server.conf") == ["9000"]
        assert db.get_non_default_settings(with_drafts=True)["a.example.com_HTTP_PORT"] == "9000"

    def test_a_shortened_list_survives_a_re_post_without_the_empty_repetition(self, render_db_tree, db):
        """The other subset shape. An empty ``_N`` is the documented way to shorten a list; a form
        that re-posts the service afterwards sends the members it has, and the empty one is not one
        of them. Per member that reads as "restating the fleet's base" and undid the shortening."""
        fleet = {"HTTP_PORT_1": "8081"}
        shortened = render_db_tree(fleet, {"a.example.com": {"HTTP_PORT": "8080", "HTTP_PORT_1": ""}})
        assert ports_of(shortened, "a.example.com/server.conf") == ["8080"]

        re_posted = render_db_tree(fleet, {"a.example.com": {"HTTP_PORT": "8080"}})
        assert ports_of(re_posted, "a.example.com/server.conf") == ["8080"]
        assert db.get_non_default_settings(with_drafts=True)["a.example.com_HTTP_PORT"] == "8080"

    def test_emptying_a_repetition_is_still_how_a_service_drops_one(self, render_db_tree):
        """The documented way to shorten the list (conception §2.2): an empty ``_N``. It has to keep
        working through the atomic rule, or there is no way to say "the base only"."""
        tree = render_db_tree(self.PARTIAL_DEFAULT, {"a.example.com": {"HTTP_PORT": "8080", "HTTP_PORT_1": ""}, "b.example.com": {}})
        assert ports_of(tree, "a.example.com/server.conf") == ["8080"]
        assert ports_of(tree, "b.example.com/server.conf") == ["8080", "8081"]

    def test_variables_env_carries_the_ports_the_service_actually_listens_on(self, render_db_tree):
        """``variables.env`` is the Lua side's ONLY view of the configuration, and it is written
        from the raw full config (``Templator.py:648``) -- the INHERITED one. Without
        :meth:`Templator._inherited_port_keys`, ``utils.listen_port_override`` reads
        ``a.example.com_HTTP_PORT=8080`` here and answers 8080 for a service whose block listens on
        9081 alone, so every absolute URL C1/C2/C3/C7 build points at a port nothing serves."""
        tree = render_db_tree({"HTTP_PORT": "8090"}, {"a.example.com": {"HTTP_PORT_1": "9081"}, "b.example.com": {}})
        variables = dict(line.split("=", 1) for line in tree["variables.env"].splitlines() if "=" in line)
        assert [key for key in variables if key.startswith("a.example.com_HTTP_PORT")] == ["a.example.com_HTTP_PORT_1"]
        # The service that declared nothing keeps the whole inherited list, so Lua sees the same
        # list as the global one and correctly answers "did not move".
        assert sorted(key for key in variables if key.startswith("b.example.com_HTTP_PORT")) == [
            "b.example.com_HTTP_PORT",
        ]


class TestThePortReportRunsOnBothGenerationPaths:
    """``check_ports`` / ``reserved_ports`` used to be called from ``Configurator``, which only the
    ENVIRONMENT path constructs: ``scheduler/main.py`` runs ``gen/main.py`` with no ``--variables``,
    so the database render — the one path where per-service ports can be declared at all — got no
    FATAL collision report and no reserved/privileged warning. The report now runs in
    ``Templator.__init__``, the one object both paths build, over the merged per-service views.
    """

    def test_an_http_stream_collision_is_reported_on_the_database_path(self, render_db_tree, caplog):
        """The one FATAL of the family: http{} and stream{} open their own sockets, so the same TCP
        port in both is an EADDRINUSE at bind time rather than a shared listener."""
        with caplog.at_level(logging.WARNING, logger="TEMPLATOR"):
            render_db_tree(
                {},
                {
                    "a.example.com": {"HTTP_PORT": "9000"},
                    "b.example.com": {"SERVER_TYPE": "stream", "LISTEN_STREAM_PORT": "9000"},
                },
            )
        fatals = [record.message for record in caplog.records if record.message.startswith("Listen port conflict")]
        assert any("9000" in message for message in fatals), caplog.text

    def test_a_reserved_port_is_reported_on_the_database_path(self, render_db_tree, caplog):
        """6000 is the internal healthcheck (`healthcheck.conf:7`, hardcoded), so a service that
        takes it silently breaks the instance's own liveness probe."""
        with caplog.at_level(logging.WARNING, logger="TEMPLATOR"):
            render_db_tree({}, {"a.example.com": {"HTTP_PORT": "6000"}})
        reported = [record.message for record in caplog.records if record.message.startswith(("Listen port conflict", "Listen port warning"))]
        assert any("6000" in message for message in reported), caplog.text

    def test_a_clean_configuration_reports_nothing(self, render_db_tree, caplog):
        """Anti-vacuity: the assertions above must not pass because the reporter shouts at
        everything."""
        with caplog.at_level(logging.WARNING, logger="TEMPLATOR"):
            render_db_tree({}, {"a.example.com": {}, "b.example.com": {"HTTP_PORT": "9000"}})
        assert not [record.message for record in caplog.records if record.message.startswith(("Listen port conflict", "Listen port warning"))], caplog.text


class TestATemplateCanSupplyThePort:
    """A template-resolved port is a DECLARATION, not an inheritance.

    ``Configurator`` resolves the service's template overlay into
    ``service_template_settings`` and writes the resolved value under the service name. Ports are
    the one family it does not materialise an inherited copy of -- but a template really did supply
    this one, so it must be written, or the service ends up with no HTTP listener at all where HEAD
    gave it the global port.
    """

    def test_a_template_supplied_port_survives(self, tmp_path, monkeypatch):
        import Templator as T  # type: ignore
        from Configurator import Configurator  # type: ignore

        class _FakeDB:
            """Only what ``__resolve_template_settings`` reads."""

            def resolve_template_settings(self, raw_value):
                return {"HTTP_PORT": "9000"}, []

        monkeypatch.setattr(T, "sep", str(tmp_path))
        config = Configurator(
            str(_REPO_ROOT / "src" / "common" / "settings.json"),
            str(_REPO_ROOT / "src" / "common" / "core"),
            str(tmp_path / "plugins"),
            str(tmp_path / "pro-plugins"),
            {"MULTISITE": "yes", "SERVER_NAME": "a.example.com", "a.example.com_USE_TEMPLATE": "ports"},
            logging.getLogger("template-port"),
        ).get_config(_FakeDB())
        assert config["a.example.com_HTTP_PORT"] == "9000"

    def test_a_service_with_no_declaration_gets_no_port_key_at_all(self, render):
        """The invariant the rule rests on: presence IS the declaration. If an inherited copy were
        materialised here it would also be PERSISTED -- the scheduler saves this config back -- and
        the database path would then read a declaration the operator never made."""
        render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com", HTTP_PORT="8080", HTTP_PORT_1="8081")
        from Configurator import Configurator  # type: ignore

        config = Configurator(
            str(_REPO_ROOT / "src" / "common" / "settings.json"),
            str(_REPO_ROOT / "src" / "common" / "core"),
            str(_REPO_ROOT / "src" / "common" / "core"),  # unused: no external/pro plugins here
            str(_REPO_ROOT / "src" / "common" / "core"),
            {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com", "HTTP_PORT": "8080", "HTTP_PORT_1": "8081"},
            logging.getLogger("no-port-key"),
        ).get_config(None)
        assert "a.example.com_HTTP_PORT" not in config and "a.example.com_HTTPS_PORT" not in config
        # ...while every other multisite setting still gets one, so this is a port-specific rule
        # and not an accidental hole in the expansion.
        assert config["a.example.com_SERVER_TYPE"] == "http"
