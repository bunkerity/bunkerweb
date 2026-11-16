"""A stream backend name that does not resolve must not fail the whole nginx load.

NGINX resolves every plain ``server <name>;`` of an ``upstream`` block when it loads the
configuration, so one deleted Kubernetes Service or removed container makes the load fail with
``[emerg] host not found in upstream`` and the reload is refused for every service on the
instance. ``server <name> resolve;`` (stream, nginx >= 1.27.3) moves the lookup to run time and
needs the upstream to live in a shared memory ``zone``. NGINX accepts it on IP literals too and
never queries DNS for them.
"""

import re
from pathlib import Path

import pytest
from jinja2 import ChainableUndefined, Environment

ROOT = Path(__file__).resolve().parents[3]
SERVICE = "tcp.example.com"


def _stream_service(render_tree, host, **extra):
    variables = {
        "MULTISITE": "yes",
        "SERVER_NAME": SERVICE,
        f"{SERVICE}_SERVER_TYPE": "stream",
        f"{SERVICE}_LISTEN_STREAM_PORT": "9000",
        f"{SERVICE}_USE_REVERSE_PROXY": "yes",
        f"{SERVICE}_REVERSE_PROXY_HOST": host,
    }
    variables.update({f"{SERVICE}_{key}": value for key, value in extra.items()})
    return render_tree(**variables)


def _upstream_block(text, name):
    match = re.search(r"^upstream " + re.escape(name) + r" \{\n(.*?)^\}", text, re.S | re.M)
    assert match, f"no upstream {name} in:\n{text}"
    return match.group(1)


@pytest.mark.parametrize("host", ["backend:9000", "backend.default.svc.cluster.local:9000"])
def test_a_named_backend_resolves_at_run_time(render_tree, host):
    block = _upstream_block(_stream_service(render_tree, host)["stream.conf"], SERVICE)
    assert re.search(rf"^\s*zone bw_svc_{re.escape(SERVICE)} \S+;$", block, re.M), block
    assert re.search(rf"^\s*server {re.escape(host)} resolve;$", block, re.M), block


@pytest.mark.parametrize("host", ["10.0.0.5:9000", "[2001:db8::1]:9000"])
def test_an_ip_literal_backend_keeps_its_address(render_tree, host):
    """NGINX takes `resolve` on a literal too and then never queries DNS for it."""
    block = _upstream_block(_stream_service(render_tree, host)["stream.conf"], SERVICE)
    assert re.search(rf"^\s*server {re.escape(host)} resolve;$", block, re.M), block


def _pool(servers, method="round_robin"):
    """Render the pool template alone.

    ``UPSTREAM_*`` are not operator settings (upstream_resolver writes them after the Configurator
    has run), so ``render_tree`` would drop them. The environment copies Templator's flags.
    """
    template = ROOT / "src" / "common" / "core" / "reverseproxy" / "confs" / "stream" / "upstreams.conf"
    env = Environment(undefined=ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    return env.from_string(template.read_text()).render(
        all={
            "UPSTREAM_NAME_1": "bw_stream_pool",
            "UPSTREAM_PROTOCOL_1": "stream",
            "UPSTREAM_METHOD_1": method,
            "UPSTREAM_SERVERS_1": servers,
        }
    )


def test_a_pool_resolves_its_named_members_at_run_time():
    block = _upstream_block(_pool("app-a:9000 weight=2;10.0.0.5:9000;[2001:db8::1]:9000"), "bw_stream_pool")
    assert re.search(r"^\s*zone bw_stream_pool \S+;$", block, re.M), block
    assert "server app-a:9000 weight=2 resolve;" in block
    assert "server 10.0.0.5:9000 resolve;" in block
    assert "server [2001:db8::1]:9000 resolve;" in block


def test_a_pool_keeps_its_balancing_method():
    block = _upstream_block(_pool("a:9000;b:9000", method="least_conn"), "bw_stream_pool")
    assert "least_conn;" in block
    assert block.count("resolve;") == 2
