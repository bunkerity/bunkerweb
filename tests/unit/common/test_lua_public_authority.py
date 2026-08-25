"""``utils.public_authority`` — the authority an absolute URL built at request time must carry.

``HTTP_PORT`` / ``HTTPS_PORT`` became multisite (Lot B), so the port a service listens on is no
longer necessarily the global one. Three request-path call sites build an absolute URL out of a
host, and a wrong authority there sends the client to a socket nothing is listening on:
``ssl.lua`` (the HTTPS redirect), ``cors.lua`` (the self origin it compares Origin against) and
``ui.conf`` (the setup-wizard check).

The rule is per-service-list-differs-from-global, and the "equal" half carries most of the weight:
the images publish ``80:8080`` and ``443:8443`` (``misc/integrations/docker.yml:16-18``), so on a
standard install the RENDERED port is NOT the reachable one. Emitting it would break every
deployment that overrides nothing. Only a service whose list actually differs is on a port the
operator moved on purpose, and there the rendered port is the only one that reaches it.

Runs the real functions under a plain Lua interpreter with a fake ``internalstore`` -- ``utils.lua``
itself cannot be loaded outside OpenResty (its logger requires ``ngx.errlog``), so the sources are
lifted the same way ``test_lua_request_path_ports.py`` lifts them.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
CORS_LUA = ROOT / "src" / "common" / "core" / "cors" / "cors.lua"
SSL_LUA = ROOT / "src" / "common" / "core" / "ssl" / "ssl.lua"
UI_CONF = ROOT / "src" / "common" / "core" / "ui" / "confs" / "default-server-http" / "ui.conf"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

GLOBAL_ONLY = '{ global = { MULTISITE = "yes", HTTP_PORT = "8080", HTTPS_PORT = "8443" } }'


def _sources() -> str:
    text = UTILS_LUA.read_text(encoding="utf-8")
    chunks = [re.search(r"^local function port_list\(.*?^end$", text, re.S | re.M)]
    chunks += [
        re.search(rf"^utils\.{name} = function.*?^end$", text, re.S | re.M) for name in ("listen_port_override", "host_without_port", "public_authority")
    ]
    for chunk in chunks:
        assert chunk, "a helper was renamed -- this harness lifts them by name"
    return "\n".join(chunk.group(0) for chunk in chunks)


def run(variables: str, body: str) -> str:
    script = "local utils = {}\nlocal internalstore = { get = function() return %s, nil end }\n%s\n%s\n" % (variables, _sources(), body)
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def authority(variables: str, host: str, setting: str, service: str) -> str:
    return run(variables, f'print(utils.public_authority("{host}", "{setting}", "{service}"))')


class TestTheServiceDidNotMove:
    """Every one of these must return the host UNCHANGED. This is the whole install base."""

    def test_a_service_that_declares_nothing(self):
        variables = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["a.example.com"] = { SERVER_TYPE = "http" } }'
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com"

    def test_a_service_that_restates_the_global_list(self):
        variables = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTPS_PORT = "8443" } }'
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com"

    def test_a_non_multisite_instance(self):
        """One server block owns the whole instance: there is no "its own port" to speak of."""
        variables = '{ global = { MULTISITE = "no", HTTPS_PORT = "9443" } }'
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com"

    def test_a_host_that_matches_no_known_service(self):
        """The default server answers unknown Hosts. Guessing a port for one would be inventing a
        destination."""
        variables = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTPS_PORT = "9443" } }'
        assert authority(variables, "other.example.com", "HTTPS_PORT", "other.example.com") == "other.example.com"

    def test_a_service_with_no_listener_of_its_own(self):
        """``HTTPS_PORT=""`` disables listening (settings.json:23). There is no port to point at,
        so the host is left alone rather than gaining an empty ``:``."""
        variables = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTPS_PORT = "" } }'
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com"

    def test_a_nil_server_name(self):
        """``ctx.bw.server_name`` is absent in the default server's phases."""
        assert run(GLOBAL_ONLY, 'print(utils.public_authority("a.example.com", "HTTPS_PORT", nil))') == "a.example.com"


class TestTheServiceMoved:
    MOVED = '{ global = { MULTISITE = "yes", HTTP_PORT = "8080", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTP_PORT = "9080", HTTPS_PORT = "9443" } }'

    def test_the_port_is_appended(self):
        assert authority(self.MOVED, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com:9443"

    def test_each_setting_is_answered_independently(self):
        assert authority(self.MOVED, "a.example.com", "HTTP_PORT", "a.example.com") == "a.example.com:9080"

    def test_a_host_that_already_carries_a_port_does_not_gain_a_second(self):
        """``Host`` is client-supplied and routinely carries the port it was reached on. Naive
        concatenation yields ``a.example.com:8080:9443``, which is not a URL."""
        assert authority(self.MOVED, "a.example.com:8080", "HTTPS_PORT", "a.example.com") == "a.example.com:9443"

    def test_the_first_port_of_the_list_is_the_one_used(self):
        variables = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTPS_PORT_2 = "9444", HTTPS_PORT = "9443" } }'
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com:9443"

    def test_a_declared_repetition_alone_still_moves_the_service(self):
        """Suffixes need not start at 1 or be contiguous, and ``pairs()`` has no order -- the list
        is sorted by suffix, so the answer cannot depend on table iteration order."""
        variables = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTPS_PORT_7 = "9447" } }'
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com:9447"

    def test_the_same_ports_in_a_different_order_count_as_moved(self):
        variables = (
            '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443", HTTPS_PORT_1 = "8444" }, ["a.example.com"] = { HTTPS_PORT = "8444", HTTPS_PORT_1 = "8443" } }'
        )
        assert authority(variables, "a.example.com", "HTTPS_PORT", "a.example.com") == "a.example.com:8444"


class TestTheVariablesTableTheSchedulerActuallyWrites:
    """``variables.env`` is the ONLY view Lua has, and it is written from the FULL config
    (``Templator.py:648``) -- the inherited one, where every service carries a copy of every
    multisite setting that has a global row. For the port lists that copy is a lie: the service's
    block does not listen there. ``Templator._inherited_port_keys`` removes exactly those keys
    before the file is written, and these two cases are why.
    """

    def test_a_service_that_declared_only_a_repetition_answers_its_own_port(self):
        """The shape the scheduler writes TODAY: ``a`` declared ``HTTP_PORT_1=9081`` and the
        inherited ``HTTP_PORT`` copy is gone, so Lua sees the list the block really listens on."""
        variables = '{ global = { MULTISITE = "yes", HTTP_PORT = "8090" }, ["a.example.com"] = { HTTP_PORT_1 = "9081" } }'
        assert authority(variables, "a.example.com", "HTTP_PORT", "a.example.com") == "a.example.com:9081"

    def test_the_inherited_copy_is_what_made_it_answer_the_global_port(self):
        """Characterisation, not a wish: with the copy present -- what the raw full config carries
        -- the list sorts ``8090`` (suffix 0) ahead of ``9081`` and Lua answers 8090, a port
        ``a.example.com``'s server block does not listen on. Lua cannot tell an inherited value
        from a declared one, so the fix has to be on the writing side; if
        ``Templator._inherited_port_keys`` is ever removed, this is what comes back."""
        variables = '{ global = { MULTISITE = "yes", HTTP_PORT = "8090" }, ["a.example.com"] = { HTTP_PORT = "8090", HTTP_PORT_1 = "9081" } }'
        assert authority(variables, "a.example.com", "HTTP_PORT", "a.example.com") == "a.example.com:8090"

    def test_a_variables_table_with_no_global_section_does_not_raise(self):
        """``init_by_lua`` keeps the previous LRU data when ``variables.env`` is truncated
        (``api.lua:225``), so a partial table is reachable. Same guard as ``internal_api.lua:20``:
        degrade to "not multisite" instead of raising inside the access phase."""
        assert authority("{ }", "a.example.com", "HTTP_PORT", "a.example.com") == "a.example.com"


class TestHostWithoutPort:
    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("a.example.com", "a.example.com"),
            ("a.example.com:8080", "a.example.com"),
            # An IPv6 literal is bracketed in a Host header, and stripping `:%d+$` off a BARE one
            # would eat part of the address.
            ("[::1]:8080", "[::1]"),
            ("[2001:db8::1]", "[2001:db8::1]"),
        ],
    )
    def test_only_a_trailing_port_is_removed(self, host, expected):
        assert run(GLOBAL_ONLY, f'print(utils.host_without_port("{host}"))') == expected


class TestEveryCallSiteUsesIt:
    """Source-level, because the alternative -- a raw concatenation -- is what these files did
    before and is one edit away from coming back. Behaviour is covered above and, for the redirect,
    in ``test_ssl_acme_challenge_not_redirected.py``."""

    @pytest.mark.parametrize("path", [SSL_LUA, CORS_LUA, UI_CONF])
    def test_the_absolute_url_is_built_from_public_authority(self, path):
        text = path.read_text(encoding="utf-8")
        assert "public_authority(" in text, f"{path.name} builds an absolute URL without it"
        for scheme in ('"https://" .. self.ctx.bw.http_host', '"https://" .. args["server_name"]', '"http://" .. self.ctx.bw.server_name'):
            assert scheme not in text, f"{path.name} still concatenates a bare host: {scheme}"
