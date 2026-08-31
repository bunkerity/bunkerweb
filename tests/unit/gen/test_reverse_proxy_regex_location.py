"""An anchored path must render as a regex location, in all three templates that emit one.

Without this, ``REVERSE_PROXY_URL=^/api/v[0-9]+`` renders ``location ^/api/v[0-9]+ {`` — a
*prefix* location whose URI happens to start with ``^``. NGINX accepts the config and the
location never matches, so the failure is silent: the request falls through to whatever else
claims ``/``.

The guard on the modifier is not cosmetic. ``~* \\.php$`` and ``^~ /static`` are already valid
today; prefixing ``~`` onto them yields ``location ~ ~* \\.php$`` and ``location ~ ^~ /static``,
which NGINX refuses outright — the service does not come up. That is why the two upstream
commits (``bdb3a34ad`` then ``b236eda5d``) only make sense together.

``reverseproxy``, ``grpc``, ``redirect`` and ``php`` all render a ``location`` into the same
server block and share one path namespace (``src/common/utils/location_claims.py`` at render time,
``db_methods/locations.py`` at mutation time). Making the ``~`` *implicit* means two different
stored values can render the same ``location``, so both guards claim what NGINX receives rather
than what was typed — and all three templates have to follow the same rule, or a guard refuses a
pair NGINX would accept. ``test_every_template_agrees_with_the_claim_helper`` is what ties the
three templates to the two guards; without it, dropping the rule from one template is invisible
here.
"""

from importlib import import_module
from pathlib import Path
from re import search

import pytest

jinja2 = pytest.importorskip("jinja2")

from location_claims import claimed_paths, rendered_location  # type: ignore  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "src" / "common" / "core" / "reverseproxy" / "confs" / "server-http" / "reverse-proxy.conf"

# (REVERSE_PROXY_URL, the location line NGINX must receive, may X-Forwarded-Prefix be sent?)
URLS = [
    ("/", "location / {", True),
    ("/api/", "location /api/ {", True),
    ("^/api/v[0-9]+", "location ~ ^/api/v[0-9]+ {", False),
    ("/health$", "location ~ /health$ {", False),
    ("^/api/v[0-9]+$", "location ~ ^/api/v[0-9]+$ {", False),
    ("~ ^/api", "location ~ ^/api {", False),
    ("~* \\.php$", "location ~* \\.php$ {", False),
    ("= /exact", "location = /exact {", False),
    ("^~ /static", "location ^~ /static {", False),
]


# RULE 13 floors. Both lists drive @parametrize, so emptying either reports success, not failure:
# measured, URLS = [] gives "4 passed, 6 skipped" and FAMILIES = [] gives "31 passed, 9 skipped".
# Zero failures, a clean bill of health for nothing.
#
# `>=` on both, because both grow by collaboration: URLS grows when someone covers another value
# shape, FAMILIES when another plugin starts rendering a `location`. Neither growth is a defect.
MINIMUM_URLS = 9
MINIMUM_FAMILIES = 3


def test_the_source_lists_have_not_emptied_out():
    assert len(URLS) >= MINIMUM_URLS
    assert len(FAMILIES) >= MINIMUM_FAMILIES


def test_every_template_that_renders_a_location_is_covered():
    """FAMILIES must not silently fall behind the templates that emit a `location`.

    ⚠️ `antibot.conf` renders `location {{ ANTIBOT_URI }}` and is deliberately NOT here: it is also
    absent from `location_claims.LOCATION_FAMILIES`, so an anti-bot URI is not claimed against the
    others and an anchored value there is still a dead prefix location. That is a live gap,
    reported separately -- not something this test should paper over by growing to four.
    """
    # Match the emitted directive, not one spelling of it. Searching for the literal `location {{`
    # was my first version and it found ONLY antibot.conf -- because cluster D rewrote the other
    # three to `location {% if ... %}~ {% endif %}{{ url }}`. A detector that the change under test
    # invalidates is worse than no detector.
    emitting = {
        path.name
        for path in (ROOT / "src" / "common" / "core").glob("*/confs/server-http/*.conf")
        if search(r"(?m)^\s*location\s", path.read_text(encoding="utf-8"))
    }

    # Eight, not three. Only the first three carry a user-settable path AND are claimed against
    # each other in location_claims.LOCATION_FAMILIES; the rest share the same `location` namespace
    # without participating in it:
    #
    #   antibot.conf     `location {{ ANTIBOT_URI }}`      user-settable, NOT claimed
    #   errors.conf      `location = {{ page }}`           user-settable, NOT claimed
    #   securitytxt.conf `location = {{ SECURITYTXT_URI }}` user-settable, NOT claimed -- but it
    #                    self-guards its own second literal at :36, which is the shape the others lack
    #   lets-encrypt.conf                                  fixed literal, NOT claimed
    #   php.conf                                           fixed literal, CLAIMED since the
    #                    registry learned to carry a family with no path setting
    #
    # php.conf renders an unconditional `location / {` whenever REMOTE_PHP or LOCAL_PHP is set,
    # which collides with the DEFAULT `REVERSE_PROXY_URL=/`. It IS a claim family now
    # (`location_claims.LOCATION_FAMILIES["PHP"]`), so it is absent from FAMILIES below only
    # because that list parametrizes path VALUES and php has no path setting to vary --
    # `tests/unit/common/test_location_claims.py` is where its claim and its render are pinned.
    assert emitting == {
        "reverse-proxy.conf",
        "grpc.conf",
        "redirect.conf",
        "antibot.conf",
        "errors.conf",
        "lets-encrypt.conf",
        "php.conf",
        "securitytxt.conf",
    }, (
        f"a template started or stopped rendering a location: {sorted(emitting)} -- "
        "if it carries a user-settable path, it belongs in FAMILIES and in location_claims.LOCATION_FAMILIES"
    )


def _render(**overrides) -> str:
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module  # Templator exposes this; the mTLS block uses it
    variables = {
        "USE_REVERSE_PROXY": "yes",
        "SERVER_NAME": "www.example.com",
        "REVERSE_PROXY_CUSTOM_HOST": "",
        "USE_MODSECURITY": "no",
        "USE_MTLS": "no",
        "USE_PROXY_CACHE": "no",
        "USE_UI": "no",
    }
    variables.update(overrides)
    return environment.from_string(TEMPLATE.read_text(encoding="utf-8")).render(**variables)


def _render_url(url: str) -> str:
    return _render(all={"REVERSE_PROXY_HOST": "http://backend:8080", "REVERSE_PROXY_URL": url})


# (template, the setting holding the path, the trigger that makes the location render)
FAMILIES = [
    ("reverseproxy/confs/server-http/reverse-proxy.conf", "REVERSE_PROXY_URL", {"REVERSE_PROXY_HOST": "http://backend:8080"}),
    ("grpc/confs/server-http/grpc.conf", "GRPC_URL", {"GRPC_HOST": "grpc://backend:9000"}),
    ("redirect/confs/server-http/redirect.conf", "REDIRECT_FROM", {"REDIRECT_TO": "https://elsewhere.example.com"}),
]


def _render_family(template: str, path_setting: str, trigger: dict, value: str) -> list:
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module
    rendered = environment.from_string((ROOT / "src" / "common" / "core" / template).read_text(encoding="utf-8")).render(
        USE_REVERSE_PROXY="yes",
        USE_GRPC="yes",
        SERVER_NAME="www.example.com",
        REVERSE_PROXY_CUSTOM_HOST="",
        GRPC_CUSTOM_HOST="",
        GRPC_SSL_SNI="no",
        USE_MODSECURITY="no",
        USE_MTLS="no",
        USE_PROXY_CACHE="no",
        USE_UI="no",
        all=dict(trigger, **{path_setting: value}),
    )
    return [line for line in rendered.splitlines() if line.startswith("location ")]


@pytest.mark.parametrize(("url", "expected", "_prefix_ok"), URLS)
def test_the_location_modifier_matches_what_the_value_means(url, expected, _prefix_ok):
    locations = [line for line in _render_url(url).splitlines() if line.startswith("location ")]

    assert locations == [expected]


@pytest.mark.parametrize(("url", "_expected", "prefix_ok"), URLS)
def test_x_forwarded_prefix_is_only_sent_for_a_real_prefix(url, _expected, prefix_ok):
    # A regex is not a prefix. Sending "/health$" as X-Forwarded-Prefix hands the backend a
    # path that does not exist, which is worse than sending nothing.
    sent = any("X-Forwarded-Prefix" in line for line in _render_url(url).splitlines())

    assert sent is prefix_ok


def test_an_explicit_modifier_is_never_double_prefixed():
    """The control for the guard: this is the state ``bdb3a34ad`` alone would have shipped."""
    for url in ("~ ^/api", "~* \\.php$", "= /exact", "^~ /static"):
        rendered = _render_url(url)

        assert f"location ~ {url} {{" not in rendered, f"{url!r} got a second modifier"


def test_the_template_still_reads_the_url_from_the_suffixed_setting():
    # Guards the parametrization above from passing vacuously if the loop ever stops binding url.
    locations = [
        line
        for line in _render(
            all={
                "REVERSE_PROXY_HOST": "http://a:80",
                "REVERSE_PROXY_URL": "/first",
                "REVERSE_PROXY_HOST_2": "http://b:80",
                "REVERSE_PROXY_URL_2": "^/second",
            }
        ).splitlines()
        if line.startswith("location ")
    ]

    assert locations == ["location /first {", "location ~ ^/second {"]


@pytest.mark.parametrize(("url", "expected", "_prefix_ok"), URLS)
def test_the_claim_key_is_the_location_nginx_receives(url, expected, _prefix_ok):
    """What a service claims must be what NGINX sees, or the conflict check misses a duplicate."""
    assert rendered_location("REVERSE_PROXY_URL", url) == expected[len("location ") : -len(" {")]  # noqa: E203


def test_two_spellings_of_one_regex_location_are_a_single_claim():
    # An attached upstream serving "~ ^/api" and an inline rule spelling it "^/api" now render
    # the same location; NGINX refuses the pair with "duplicate location".
    config = {
        "REVERSE_PROXY_HOST": "http://a:80",
        "REVERSE_PROXY_URL": "^/api",
        "REVERSE_PROXY_HOST_2": "http://b:80",
        "REVERSE_PROXY_URL_2": "~ ^/api",
    }

    assert claimed_paths(config, [""]) == {"~ ^/api": "reverse proxy"}


def test_the_helper_treats_all_three_families_alike():
    # It deliberately has NO per-family branch: reverse-proxy.conf, grpc.conf and redirect.conf
    # all render an anchored path as a regex location, so a value means the same thing in each.
    # A branch here is what produced the false refusal the mutation guard shipped with.
    for setting in ("REVERSE_PROXY_URL", "GRPC_URL", "REDIRECT_FROM"):
        assert rendered_location(setting, "^/api") == "~ ^/api"
        assert rendered_location(setting, "/health$") == "~ /health$"
        assert rendered_location(setting, "/api") == "/api"
        assert rendered_location(setting, "~* \\.php$") == "~* \\.php$"


@pytest.mark.parametrize(("template", "path_setting", "trigger"), FAMILIES)
@pytest.mark.parametrize("value", [url for url, _expected, _prefix in URLS])
def test_every_template_agrees_with_the_claim_helper(template, path_setting, trigger, value):
    """The three templates and the two guards must derive the same ``location`` from one value.

    This is the tie that a guard-to-guard test cannot make: with both guards normalizing, a
    template that quietly drops the rule renders a *prefix* location while the guards keep
    claiming a regex one, and the guards then refuse a pair NGINX accepts.
    """
    locations = _render_family(template, path_setting, trigger, value)

    assert locations == [f"location {rendered_location(path_setting, value)} {{"]
