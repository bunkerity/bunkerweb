"""`X-SSL-*` request headers are stripped on ingress, on every site, always.

This is the mechanism behind a guarantee the mTLS documentation states outright: *"a client cannot
spoof `X-SSL-Client-Verify: SUCCESS`"*. Applications are told to gate authorization on that header,
so if the strip ever stops being emitted, every mTLS-protected backend behind BunkerWeb starts
trusting a header any client can set. Until now the only thing standing behind it was a single
`grep -qF` in a marker script, which proves the line exists, not that it is emitted.

Two code paths, because one guard per behaviour is not one guard per path:

* the strip itself, in `http.conf`, which must be unconditional -- a site with `USE_MTLS=no` still
  has to have forged headers removed, because a *reverse-proxied* app cannot tell the difference;
* the legitimate producers, which must read the TLS handshake variables (`$ssl_client_*`) and never
  the incoming request header (`$http_x_ssl_*`). A producer reading the request header would put
  the forged value back after the strip removed it, and the strip would still be there, still
  emitted, still passing a test that only looked at `http.conf`.
"""

import re
from pathlib import Path

import pytest
from jinja2 import ChainableUndefined, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
STRIP = 'more_clear_input_headers "X-SSL-*" "X_SSL_*";'

# The producer templates that legitimately emit X-SSL-* toward the backend.
PRODUCER_GLOBS = ("*/confs/server-http/*.conf", "*/confs/http/*.conf", "*/confs/*.conf")


class _Blank(ChainableUndefined):
    """Any setting not supplied renders empty, and stays usable when chained.

    `http.conf` reads dozens of settings and none of them gates the strip; supplying a curated dict
    would quietly turn "unconditional" into "conditional on the values I happened to choose".
    Chainable because the template reaches through attributes (`x.all`) on values it expects to be
    objects -- a plain Undefined raises there and the render dies before reaching the strip.
    """

    def __iter__(self):
        return iter(())


def render(**settings) -> str:
    env = Environment(  # same knobs as Templator._build_environment
        loader=FileSystemLoader(str(CONFS)),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
        undefined=_Blank,
    )
    # `all` is not a setting -- Templator passes the whole config dict under that name and the
    # template iterates it (`{% for k, v in all.items() %}`), so an Undefined there kills the render
    # before it reaches the strip.
    # Templator injects seven callables; `http.conf` uses exactly one of them, and none of them
    # gates the strip. Measured rather than assumed -- and notably `import(` is absent, so this
    # template never reaches the render host's filesystem.
    env.globals["normalize_memory_size"] = lambda value: str(value)
    return env.get_template("http.conf").render({"all": dict(settings), **settings})


def directives(text: str) -> list:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {"USE_MTLS": "no"},
        {"USE_MTLS": "yes"},
        {"MTLS_FORWARD_CLIENT_HEADERS": "no"},
        # MULTISITE requires SERVER_NAME -- the template iterates it, and a multisite config
        # without one is not a configuration BunkerWeb would ever render.
        {"USE_MTLS": "no", "MULTISITE": "yes", "SERVER_NAME": "app.example.com"},
        {"USE_MODSECURITY": "no", "USE_REVERSE_PROXY": "yes"},
    ],
)
def test_the_strip_is_emitted_whatever_the_configuration(settings):
    """`USE_MTLS=no` is the case that matters: the strip is not part of the mTLS feature."""
    assert STRIP in directives(render(**settings)), f"the X-SSL ingress strip vanished for {settings}"


def test_the_strip_is_not_nested_inside_a_conditional_block():
    """A strip inside a `server {}` or `if {}` would apply to some requests only.

    Checked by brace depth rather than by eye: it must sit at the top level of `http.conf`, which
    nginx includes at `http` scope, so it applies to every server and every request.
    """
    depth = 0
    for line in render().splitlines():
        stripped = line.strip()
        if STRIP in stripped:
            assert depth == 0, f"the strip is nested {depth} block(s) deep, so it is conditional"
            return
        if not stripped.startswith("#"):
            depth += stripped.count("{") - stripped.count("}")
    pytest.fail("the strip was never emitted at all")


def _producer_lines():
    seen = []
    for glob in PRODUCER_GLOBS:
        for path in CORE.glob(glob):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"set_header\s+X-SSL-", line, re.I):
                    seen.append((path.relative_to(ROOT), number, line.strip()))
    return seen


def test_there_are_producers_to_check():
    """RULE 13: the scan below is a floor, not an exact count.

    With no producers found -- a renamed directory, a changed glob -- every case in the next test
    passes over an empty list and reports success. `>=` because a new integration emitting these
    headers is a normal thing to add.
    """
    found = _producer_lines()
    assert len(found) >= 14, f"only {len(found)} X-SSL producer lines found; the glob is probably wrong"


def test_no_producer_reads_the_incoming_request_header():
    """Every value forwarded must come from the handshake, never from what the client sent.

    `$http_x_ssl_client_verify` is exactly the forged value the strip removed. A producer reading it
    would re-publish it to the backend and defeat the strip without touching it.
    """
    offenders = [(path, number, line) for path, number, line in _producer_lines() if "$http_x_ssl" in line.lower()]
    assert not offenders, f"a producer re-publishes a client-supplied header: {offenders}"
