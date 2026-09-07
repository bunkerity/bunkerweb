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
    ("/", 'location "/" {', True),
    ("/api/", 'location "/api/" {', True),
    ("^/api/v[0-9]+", 'location ~ "^/api/v[0-9]+" {', False),
    ("/health$", 'location ~ "/health$" {', False),
    ("^/api/v[0-9]+$", 'location ~ "^/api/v[0-9]+$" {', False),
    ("~ ^/api", 'location ~ "^/api" {', False),
    # The template escapes the backslash for NGINX: inside a quoted operand `\\` is one literal
    # backslash, so the regex NGINX compiles is still `\.php$`.
    ("~* \\.php$", 'location ~* "\\\\.php$" {', False),
    ("= /exact", 'location = "/exact" {', False),
    ("^~ /static", 'location ^~ "/static" {', False),
]


# RULE 13 floors. Both lists drive @parametrize, so emptying either reports success, not failure:
# measured, URLS = [] gives "4 passed, 6 skipped" and FAMILIES = [] gives "31 passed, 9 skipped".
# Zero failures, a clean bill of health for nothing.
#
# `>=` on both, because both grow by collaboration: URLS grows when someone covers another value
# shape, FAMILIES when another plugin starts rendering a `location`. Neither growth is a defect.
MINIMUM_URLS = 9
MINIMUM_FAMILIES = 3


# NGINX strips the quotes at tokenization, so `location "/"` and `location /` are the same URI and
# NGINX still refuses the pair. The templates quote the operand (port of dev 0af49ac8b) so a value
# carrying `"`, `#` or a backslash cannot end the directive early; the quotes are directive syntax,
# not part of the URI, which is why `rendered_location` keeps claiming the unquoted value.
def _claim_key(location_line: str) -> str:
    """The `rendered_location` claim key a rendered `location ... {` line corresponds to."""
    body = location_line[len("location ") : -len(" {")]  # noqa: E203
    if not body.endswith('"'):
        return body
    opening = body.index('"')
    modifier = body[:opening].strip()
    operand = body[opening + 1 : -1].replace('\\"', '"').replace("\\\\", "\\")  # noqa: E203
    return f"{modifier} {operand}" if modifier else operand


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


def _render_family_raw(template: str, config: dict) -> str:
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module
    return environment.from_string((ROOT / "src" / "common" / "core" / template).read_text(encoding="utf-8")).render(
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
        all=config,
    )


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

        assert f'location ~ "{url}" {{' not in rendered, f"{url!r} got a second modifier"


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

    assert locations == ['location "/first" {', 'location ~ "^/second" {']


@pytest.mark.parametrize(("url", "expected", "_prefix_ok"), URLS)
def test_the_claim_key_is_the_location_nginx_receives(url, expected, _prefix_ok):
    """What a service claims must be what NGINX sees, or the conflict check misses a duplicate."""
    assert rendered_location("REVERSE_PROXY_URL", url) == _claim_key(expected)


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

    assert [_claim_key(line) for line in locations] == [rendered_location(path_setting, value)]
    # _claim_key passes an UNQUOTED line straight through (php.conf renders one), so the claim
    # comparison above cannot tell a quoted emitter from an unquoted one. Without this line a
    # template that drops the quoting ships unpinned: only reverse-proxy.conf is covered by
    # test_the_operand_is_quoted_and_escaped, and grpc.conf and redirect.conf are rendered
    # nowhere else in the suite.
    assert all(line.endswith('" {') for line in locations), f"{template} stopped quoting its operand: {locations}"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # A bare `#` starts a comment and a bare `"` ends the operand: unquoted, either one
        # truncates the directive and NGINX either refuses the file or serves a location nobody
        # asked for. The value regex allows both (only whitespace, `;`, `{` and `}` are refused),
        # so quoting is what makes them safe.
        ('/a"b', 'location "/a\\"b" {'),
        ("/a#b", 'location "/a#b" {'),
        ("/a\\b", 'location "/a\\\\b" {'),
        ("~ ^/a#b", 'location ~ "^/a#b" {'),
    ],
)
def test_the_operand_is_quoted_and_escaped(url, expected):
    """Port of dev 0af49ac8b: the operand is quoted, and `"`/`\\` inside it are escaped."""
    locations = [line for line in _render_url(url).splitlines() if line.startswith("location ")]

    assert locations == [expected]
    # ...and the claim registry still claims the value itself, so the two guards keep agreeing.
    assert _claim_key(expected) == rendered_location("REVERSE_PROXY_URL", url)


MODIFIERS = ("~", "~*", "=", "^~")


def _expected_location(value: str) -> str:
    """The `location` line the three templates must all render for `value`.

    Derived from the rule rather than copied from a template, so it cannot drift with the thing
    it checks: explicit modifier wins, an anchored path is implicitly `~`, the operand is quoted
    and its backslashes and quotes escaped for NGINX's own string syntax.
    """
    # The rule stated in words, not the template's expression: ANY whitespace run separates the
    # modifier from the operand, and the operand is then whatever is left, VERBATIM. Deliberately
    # not `rendered_location`'s rule -- that one collapses every whitespace run, including inside
    # the operand, which is a claim-side normalisation and not what NGINX receives.
    parts = value.split(None, 1)
    head = parts[0] if parts else ""
    if head in MODIFIERS:
        modifier, operand = head, (parts[1] if len(parts) > 1 else "")
    else:
        modifier = "~" if value.startswith("^") or value.endswith("$") else ""
        operand = value
    quoted = operand.replace("\\", "\\\\").replace('"', '\\"')
    return f'location {modifier} "{quoted}" {{' if modifier else f'location "{quoted}" {{'


@pytest.mark.parametrize(("template", "path_setting", "trigger"), FAMILIES)
# "~  ^/api" and "~\t^/a" are the whitespace-divergence cases: `rendered_location` splits on ANY
# whitespace and collapses the separator, so the template has to do the same or the two mirrors
# claim different locations for one value (Criticos round 2).
@pytest.mark.parametrize("url", ['/a"b', "/a#b", "/a\\b", "~ ^/a#b", "^/api", "/", "~  ^/api", "~\t^/a"])
def test_all_three_templates_quote_and_escape_alike(template, path_setting, trigger, url):
    """The same escaping in every emitter: one template left unquoted is one injection site left.

    `test_the_operand_is_quoted_and_escaped` covers reverse-proxy.conf only, and `_claim_key`
    passes an unquoted line straight through, so without this grpc.conf and redirect.conf could
    drop the quoting with the whole suite still green.
    """
    locations = _render_family(template, path_setting, trigger, url)

    assert locations == [_expected_location(url)]
    assert _claim_key(locations[0]) == rendered_location(path_setting, url)


@pytest.mark.parametrize(("template", "path_setting", "trigger"), FAMILIES)
@pytest.mark.parametrize("url", ["", "~", "~*", "=", "^~"])
def test_an_empty_operand_renders_no_location_at_all(template, path_setting, trigger, url):
    """Quoting turned a loud `[emerg]` into a silent catch-all, so the render has to refuse it.

    Before the operand was quoted, an empty value rendered ``location  {`` and NGINX refused the
    whole configuration with *invalid number of arguments*. Quoted, ``location "" {`` is a valid
    PREFIX location matching every URI, which on these three templates means proxying (or
    redirecting) the entire service. The plugin.json regex refuses these values, but it is a
    write-time guard: a stored setting is never re-validated at render and ``IGNORE_REGEX_CHECK``
    turns it off wholesale, so the render must not fail open on its own.
    """
    assert _render_family(template, path_setting, trigger, url) == []


@pytest.mark.parametrize(("template", "path_setting", "trigger"), FAMILIES)
@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("", "/second", ['location "/second" {']),
        ("/first", "", ['location "/first" {']),
        ("/first", "^/second", ['location "/first" {', 'location ~ "^/second" {']),
        ("", "", []),
    ],
)
def test_one_empty_rule_does_not_swallow_its_siblings(template, path_setting, trigger, first, second, expected):
    """The empty-operand guard wraps a long block; a misplaced `{% endif %}` would eat the loop.

    Skipping the rule with no path must skip exactly that rule: the other suffixed rules on the
    same service still render, and the braces still balance (an unbalanced block is an `[emerg]`
    that no location-level assertion would notice).
    """
    trigger_setting, trigger_value = next(iter(trigger.items()))
    config = {
        trigger_setting: trigger_value,
        path_setting: first,
        f"{trigger_setting}_2": trigger_value,
        f"{path_setting}_2": second,
    }
    rendered = _render_family_raw(template, config)

    assert [line for line in rendered.splitlines() if line.startswith("location ")] == expected
    assert rendered.count("{") == rendered.count("}") == len(expected), "the location block's braces no longer balance"


@pytest.mark.parametrize(("template", "path_setting", "trigger"), FAMILIES)
@pytest.mark.parametrize(("url", "operand"), [("~ ^/a  b", "^/a  b"), ("~\t^/a\tb", "^/a\tb"), ("~  ^/a b", "^/a b")])
def test_only_the_modifier_separator_is_collapsed(template, path_setting, trigger, url, operand):
    """The operand is whatever follows the modifier, VERBATIM -- `split(None, 1)`, not `split()`.

    Splitting the whole value and taking `parts[1]` looks identical on every value with at most
    two whitespace-separated tokens, which is every value the rest of this module feeds a
    template. It silently truncates the operand at its first inner whitespace otherwise: measured,
    `~ ^/a  b` rendered `location ~ "^/a" {`, dropping user data with no error anywhere. That
    mutation survived the entire suite before this test existed (Criticos round 3, item 3).

    The claim key is NOT asserted here, unlike `test_all_three_templates_quote_and_escape_alike`.
    `location_claims.rendered_location()` collapses EVERY whitespace run, so for these values it
    answers the collapsed form while NGINX receives the verbatim one -- a known, deliberately
    unfixed divergence recorded as a PO note (`location_claims.py` is the mutation-time guard's
    mirror too, shared with `db_methods/locations.py` and pinned by `tests/unit/db/test_redirects.py`).
    It is false-refusal-only, and the operand regex refuses the whole class at write time.
    """
    assert _render_family(template, path_setting, trigger, url) == [f'location ~ "{operand}" {{']
