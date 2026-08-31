"""The location namespace has to be able to *count* claims, and php has to be in it.

Three gaps let ``duplicate location "/"`` — an ``[emerg]`` NGINX answers by refusing the whole
reload — reach the instances from a configuration the save path had just accepted:

1. ``php.conf:2`` renders an unconditional ``location /`` whenever ``REMOTE_PHP`` or
   ``LOCAL_PHP`` is set, and ``php`` was never in ``LOCATION_FAMILIES`` — invisible to every
   conflict check in the codebase.
2. ``save_config`` compared the incoming settings only against *attached resources*, so two
   inline families in one save (the shape Autoconf and the Kubernetes controller push) never met
   each other.
3. ``claimed_paths`` used ``setdefault``: the first claim on a path won and every later one was
   dropped, so it could never see a second claim — same family or not.

The render half of this file is what keeps the registry honest: the pairs the guard refuses are
rendered from the real templates and asserted to produce the same ``location`` line twice. A
registry test that only talks to the registry proves the registry agrees with itself.
"""

from importlib import import_module
from pathlib import Path

import pytest

from location_claims import (  # type: ignore
    FAMILY_SWITCHES,
    FIXED_LOCATION,
    LOCATION_FAMILIES,
    LOCATION_TRIGGERS,
    claim_counts,
    claimed_paths,
    family_enabled,
    inline_family_conflict,
    inline_location_conflict,
)

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

SERVER = "www.example.com"
PREFIXES = ["", f"{SERVER}_"]


def cfg(**settings):
    """A multisite config for one server, keys prefixed the way Templator sees them."""
    return {"MULTISITE": "yes", "SERVER_NAME": SERVER, **{f"{SERVER}_{key}": value for key, value in settings.items()}}


# ---------------------------------------------------------------------------------------------
# Gap 1 — php is a claim family
# ---------------------------------------------------------------------------------------------


def test_php_is_registered_with_both_triggers_and_no_path_setting():
    assert LOCATION_FAMILIES["PHP"] == (("REMOTE_PHP", "LOCAL_PHP"), None)
    assert "REMOTE_PHP" in LOCATION_TRIGGERS and "LOCAL_PHP" in LOCATION_TRIGGERS


@pytest.mark.parametrize("trigger", ["REMOTE_PHP", "LOCAL_PHP"])
def test_either_php_trigger_claims_the_hardcoded_location(trigger):
    """php.conf renders for REMOTE_PHP *or* LOCAL_PHP, and its path is not configurable."""
    assert claimed_paths(cfg(**{trigger: "php-fpm"}), PREFIXES) == {FIXED_LOCATION: "PHP"}


def test_both_php_triggers_together_are_still_one_claim():
    """One `location /` renders whether one trigger is set or both — so one claim, not two.

    Scanning the two triggers as a single pass instead of unioning them is what makes this fail
    both ways: an empty REMOTE_PHP would pop the claim LOCAL_PHP made, and setting both would
    count twice and refuse a configuration NGINX accepts.
    """
    assert claim_counts(cfg(REMOTE_PHP="php-fpm", LOCAL_PHP="/run/php/php-fpm.sock"), PREFIXES) == {FIXED_LOCATION: ["PHP"]}
    assert claim_counts(cfg(REMOTE_PHP="", LOCAL_PHP="/run/php/php-fpm.sock"), PREFIXES) == {FIXED_LOCATION: ["PHP"]}
    assert claim_counts(cfg(REMOTE_PHP="php-fpm", LOCAL_PHP=""), PREFIXES) == {FIXED_LOCATION: ["PHP"]}


def test_a_service_that_blanks_the_inherited_php_setting_frees_the_path():
    """The template loops on the value, so a server-specific blank must free the claim."""
    config = {"MULTISITE": "yes", "SERVER_NAME": SERVER, "REMOTE_PHP": "php-fpm", f"{SERVER}_REMOTE_PHP": ""}
    assert claim_counts(config, PREFIXES) == {}


def test_php_is_claimed_against_an_attached_resource_too():
    """The gap was in the registry, so closing it covers the attached-resource guard for free."""
    error = inline_location_conflict(cfg(REMOTE_PHP="php-fpm"), SERVER, PREFIXES, ["/"])
    assert "already serves / through an attached resource" in error
    assert "PHP" in error


# ---------------------------------------------------------------------------------------------
# Gaps 2 and 3 — the incoming config can collide with itself
# ---------------------------------------------------------------------------------------------


def test_two_inline_families_on_the_default_path_are_refused():
    error = inline_family_conflict(cfg(REVERSE_PROXY_HOST="http://backend:8080", REDIRECT_TO="https://elsewhere.example.com"), SERVER, PREFIXES)
    assert "reverse proxy" in error and "redirect" in error and f"{SERVER} would serve / " in error


def test_php_next_to_a_reverse_proxy_is_refused():
    error = inline_family_conflict(cfg(REVERSE_PROXY_HOST="http://backend:8080", REMOTE_PHP="php-fpm"), SERVER, PREFIXES)
    assert "reverse proxy" in error and "PHP" in error


def test_two_suffixes_of_one_family_with_no_path_of_their_own_are_refused():
    """The same defect inside one family: both suffixes fall back to REVERSE_PROXY_URL's "/"."""
    error = inline_family_conflict(cfg(REVERSE_PROXY_HOST_1="http://a:8080", REVERSE_PROXY_HOST_2="http://b:8080"), SERVER, PREFIXES)
    assert "twice through its reverse proxy settings" in error


def test_distinct_paths_are_not_refused():
    """The false-refusal direction: a guard that refuses what NGINX accepts is worse than none."""
    config = cfg(
        REVERSE_PROXY_HOST="http://backend:8080",
        REVERSE_PROXY_URL="/app",
        REDIRECT_TO="https://elsewhere.example.com",
        REDIRECT_FROM="/legacy",
        GRPC_HOST="grpc://backend:9000",
        GRPC_URL="/grpc",
    )
    assert inline_family_conflict(config, SERVER, PREFIXES) == ""


def test_two_spellings_of_one_regex_location_are_one_claim_and_are_refused():
    """`^/api` and `~ ^/api` both render `location ~ ^/api`, so they collide.

    This is the trap the two mirrors exist for: comparing the stored value instead of the
    rendered one makes this pair pass, and normalizing only one mirror makes a legal pair fail.
    """
    config = cfg(
        REVERSE_PROXY_HOST="http://backend:8080",
        REVERSE_PROXY_URL="^/api",
        REDIRECT_TO="https://elsewhere.example.com",
        REDIRECT_FROM="~ ^/api",
    )
    assert claim_counts(config, PREFIXES) == {"~ ^/api": ["reverse proxy", "redirect"]}
    assert "~ ^/api" in inline_family_conflict(config, SERVER, PREFIXES)


def test_a_blanked_out_rule_frees_its_path_instead_of_colliding():
    """A cleared trigger renders nothing, so it must not be counted as a second claim."""
    config = cfg(REVERSE_PROXY_HOST="http://backend:8080", REDIRECT_TO="")
    assert inline_family_conflict(config, SERVER, PREFIXES) == ""


def test_claimed_paths_still_reports_the_first_claim_only():
    """`claimed_paths` keeps its old contract — three resolvers and the UI read it that way."""
    config = cfg(REVERSE_PROXY_HOST="http://backend:8080", REDIRECT_TO="https://elsewhere.example.com", REMOTE_PHP="php-fpm")
    assert claimed_paths(config, PREFIXES) == {"/": "reverse proxy"}
    assert claim_counts(config, PREFIXES) == {"/": ["reverse proxy", "redirect", "PHP"]}


# ---------------------------------------------------------------------------------------------
# The enable switches — a family that renders nothing cannot claim anything
# ---------------------------------------------------------------------------------------------


def test_only_the_two_switched_families_are_registered():
    """`redirect.conf` has no switch and `php.conf`'s switch *is* its triggers."""
    assert FAMILY_SWITCHES == {"reverse proxy": "USE_REVERSE_PROXY", "gRPC": "USE_GRPC"}
    assert set(FAMILY_SWITCHES) <= set(LOCATION_FAMILIES)


def test_a_dormant_grpc_host_does_not_refuse_a_real_reverse_proxy():
    """The false refusal that would have frozen every save: `grpc.conf:1` renders nothing.

    `routers/services.py` and `routers/global_settings.py` send the FULL config snapshot and
    `config_save` returns on the first hit, so one service left carrying a `GRPC_HOST` from a
    gRPC backend that was switched off would have refused every save, fleet-wide.
    """
    config = cfg(
        USE_REVERSE_PROXY="yes",
        REVERSE_PROXY_HOST="http://backend:8080",
        USE_GRPC="no",
        GRPC_HOST="grpc://backend:9000",
    )
    assert inline_family_conflict(config, SERVER, PREFIXES) == ""


def test_a_dormant_reverse_proxy_host_does_not_refuse_php():
    config = cfg(USE_REVERSE_PROXY="no", REVERSE_PROXY_HOST="http://backend:8080", REMOTE_PHP="php-fpm")
    assert inline_family_conflict(config, SERVER, PREFIXES) == ""


def test_the_switches_on_the_same_path_are_still_refused():
    """The gate must not become a way to smuggle a real duplicate past the guard."""
    config = cfg(
        USE_REVERSE_PROXY="yes",
        REVERSE_PROXY_HOST="http://backend:8080",
        USE_GRPC="yes",
        GRPC_HOST="grpc://backend:9000",
    )
    error = inline_family_conflict(config, SERVER, PREFIXES)
    assert "reverse proxy" in error and "gRPC" in error


def test_an_absent_switch_stays_enabled():
    """A partial save carries only what changed, so absence proves nothing — only `no` does.

    Every refusal test above relies on this: none of them sets a switch.
    """
    assert family_enabled(cfg(REVERSE_PROXY_HOST="http://backend:8080"), PREFIXES, "reverse proxy")
    assert family_enabled({}, PREFIXES, "redirect") and family_enabled({}, PREFIXES, "PHP")


@pytest.mark.parametrize(
    ("settings", "enabled"),
    [
        ({"USE_REVERSE_PROXY": "no"}, False),
        ({"USE_REVERSE_PROXY": " yes "}, True),
        ({"USE_REVERSE_PROXY": ""}, False),
    ],
)
def test_the_switch_is_read_the_way_the_template_reads_it(settings, enabled):
    assert family_enabled(cfg(**settings), PREFIXES, "reverse proxy") is enabled


def test_a_service_specific_switch_overrides_the_global_one():
    """Least specific first, the same merge `_trigger_occupancy` applies — both directions."""
    off_globally = {"MULTISITE": "yes", "SERVER_NAME": SERVER, "USE_GRPC": "no", f"{SERVER}_USE_GRPC": "yes"}
    on_globally = {"MULTISITE": "yes", "SERVER_NAME": SERVER, "USE_GRPC": "yes", f"{SERVER}_USE_GRPC": "no"}
    assert family_enabled(off_globally, PREFIXES, "gRPC")
    assert not family_enabled(on_globally, PREFIXES, "gRPC")


def test_a_switched_off_family_still_collides_inside_itself_when_switched_on():
    """Gating is per family, not per path: the other families keep their own claims."""
    config = cfg(USE_GRPC="no", GRPC_HOST="grpc://backend:9000", REDIRECT_TO="https://elsewhere.example.com", REMOTE_PHP="php-fpm")
    error = inline_family_conflict(config, SERVER, PREFIXES)
    assert "redirect" in error and "PHP" in error and "gRPC" not in error


# ---------------------------------------------------------------------------------------------
# Render truth — the registry must agree with what the templates actually emit
# ---------------------------------------------------------------------------------------------

# (template, the settings that make it render its location on the default path)
EMITTERS = [
    ("reverseproxy/confs/server-http/reverse-proxy.conf", {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_HOST": "http://backend:8080"}),
    ("grpc/confs/server-http/grpc.conf", {"USE_GRPC": "yes", "GRPC_HOST": "grpc://backend:9000"}),
    ("redirect/confs/server-http/redirect.conf", {"REDIRECT_TO": "https://elsewhere.example.com"}),
    ("php/confs/server-http/php.conf", {"REMOTE_PHP": "php-fpm"}),
]

# Emptying EMITTERS would turn the render assertions into a silent no-op, so floor it. `>=`
# because it grows when another plugin starts emitting a location.
MINIMUM_EMITTERS = 4


def test_the_emitter_list_has_not_emptied_out():
    assert len(EMITTERS) >= MINIMUM_EMITTERS
    # Every registered family must have a render fixture, or the registry can drift from NGINX.
    assert len(EMITTERS) >= len(LOCATION_FAMILIES)


def _default_locations(template: str, trigger: dict) -> list:
    jinja2 = pytest.importorskip("jinja2")
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module  # Templator exposes this; the mTLS block uses it
    # The enable switches are NOT defaulted here: `reverse-proxy.conf:1` and `grpc.conf:1` are
    # wrapped in them, so each emitter carries its own and the disabled direction can be rendered.
    variables = {
        "SERVER_NAME": SERVER,
        "REVERSE_PROXY_CUSTOM_HOST": "",
        "USE_MODSECURITY": "no",
        "USE_MTLS": "no",
        "USE_PROXY_CACHE": "no",
        "USE_UI": "no",
        # php.conf reads these directly rather than through the `all` map the suffixed families use.
        "REMOTE_PHP": "",
        "LOCAL_PHP": "",
        "REMOTE_PHP_PORT": "9000",
        "all": trigger,
    }
    variables.update(trigger)
    rendered = environment.from_string((CORE / template).read_text(encoding="utf-8")).render(**variables)
    return [line.strip() for line in rendered.splitlines() if line.strip().startswith("location ")]


@pytest.mark.parametrize("template,trigger", EMITTERS, ids=[template.split("/")[0] for template, _ in EMITTERS])
def test_every_emitter_renders_the_location_the_registry_claims_for_it(template, trigger):
    """What the registry claims on the default path is literally what NGINX receives.

    php.conf also emits `location ~ \\.php$`, which nothing else can collide with; only the
    unqualified one is the shared claim.
    """
    assert f"location {FIXED_LOCATION} {{" in _default_locations(template, trigger)


@pytest.mark.parametrize(
    ("template", "trigger", "switch"),
    [(EMITTERS[0][0], EMITTERS[0][1], "USE_REVERSE_PROXY"), (EMITTERS[1][0], EMITTERS[1][1], "USE_GRPC")],
    ids=["reverseproxy", "grpc"],
)
def test_a_switched_off_family_renders_no_location_at_all(template, trigger, switch):
    """Render truth for the gate: with the switch off the template emits nothing to collide with.

    Without this the gate is one more opinion about the templates rather than a reading of them.
    """
    assert _default_locations(template, {**trigger, switch: "no"}) == []


def test_the_refused_pairs_are_the_ones_nginx_would_see_twice():
    """Renders the pair the guard refuses and counts the duplicate NGINX would refuse.

    Without this, the guard and the templates are two independent opinions.
    """
    for first, second in ((EMITTERS[0], EMITTERS[3]), (EMITTERS[0], EMITTERS[2]), (EMITTERS[1], EMITTERS[3])):
        emitted = _default_locations(*first) + _default_locations(*second)
        assert emitted.count(f"location {FIXED_LOCATION} {{") == 2, f"{first[0]} + {second[0]} no longer collide"
        assert inline_family_conflict(cfg(**{**first[1], **second[1]}), SERVER, PREFIXES) != ""
