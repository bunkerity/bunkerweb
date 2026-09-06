"""The reserved ``default-server`` service is a MULTISITE feature, and the rendered tree says so.

PO ruling of 2026-09-06, after the independent Criticos pass on DS-B. Everything that gives the
reserved row meaning is gated on ``MULTISITE=yes`` -- ``config_read`` materialises
``<service>_<SETTING>`` keys only there, and ``helpers.lua`` builds ``variables[<server>]`` only
there -- while the seeding, the roster and the three new phase runners were not. On a
``MULTISITE=no`` deployment that combination is not merely useless, it is wrong twice: the reserved
id reaches the one ``server_name`` directive non-multisite renders, and the runners execute the
curated chains against the GLOBAL values, which is how an upgrade starts answering catch-all traffic
with a 301 to https and a whitelist chain it never had.

Ten of the thirty shipped ``misc/integrations/*.yml`` never set ``MULTISITE`` -- ``docker.yml`` and
``all-in-one.yml`` among them -- and every other tier in this suite hardcodes ``MULTISITE=yes``,
which is why no existing test could see any of this.
"""

from importlib import import_module
from pathlib import Path
from re import escape
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader, Undefined

from default_server import DEFAULT_SERVER_ID  # type: ignore

_CONFS = Path(__file__).resolve().parents[3] / "src" / "common" / "confs"
_CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"

pytestmark = pytest.mark.slow

SERVICE = "app1.example.com"


@pytest.fixture
def flipped_to_single_site(render_db_tree):
    """The only way a single-site deployment can hold the reserved row: it was multisite once.

    The seeding stands down under ``MULTISITE=no`` (``db_methods/services.py``), so a deployment
    that was single-site from the start never has the row at all. This fixture renders multisite
    FIRST -- which is what creates it, through the save-time seeding trigger -- then renders the
    same services with multisite off. That is the state every guard below has to survive, and it is
    strictly harder than "no row at all".
    """

    def _render(globals_=None, services=None):
        services = services if services is not None else {SERVICE: {}}
        render_db_tree({"MULTISITE": "yes"} | (globals_ or {}), services)
        return render_db_tree({"MULTISITE": "no"} | (globals_ or {}), services)

    return _render


class TestTheIdNeverReachesTheRenderedConfiguration:
    def test_the_server_name_directive_is_the_operators_names_only(self, flipped_to_single_site):
        """Non-multisite renders ONE block from the WHOLE ``SERVER_NAME`` string, so the reserved id
        is not an unused list entry here -- it is an alias the block answers to, which takes
        ``default-server`` away from ``DISABLE_DEFAULT_SERVER`` and the strict-SNI path."""
        tree = flipped_to_single_site()
        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert f"server_name {SERVICE};" in server_conf
        assert DEFAULT_SERVER_ID not in server_conf

    def test_no_generated_modsecurity_host_exclusion_carries_it(self, flipped_to_single_site):
        """`antibot.modsec-crs` has TWO roster loops and only the multisite one was filtered. The
        non-multisite branch escapes every name into a `Host` exclusion regex, so the reserved id
        landed in a ModSecurity rule as `default\\-server`."""
        tree = flipped_to_single_site(
            {"USE_ANTIBOT": "captcha", "USE_MODSECURITY": "yes", "USE_MODSECURITY_CRS": "yes", "USE_MODSECURITY_GLOBAL_CRS": "yes"},
        )
        crs = [content for path, content in tree.items() if path.endswith("antibot.modsec-crs")]
        assert crs, sorted(tree)
        for content in crs:
            assert "default" not in content or DEFAULT_SERVER_ID.replace("-", r"\-") not in content
            assert DEFAULT_SERVER_ID not in content

    def test_the_whitelist_default_lookup_skips_it(self, flipped_to_single_site):
        """`core/whitelist/confs/default-server-http/whitelist.conf` takes the FIRST name of
        `SERVER_NAME` at request time. Order is engine-dependent, so the reserved id could be it --
        and the lookup then keys on a domain no whitelist job ever caches for."""
        tree = flipped_to_single_site({"USE_WHITELIST": "yes"})
        whitelist = next(content for path, content in tree.items() if path.endswith("default-server-http/whitelist.conf"))
        assert f'if name ~= "{DEFAULT_SERVER_ID}" then' in whitelist


class TestTheRunnersStandDown:
    def test_the_three_phase_runners_are_not_rendered(self, flipped_to_single_site):
        """Without the per-service materialisation and the per-site variables table they would run
        the curated chains against the GLOBAL values -- the exact behaviour change the seeded row
        exists to prevent in multisite, on a deployment that has no seeded row at all."""
        block = flipped_to_single_site()["default-server-http.conf"]
        assert "set_by_lua_block $default_server_dummy_set" not in block
        assert "access_by_lua_block" not in block
        assert "header_filter_by_lua_block" not in block
        assert f'ctx.bw.server_name = "{DEFAULT_SERVER_ID}"' not in block

    def test_the_certificate_phase_still_runs(self, flipped_to_single_site):
        """DS-A's certificate override is built from four GLOBAL settings, so it is the one half of
        the feature that must keep working in single-site -- it is what the documentation tells a
        single-site operator to use."""
        block = flipped_to_single_site()["default-server-http.conf"]
        # The DIRECTIVE, not the string: the partial names it twice more in its own comments.
        assert block.count("ssl_certificate_by_lua_block {") == 1
        assert "run_certificate_phase" in block

    def test_multisite_still_renders_them(self, render_db_tree):
        """The control. A gate that turned the runners off everywhere would pass every assertion
        above."""
        block = render_db_tree({"MULTISITE": "yes"}, {SERVICE: {}, DEFAULT_SERVER_ID: {}})["default-server-http.conf"]
        assert "set_by_lua_block $default_server_dummy_set" in block
        assert block.count("access_by_lua_block") == 1
        assert block.count("header_filter_by_lua_block") == 1


class TestTheRosterIsCleanAtTheSource:
    def test_the_database_keeps_the_row_but_not_the_roster_entry(self, db, render_db_tree):
        """`config_read` is where `SERVER_NAME` is rebuilt, and it is the guard that covers every
        renderer at once. The row is deliberately NOT deleted: an operator who turns multisite off
        and on again keeps everything they configured on the Default server page."""
        render_db_tree({"MULTISITE": "yes"}, {SERVICE: {}})
        assert DEFAULT_SERVER_ID in {service["id"] for service in db.get_services(with_drafts=True)}
        assert DEFAULT_SERVER_ID in db.get_config()["SERVER_NAME"].split()

        render_db_tree({"MULTISITE": "no"}, {SERVICE: {}})

        assert DEFAULT_SERVER_ID in {service["id"] for service in db.get_services(with_drafts=True)}
        assert DEFAULT_SERVER_ID not in db.get_config()["SERVER_NAME"].split()


# --------------------------------------------------------- the environment-variable path
# `config_read` strips the reserved id from the non-multisite roster, which is why every test above
# -- they all go through the database -- can never see the id reach a template. The OTHER generation
# path does not touch the database at all: `gen/main.py` builds the config with `Configurator` from
# the environment when the scheduler passes `--variables`, and an operator can put `default-server`
# in `SERVER_NAME` there by hand. These two are the guards for that path, and they are the only
# tests that can prove them.


class TestTheEnvironmentVariablePath:
    def test_the_templator_strips_the_id_from_a_non_multisite_server_name(self, render_tree):
        """`render_tree` is the `Configurator` path: raw variables in, no database. Non-multisite
        renders ONE block whose `server_name` is the whole string, so without the strip the block
        answers to `default-server` -- and `DISABLE_DEFAULT_SERVER` and the strict-SNI path stop
        covering that name."""
        tree = render_tree(SERVER_NAME=f"app.example.com {DEFAULT_SERVER_ID}", MULTISITE="no")
        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert "server_name app.example.com;" in server_conf
        assert DEFAULT_SERVER_ID not in server_conf

    def test_multisite_keeps_it_in_server_name(self, render_tree):
        """The control, and it has to be observable. The reserved id BELONGS in a multisite
        `SERVER_NAME`: the stream-port election reads it back out of the roster
        (`Templator.__init__` -> `_service_configs()` -> `default_server_stream_listeners`), so a
        strip that fired in multisite too would silently take the stream default server away. That
        is the one output that differs, which is why this asserts on `stream.conf` and not on the
        rendered directory list (identical either way)."""
        tree = render_tree(
            SERVER_NAME=f"app.example.com {DEFAULT_SERVER_ID}",
            MULTISITE="yes",
            **{f"{DEFAULT_SERVER_ID}_DEFAULT_SERVER_STREAM_PORTS": "9001"},
        )
        assert any(path.startswith("app.example.com/") for path in tree)
        assert not any(path.startswith(f"{DEFAULT_SERVER_ID}/") for path in tree)
        assert "9001" in tree["stream.conf"] and "default_server" in tree["stream.conf"]

    def test_the_strip_is_never_silent_and_never_empties_server_name(self, render_tree, monkeypatch):
        """Dropping a name changes which hostnames are served, so it is said out loud -- and when the
        reserved id is the LAST name left the strip stands down entirely instead of rendering an
        empty `SERVER_NAME`, which would mean no `server{}` block at all and a deployment that serves
        nothing. Under `MULTISITE=no` the reserved pseudo-service does not exist, so a
        `default-server` that gets this far is an operator's own service name; the warning tells them
        the id is reserved rather than taking their site down for them.

        The module logger is replaced rather than captured: `render_tree` MEMOISES on its variables,
        so the assertion has to be tied to a render that really happens, and the BunkerWeb logger's
        propagation is not this test's business.
        """
        import Templator as T  # type: ignore

        said = []
        monkeypatch.setattr(T, "logger", SimpleNamespace(warning=said.append, error=said.append, info=lambda *a: None, debug=lambda *a: None))

        render_tree(SERVER_NAME=f"warned.example.com {DEFAULT_SERVER_ID}", MULTISITE="no")
        assert [message for message in said if DEFAULT_SERVER_ID in message and "dropped it from" in message], said

        said.clear()
        tree = render_tree(SERVER_NAME=DEFAULT_SERVER_ID, MULTISITE="no", HTTP_PORT="8080")
        assert [message for message in said if DEFAULT_SERVER_ID in message and "is KEPT" in message], said
        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert f"server_name {DEFAULT_SERVER_ID};" in server_conf

    def test_single_site_gets_no_stream_default_server_from_a_global_port_list(self, render_tree):
        """The reason the strip is in `__init__` and not in `render()`: the stream-port election runs
        in the constructor, on the roster. With `SERVER_NAME=default-server` single-site the reserved
        id WAS the whole roster, so a GLOBAL `DEFAULT_SERVER_STREAM_PORTS` opened listeners the
        multisite-only ruling says cannot exist there."""
        tree = render_tree(SERVER_NAME=DEFAULT_SERVER_ID, MULTISITE="no", DEFAULT_SERVER_STREAM_PORTS="9001")
        assert "9001" not in tree["stream.conf"]


def _render_template(relative, **variables):
    """One core template, rendered the way Templator renders it (its `import` global included)."""
    env = Environment(  # nosec B701 - NGINX configuration, exactly as Templator builds it
        loader=FileSystemLoader([_CONFS.as_posix(), _CORE.as_posix()]),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
        undefined=Undefined,
    )
    env.globals["import"] = import_module
    env.globals["all"] = variables
    return env.get_template(relative).render(**variables)


class TestTheAntibotHostExclusion:
    r"""`antibot.modsec-crs` has TWO roster loops. DS-B filtered the multisite one; the
    `MULTISITE == "no"` branch escapes every name straight into a ModSecurity `Host` exclusion
    regex, so the reserved id shipped as `default\-server` inside a live rule -- and that escaped
    form is why a plain "the id is not in the output" assertion would not have caught it.
    """

    VARS = {
        "SERVER_NAME": f"app.example.com {DEFAULT_SERVER_ID}",
        "ANTIBOT_URI": "/challenge",
    }

    def test_the_non_multisite_branch_filters_it(self):
        rendered = _render_template("antibot/confs/http/antibot.modsec-crs", MULTISITE="no", **self.VARS)
        assert r"app\.example\.com" in rendered
        assert DEFAULT_SERVER_ID not in rendered
        assert escape(DEFAULT_SERVER_ID) not in rendered

    def test_it_still_emits_the_operators_own_hosts(self):
        """A filter that emptied the list would pass the assertion above and silently drop the
        antibot CRS exclusion for every real service."""
        rendered = _render_template("antibot/confs/http/antibot.modsec-crs", MULTISITE="no", **self.VARS)
        assert "SecRule REQUEST_HEADERS:Host" in rendered

    def test_the_only_name_case_keeps_its_exclusion(self):
        r"""And when the reserved id is the deployment's ONLY name it is NOT filtered, because
        `Templator` keeps it there (it is the operator's own service, the reserved row being
        multisite-only). Filtering it here would empty the list and drop the whole exclusion, so the
        one host this deployment serves would meet the CRS rules the challenge page must skip --
        which is what `SecRule REQUEST_HEADERS:Host` being absent means, not merely a shorter regex.
        """
        rendered = _render_template("antibot/confs/http/antibot.modsec-crs", MULTISITE="no", SERVER_NAME=DEFAULT_SERVER_ID, ANTIBOT_URI="/challenge")
        assert "SecRule REQUEST_HEADERS:Host" in rendered
        assert escape(DEFAULT_SERVER_ID) in rendered
