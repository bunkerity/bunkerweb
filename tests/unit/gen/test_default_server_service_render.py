"""The default server block, rendered from the reserved ``default-server`` pseudo-service.

Before conception option (b) this block was rendered in the GLOBAL pass with the global config and
nothing else (``Templator._render_global``), so nothing about it could be configured. It is now
rendered from the reserved service's own merged configuration -- the same merge a service block
gets -- which is the entire point of giving it a page. Four properties are load-bearing, and each
one is a way to ship a broken default server silently:

* its settings reach the block,
* the reserved row never becomes a competing ``server{}``,
* the block keeps rendering exactly as before on every deployment that has no reserved row,
* the three new phase runners carry the curated subset and nothing else.
"""

from pathlib import Path

import pytest

from default_server import DEFAULT_SERVER_ID, DEFAULT_SERVER_PLUGINS  # type: ignore

pytestmark = pytest.mark.slow

_REPO_ROOT = Path(__file__).resolve().parents[3]

# The plugins the conception refuses BY NAME, rather than "everything outside the allowlist": a
# change that quietly put one of these back would still satisfy a "the table equals the constant"
# assertion, and these eight are the ones that assume a service identity.
REFUSED_PLUGINS = ("reverseproxy", "grpc", "redirect", "sessions", "antibot", "mtls", "cors", "authbasic")

SERVICE = "app1.example.com"


class TestTheReservedServiceConfiguresTheBlock:
    def test_its_own_setting_reaches_the_default_server(self, render_db_tree):
        tree = render_db_tree(
            {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"},
            {SERVICE: {}, DEFAULT_SERVER_ID: {"SSL_PROTOCOLS": "TLSv1.3"}},
        )
        assert "ssl_protocols TLSv1.3;" in tree["default-server-http.conf"]
        # ... and the service block is untouched by it, which is the half that says the two
        # configurations really are separate. (`ssl_protocols` renders from core/ssl's own
        # server-http fragment for a service, and inline in the default server block.)
        service_tree = "".join(text for path, text in tree.items() if path.startswith(f"{SERVICE}/"))
        assert "ssl_protocols TLSv1.2 TLSv1.3;" in service_tree

    def test_the_global_value_still_applies_when_the_reserved_service_declares_nothing(self, render_db_tree):
        tree = render_db_tree({"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})
        assert "ssl_protocols TLSv1.2 TLSv1.3;" in tree["default-server-http.conf"]

    def test_seeding_the_row_changes_nothing_on_its_own(self, render_db_tree):
        """Seeding is inert; the lane is NOT. Read the name literally -- this says the *row*
        appearing changes no byte of the block, because `_default_server_template_vars` falls back
        to the caller's global variables when the row has no settings of its own. It deliberately
        does NOT say the block renders as it did before this lane: both sides here are the NEW
        renderer, and both carry the three phase runners, which is a real behaviour change on every
        deployment (`test_the_runners_render_with_or_without_the_reserved_row` below). Naming this
        "exactly as before" is how that change would have shipped unnoticed."""
        with_row = render_db_tree({"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})
        without_row = render_db_tree({"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}, {SERVICE: {}})
        assert with_row["default-server-http.conf"] == without_row["default-server-http.conf"]

    def test_the_runners_render_with_or_without_the_reserved_row(self, render_db_tree):
        """The behaviour change this lane ships, written down where it can be found.

        PO ruling 5 asks for the three runners, and they are not conditional on anything but
        `IS_LOADING`. So on EVERY deployment that takes this code the catch-all block starts
        executing the curated plugin chains it never executed before, resolving whatever GLOBAL
        multisite values are set: `ssl:access()` (a global AUTO_REDIRECT_HTTP_TO_HTTPS now redirects
        unknown-host traffic), `misc:access()` (ALLOWED_METHODS now answers 405 there),
        `whitelist:access()`, the ban check, and `headers:header()`. That is the point of the
        chantier -- the default server used to be a hole where none of it applied -- but it is a
        change at upgrade, not an opt-in, and it is declared in `report-DS-B.md` as such."""
        for services in ({SERVICE: {}, DEFAULT_SERVER_ID: {}}, {SERVICE: {}}):
            block = render_db_tree({}, services)["default-server-http.conf"]
            assert "set_by_lua_block $default_server_dummy_set" in block, services
            assert block.count("access_by_lua_block") == 1, services
            assert block.count("header_filter_by_lua_block") == 1, services


class TestTheReservedRowIsNeverAServerBlock:
    def test_http_conf_includes_no_server_for_it(self, render_db_tree):
        tree = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})
        assert f"include /etc/nginx/{SERVICE}/server.conf;" in tree["http.conf"]
        assert f"/etc/nginx/{DEFAULT_SERVER_ID}/server.conf" not in tree["http.conf"]

    def test_stream_conf_includes_no_server_for_it(self, render_db_tree):
        """The reserved row carries ``SERVER_TYPE: stream`` here on purpose. Both of `stream.conf`'s
        roster loops already gate on that value, so with the shipped default (``http``) the reserved
        id never reaches them and this test would pass with the filter deleted -- it would prove
        nothing. `SERVER_TYPE` is not in the curated subset and so is not offered on the Default
        server page, but `PATCH /services/default-server` takes arbitrary variables, and this is the
        one case where the filter is what stands between that and a competing stream block."""
        tree = render_db_tree(
            {},
            {SERVICE: {"SERVER_TYPE": "stream"}, DEFAULT_SERVER_ID: {"SERVER_TYPE": "stream"}},
        )
        assert f"include /etc/nginx/{SERVICE}/server-stream.conf;" in tree["stream.conf"]
        assert f"/etc/nginx/{DEFAULT_SERVER_ID}/server-stream.conf" not in tree["stream.conf"]

    def test_no_sites_directory_is_rendered_for_it(self, render_db_tree):
        """Not only "not included": not written at all. A rendered directory nothing includes is
        dead output on every reload, and the next person to read the tree would reasonably conclude
        the reserved service has a server block."""
        tree = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})
        assert not [path for path in tree if path.startswith(f"{DEFAULT_SERVER_ID}/")]
        assert [path for path in tree if path.startswith(f"{SERVICE}/")]


class TestTheThreeRunners:
    def test_all_three_are_rendered(self, render_db_tree):
        block = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})["default-server-http.conf"]
        assert "set_by_lua_block $default_server_dummy_set" in block
        assert block.count("access_by_lua_block") == 1
        assert block.count("header_filter_by_lua_block") == 1

    def test_they_bind_the_reserved_service_id(self, render_db_tree):
        """PO ruling 1: `server_name _;` stays, and the runners rebind the CONTEXT instead, which is
        what makes `utils.get_variable` resolve `variables["default-server"]`."""
        block = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})["default-server-http.conf"]
        assert "\tserver_name _;\n" in block
        assert block.count(f'ctx.bw.server_name = "{DEFAULT_SERVER_ID}"') == 3
        # The other half of the rebind, and the one the context assignment does not imply: the
        # runner's own `get_phase_order` looks the per-site plugin ORDER up under the same id. With
        # `_` there the reserved service's ordering silently falls back to the global one.
        assert block.count(f'local server_name = "{DEFAULT_SERVER_ID}"') == 3
        # Restored on every path, or `log_default` and badbehavior's `_` test break.
        assert block.count("ctx.bw.server_name = previous_server_name") >= 3

    def test_the_curated_subset_is_the_python_constant(self, render_db_tree):
        block = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})["default-server-http.conf"]
        for plugin in DEFAULT_SERVER_PLUGINS:
            assert f'["{plugin}"] = true' in block, plugin

    def test_a_refused_plugin_is_never_allowed(self, render_db_tree):
        block = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})["default-server-http.conf"]
        for plugin in REFUSED_PLUGINS:
            assert f'["{plugin}"] = true' not in block, plugin

    def test_the_service_blocks_keep_the_unrestricted_runners(self, render_db_tree):
        """The restriction is the DEFAULT server's, never the product's: a service block still runs
        every plugin, with no allowlist table at all."""
        service_block = render_db_tree({}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})[f"{SERVICE}/access-lua.conf"]
        assert "allowed_plugins" not in service_block


class TestRenderStates:
    def test_the_runners_are_skipped_while_loading(self, render_tree):
        block = render_tree(MULTISITE="yes", SERVER_NAME=SERVICE, IS_LOADING="yes")["default-server-http.conf"]
        assert "$default_server_dummy_set" not in block
        assert "access_by_lua_block" not in block

    @staticmethod
    def _server_level(tree):
        """Everything NGINX parses at the default server's own level.

        `default-server-http.conf` ends with `include /etc/nginx/default-server-http/*.conf;`, so
        the plugin fragments are separate FILES that land inside the same `server{}`. Counting only
        the block file would have missed the one duplicate that matters."""
        return tree["default-server-http.conf"] + "".join(text for path, text in tree.items() if path.startswith("default-server-http/"))

    def test_exactly_one_access_block_in_bootstrap_mode(self, render_tree):
        """NGINX accepts one `access_by_lua_block` per level ("is duplicate", ngx_http_lua_accessby.c),
        and `core/ui/confs/default-server-http/ui.conf` renders one into this same server block
        whenever the UI is reached through the default server. The access runner's Jinja condition is
        that file's condition verbatim; this is what fails if either side drifts."""
        bootstrap = self._server_level(render_tree(MULTISITE="yes", SERVER_NAME=SERVICE, UI_HOST="http://ui:7000"))
        assert bootstrap.count("access_by_lua_block") == 1
        assert "$backendui" in bootstrap  # it is ui.conf's block, not the runner's

        configured = self._server_level(render_tree(MULTISITE="yes", SERVER_NAME=SERVICE, UI_HOST="http://ui:7000", USE_UI="yes"))
        assert configured.count("access_by_lua_block") == 1
        assert "$backendui" not in configured  # ... and here it is the runner's

        plain = self._server_level(render_tree(MULTISITE="yes", SERVER_NAME=SERVICE))
        assert plain.count("access_by_lua_block") == 1


class TestTheReservedIdNeverReachesAGeneratedRule:
    """The roster loops outside `http.conf`/`stream.conf`.

    Three global-context plugin templates iterate `SERVER_NAME.split()` and put each name into a
    generated rule. Two of them build CRS **exclusion** rules keyed on `Host`, so before the filter
    a request carrying `Host: default-server` picked up the antibot and UI exclusions:

        http/antibot.modsec-crs : ... "@rx ^(?:app\\.example\\.com|default\\-server)(?::\\d+)?$" ...
        http/ui.modsec-crs      : ... "@rx ^(?:app\\.example\\.com|default\\-server)(?::\\d+)?$" ...

    The third unions `ALLOWED_METHODS` across the roster, so the reserved row's INHERITED value
    widens `tx.allowed_methods` for an operator who narrowed every real service. Measured on a real
    render, not reasoned about -- which is why this test renders the real tree too.
    """

    GLOBALS = {
        "USE_ANTIBOT": "captcha",
        "USE_UI": "yes",
        "USE_MODSECURITY": "yes",
        "USE_MODSECURITY_CRS": "yes",
        # The third template renders NOTHING without it, and an empty file satisfies an
        # "the id is absent" assertion for free.
        "USE_MODSECURITY_GLOBAL_CRS": "yes",
    }

    # The three global-context templates that iterate the roster. `http.conf` and `stream.conf` are
    # the other two and are covered by TestTheReservedRowIsNeverAServerBlock above.
    ROSTER_RULES = ("http/antibot.modsec-crs", "http/ui.modsec-crs", "http/modsecurity-rules-global-crs.conf.modsec")

    def test_no_generated_rule_names_the_reserved_id(self, render_db_tree):
        tree = render_db_tree(self.GLOBALS, {SERVICE: {}, DEFAULT_SERVER_ID: {}})
        escaped = DEFAULT_SERVER_ID.replace("-", "\\-")
        for path in self.ROSTER_RULES:
            rendered = tree[path]
            # Guards the guard: each of these renders empty under the wrong globals, and an empty
            # file passes an absence assertion without proving anything.
            assert rendered.strip(), f"{path} rendered empty -- this assertion would prove nothing"
            assert DEFAULT_SERVER_ID not in rendered, path
            assert escaped not in rendered, path

    def test_the_reserved_row_does_not_widen_the_global_allowed_methods(self, render_db_tree):
        """The third template names nobody -- it UNIONS `ALLOWED_METHODS` across the roster -- so the
        leak there is a wider `tx.allowed_methods`, not a leaked string.

        The reserved row inherits the global default (`GET|POST|HEAD|QUERY`), so an operator who
        narrowed every real service to GET would get the full default back in the CRS variable, from
        a pseudo-service that serves no application.
        """
        tree = render_db_tree(self.GLOBALS | {"ALLOWED_METHODS": "GET|POST|HEAD|QUERY"}, {SERVICE: {"ALLOWED_METHODS": "GET"}, DEFAULT_SERVER_ID: {}})
        rendered = tree["http/modsecurity-rules-global-crs.conf.modsec"]
        assert "tx.allowed_methods" in rendered, sorted(tree)
        line = next(ln for ln in rendered.splitlines() if "tx.allowed_methods" in ln)
        assert "GET" in line
        for widened in ("POST", "HEAD", "QUERY"):
            assert widened not in line, line

    def test_the_real_service_still_reaches_those_rules(self, render_db_tree):
        """The filter must drop one name, not empty the loop."""
        tree = render_db_tree(self.GLOBALS, {SERVICE: {}, DEFAULT_SERVER_ID: {}})
        for path in ("http/antibot.modsec-crs", "http/ui.modsec-crs"):
            assert SERVICE.replace(".", "\\.") in tree[path], path
