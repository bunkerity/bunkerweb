"""A directive whose only argument renders empty must not be emitted at all.

Five settings accept an empty value at validation -- ``GZIP_PROXIED``, ``PROXY_NO_CACHE`` and
``PROXY_CACHE_BYPASS`` are ``^.*$``, ``REAL_IP_HEADER``'s repetition group matches zero times, and
``SERVER_NAME`` is only ``.strip()``ed -- so clearing the field in the UI is a *supported* input.
Each one is then interpolated as the sole argument of an NGINX directive, and NGINX rejects a
directive with no arguments at ``[emerg]``: the instance does not come up. Measured against the
real nginx in ``bunkerweb-aio``, control included, in
``.cache/results-2026-08-20/flua10-empty-directive-evidence.txt``::

    gzip_proxied  EMPTY     invalid number of arguments in "gzip_proxied" directive
    gzip_proxied  with-arg  the configuration file syntax is ok

The failure is not degraded output, it is a service that will not start, triggered by a value the
UI accepts. ``PROXY_CACHE_VALID`` two lines below ``proxy_no_cache`` was already guarded this way,
which is what makes the omission a slip rather than a design choice.

``sibling`` in each case is the anti-vacuity guard: it asserts the surrounding block rendered at
all, so a template that stops emitting *everything* cannot pass as "the directive is absent".
"""

from concurrent.futures import Future
from importlib import import_module
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

GZIP = {"USE_GZIP": "yes", "GZIP_TYPES": "text/html", "GZIP_COMP_LEVEL": "5", "GZIP_MIN_LENGTH": "1000"}
REALIP = {"USE_REAL_IP": "yes", "MULTISITE": "no", "SERVER_NAME": "www.example.com", "REAL_IP_FROM": "", "REAL_IP_RECURSIVE": "no"}
PROXY = {
    "USE_REVERSE_PROXY": "yes",
    "SERVER_NAME": "www.example.com",
    "REVERSE_PROXY_CUSTOM_HOST": "",
    "USE_MODSECURITY": "no",
    "USE_MTLS": "no",
    "USE_UI": "no",
    "USE_PROXY_CACHE": "yes",
    "PROXY_CACHE_METHODS": "GET HEAD",
    "PROXY_CACHE_MIN_USES": "2",
    "PROXY_CACHE_KEY": "$scheme$host$request_uri",
    "PROXY_CACHE_VALID": "",
    "all": {"REVERSE_PROXY_HOST": "http://backend:8080", "REVERSE_PROXY_URL": "/"},
}

# (template, setting, directive, a value NGINX accepts, base vars, a sibling directive that proves the block rendered)
CASES = [
    ("gzip/confs/server-http/gzip.conf", "GZIP_PROXIED", "gzip_proxied", "no-cache", GZIP, "gzip on;"),
    ("realip/confs/server-http/real-ip.conf", "REAL_IP_HEADER", "real_ip_header", "X-Forwarded-For", REALIP, "real_ip_recursive"),
    ("realip/confs/default-server-http/real-ip.conf", "REAL_IP_HEADER", "real_ip_header", "X-Forwarded-For", REALIP, "real_ip_recursive"),
    ("reverseproxy/confs/server-http/reverse-proxy.conf", "PROXY_NO_CACHE", "proxy_no_cache", "$http_pragma", PROXY, "proxy_cache_key"),
    ("reverseproxy/confs/server-http/reverse-proxy.conf", "PROXY_CACHE_BYPASS", "proxy_cache_bypass", "0", PROXY, "proxy_cache_key"),
]
IDS = [f"{setting}" if "default-server" not in t else f"{setting}-default-server" for t, setting, *_ in CASES]


def _render(template: str, base: dict, **overrides) -> str:
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module  # Templator exposes this; real-ip.conf uses it for pathlib
    return environment.from_string((CORE / template).read_text(encoding="utf-8")).render(**dict(base, **overrides))


def _directives(rendered: str, name: str) -> list:
    return [line for line in rendered.splitlines() if line.strip().split(" ")[0].rstrip(";") == name]


def test_every_guarded_directive_is_still_covered():
    """RULE 13 floor. A parametrized guard does not fail when its source list empties -- it reports
    SKIPPED, and `5 passed, 2 skipped` reads as green. This is `>=`, not `==`: the class is "a
    directive whose only argument can render empty", and another lane finding a sixth should widen
    this list without going red. Removing one is the regression.
    """
    assert len(CASES) >= 5, f"CASES has {len(CASES)} entries; F-LUA-10 guards five directives"
    assert len(IDS) == len(CASES), "ids and cases drifted apart; pytest would mislabel every case"


@pytest.mark.parametrize(("template", "setting", "directive", "value", "base", "sibling"), CASES, ids=IDS)
def test_an_empty_value_emits_no_directive(template, setting, directive, value, base, sibling):
    rendered = _render(template, base, **{setting: ""})

    assert sibling in rendered, "the block did not render at all -- this case proves nothing"
    assert _directives(rendered, directive) == []


@pytest.mark.parametrize(("template", "setting", "directive", "value", "base", "sibling"), CASES, ids=IDS)
def test_a_setting_that_is_absent_entirely_emits_no_directive(template, setting, directive, value, base, sibling):
    """RULE 14a case for the deviation from dev's port.

    dev guards with ``{% if X != "" %}``, which covers a CLEARED setting but not an ABSENT one: an
    undefined name is not equal to ``""``, so the guard passes and the template emits the very
    ``directive ;`` the row exists to prevent. Measured against the production undefined class,
    ``ConfigurableCustomUndefined``, not just the test harness::

        != "" guard, setting ABSENT  -> 'gzip_proxied ;'
        truthy guard, setting ABSENT -> ''

    The truthy form covers both and loses nothing -- config values are strings, so ``"0"`` stays
    truthy, which matters because ``PROXY_CACHE_BYPASS`` defaults to exactly that.
    """
    rendered = _render(template, {k: v for k, v in base.items() if k != setting})

    assert sibling in rendered, "the block did not render at all -- this case proves nothing"
    assert _directives(rendered, directive) == []


@pytest.mark.parametrize(("template", "setting", "directive", "value", "base", "sibling"), CASES, ids=IDS)
def test_a_real_value_still_emits_the_directive(template, setting, directive, value, base, sibling):
    """The control. Guarding the directive must not silently drop it for everyone."""
    rendered = _render(template, base, **{setting: value})

    assert _directives(rendered, directive) == [f"{directive} {value};"]


class _InlinePool:
    """Runs submitted work in-process; ``render()`` otherwise forks and the assertion never sees it."""

    def __init__(self, max_workers=None):
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def submit(self, fn, *args):
        future = Future()
        future.set_result(fn(*args))
        return future


@pytest.mark.parametrize(
    ("server_name", "multisite", "expected"),
    [
        ("", "no", []),
        ("   ", "no", []),
        ("www.example.com", "no", ["www.example.com"]),
        ("", "yes", []),
        ("a.example.com b.example.com", "yes", ["a.example.com", "b.example.com"]),
    ],
)
def test_an_empty_server_name_renders_no_server_at_all(monkeypatch, server_name, multisite, expected):
    """Singlesite used to wrap the raw value in a list unconditionally, so an empty ``SERVER_NAME``
    rendered one server whose ``server_name`` directive had no argument. Multisite already got this
    right for free -- ``"".split()`` is ``[]`` -- which is why only the singlesite branch was wrong.
    """
    templator = import_module("Templator")
    batches = []

    monkeypatch.setattr(templator, "_ensure_fork_start_method", lambda: None)
    monkeypatch.setattr(templator, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(templator, "effective_cpu_count", lambda: 4)

    # __new__, not __init__: the constructor mkdirs /var/cache/bunkerweb, which is root-owned here.
    instance = templator.Templator.__new__(templator.Templator)
    instance._config = {"SERVER_NAME": server_name, "MULTISITE": multisite}
    monkeypatch.setattr(instance, "_uses_auto_ssl_ecdh_curve", lambda: False)
    monkeypatch.setattr(instance, "_render_global", lambda: None)
    monkeypatch.setattr(instance, "_render_server_batch", batches.extend)

    instance.render()

    assert batches == expected
