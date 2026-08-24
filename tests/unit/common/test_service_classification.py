"""Unit coverage for the shared PRO quota classifier.

Mirrors the test matrix of the "Services de redirection et comptabilisation PRO"
conception: classification, mixed services, custom configs, repeated settings,
unknown plugins, attachments, and aggregate coherence.
"""

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

import service_classification  # type: ignore
from service_classification import (  # type: ignore
    ALGORITHM_VERSION,
    ALLOWED_SETTINGS,
    ALLOWLIST_VERSION,
    BILLABLE,
    CAPABILITY_DEFAULTS,
    EXEMPTION_ENABLED,
    DRAFT,
    EXEMPT_REDIRECT,
    INVALID,
    MODE_REDIRECT_ONLY,
    MODE_STANDARD,
    SERVICE_MODE_SETTING,
    base_setting,
    classify,
    count,
    count_snapshot,
    explain,
    setting_value,
    split_services,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


@contextmanager
def lot_c():
    """Run with the Lot C exemption gate forced on.

    `EXEMPTION_ENABLED` is False in production today, so `classify()` reports a
    valid declaration as billable. The RULE underneath still has to be exercised
    in both directions, or flipping the flag in Lot C would ship untested
    behaviour — that is what this context manager is for.
    """
    original = service_classification.EXEMPTION_ENABLED
    service_classification.EXEMPTION_ENABLED = True
    try:
        yield
    finally:
        service_classification.EXEMPTION_ENABLED = original


def classify_rule(*args, **kwargs):
    """`classify()` as it will answer once Lot C lands."""
    with lot_c():
        return classify(*args, **kwargs)


def redirect_only(**extra):
    """A minimal, VALID redirect-only service config.

    `SERVE_FILES` has to be here: it defaults to "yes", so a service that never
    sets it serves the document root on every path the redirect does not cover
    (see CAPABILITY_DEFAULTS).
    """
    config = {
        "SERVER_NAME": "redirect.example.com",
        SERVICE_MODE_SETTING: MODE_REDIRECT_ONLY,
        "REDIRECT_TO": "https://target.example.com",
        "SERVE_FILES": "no",
    }
    config.update(extra)
    return config


# --------------------------------------------------------------------------
# Classification: draft / standard / redirect-only valid / invalid
# --------------------------------------------------------------------------
def test_plain_service_is_billable():
    assert classify_rule({"SERVER_NAME": "app.example.com"}) == BILLABLE


def test_explicit_standard_mode_is_billable():
    assert classify_rule({"SERVER_NAME": "app.example.com", SERVICE_MODE_SETTING: MODE_STANDARD}) == BILLABLE


def test_draft_wins_over_every_other_class():
    assert classify_rule({"SERVER_NAME": "app.example.com", "IS_DRAFT": "yes"}) == DRAFT
    assert classify_rule(redirect_only(IS_DRAFT="yes")) == DRAFT
    # A draft that would otherwise be invalid is still just a draft.
    assert classify_rule(redirect_only(IS_DRAFT="yes", USE_REVERSE_PROXY="yes")) == DRAFT


def test_is_draft_no_is_not_a_draft():
    assert classify_rule({"SERVER_NAME": "app.example.com", "IS_DRAFT": "no"}) == BILLABLE


def test_valid_redirect_only_is_exempt():
    assert classify_rule(redirect_only()) == EXEMPT_REDIRECT
    assert explain(redirect_only()) == []


def test_unknown_service_mode_value_is_not_exempt():
    # Anything that is not the exact redirect_only token is an ordinary service.
    for value in ("Redirect_Only", "redirect-only", "redirectonly", "", "exempt"):
        assert classify_rule({"SERVER_NAME": "a.example.com", SERVICE_MODE_SETTING: value}) == BILLABLE


def test_exemption_is_never_inferred_from_redirect_to():
    # The whole point of the rule: a redirect on an undeclared service counts.
    assert classify_rule({"SERVER_NAME": "a.example.com", "REDIRECT_TO": "https://x.example.com"}) == BILLABLE


def test_redirect_only_without_target_is_invalid():
    config = {"SERVER_NAME": "a.example.com", SERVICE_MODE_SETTING: MODE_REDIRECT_ONLY}
    assert classify_rule(config) == INVALID
    assert "no REDIRECT_TO target set" in explain(config)


def test_redirect_only_with_empty_target_is_invalid():
    assert classify_rule(redirect_only(REDIRECT_TO="")) == INVALID


def test_full_redirect_contract_stays_exempt():
    config = redirect_only(REDIRECT_FROM="/old", REDIRECT_TO_REQUEST_URI="yes", REDIRECT_TO_STATUS_CODE="308")
    assert classify_rule(config) == EXEMPT_REDIRECT


# --------------------------------------------------------------------------
# Mixed services: redirect + proxy / content / auth / security
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key, value",
    [
        ("USE_REVERSE_PROXY", "yes"),
        ("REVERSE_PROXY_HOST", "http://app:8080"),
        ("USE_GRPC", "yes"),
        ("GRPC_HOST", "grpc://app:9000"),
        ("SERVE_FILES", "yes"),
        ("ROOT_FOLDER", "/var/www/site"),
        ("USE_AUTH_BASIC", "yes"),
        ("AUTH_BASIC_USER", "admin"),
        ("USE_MTLS", "yes"),
        ("USE_ANTIBOT", "captcha"),
        ("INJECT_BODY", "<script></script>"),
        ("ERRORS", "404=/errors/404.html"),
        ("USE_TEMPLATE", "some-template"),
        ("WHITELIST_IP", "10.0.0.1"),
        ("USE_CORS", "yes"),
        ("USE_UI", "yes"),
        ("REMOTE_PHP", "php:9000"),
        ("SESSIONS_DOMAIN", "example.com"),
        ("PLUGINS_ORDER_ACCESS", "ssl misc"),
    ],
)
def test_mixed_capability_makes_redirect_only_invalid(key, value):
    config = redirect_only(**{key: value})
    assert classify_rule(config) == INVALID
    assert any(key in reason for reason in explain(config))


@pytest.mark.parametrize(
    "key",
    [
        "USE_REVERSE_PROXY",
        "USE_GRPC",
        "SERVE_FILES",
        "USE_MODSECURITY",
        "USE_WHITELIST",
        "USE_BLACKLIST",
        "USE_BAD_BEHAVIOR",
        "USE_LIMIT_REQ",
        "USE_ANTIBOT",
        "USE_CROWDSEC",
        "USE_REAL_IP",
        "USE_GZIP",
    ],
)
def test_disabling_an_optional_plugin_keeps_the_exemption(key):
    # An operator turning a plugin OFF (often globally) never costs the exemption;
    # turning it ON always does.
    assert classify_rule(redirect_only(**{key: "no"})) == EXEMPT_REDIRECT
    assert classify_rule(redirect_only(**{key: "yes"})) == INVALID


def test_server_type_is_pinned_to_http():
    # The Redirect plugin is HTTP-only ("stream": "no"), so a stream listener
    # cannot be a valid redirect service.
    assert classify_rule(redirect_only(SERVER_TYPE="http")) == EXEMPT_REDIRECT
    config = redirect_only(SERVER_TYPE="stream")
    assert classify_rule(config) == INVALID
    assert any("SERVER_TYPE" in reason for reason in explain(config))


@pytest.mark.parametrize(
    "key, value",
    [
        ("AUTO_LETS_ENCRYPT", "yes"),
        ("EMAIL_LETS_ENCRYPT", "ops@example.com"),
        ("LETS_ENCRYPT_CHALLENGE", "dns"),
        ("USE_CUSTOM_SSL", "yes"),
        ("CUSTOM_SSL_CERT", "/certs/cert.pem"),
        ("GENERATE_SELF_SIGNED_SSL", "yes"),
        ("SSL_PROTOCOLS", "TLSv1.3"),
        ("REDIRECT_HTTP_TO_HTTPS", "yes"),
        ("LISTEN_HTTP", "no"),
        ("HTTP3", "no"),
        ("USE_METRICS", "yes"),
        ("SECURITY_MODE", "detect"),
        ("LISTEN_STREAM", "no"),
    ],
)
def test_listener_tls_acme_and_observability_stay_exempt(key, value):
    assert classify_rule(redirect_only(**{key: value})) == EXEMPT_REDIRECT


# --------------------------------------------------------------------------
# Repeated (``multiple``) settings
# --------------------------------------------------------------------------
def test_repeated_redirect_settings_are_allowed():
    config = redirect_only(REDIRECT_FROM_2="/legacy", REDIRECT_TO_2="https://other.example.com", REDIRECT_TO_STATUS_CODE_2="302")
    assert classify_rule(config) == EXEMPT_REDIRECT


def test_target_can_come_from_a_suffixed_key_only():
    config = {
        "SERVER_NAME": "a.example.com",
        SERVICE_MODE_SETTING: MODE_REDIRECT_ONLY,
        "REDIRECT_TO_2": "https://target.example.com",
        "SERVE_FILES": "no",
    }
    assert classify_rule(config) == EXEMPT_REDIRECT


def test_repeated_forbidden_setting_is_still_forbidden():
    config = redirect_only(REVERSE_PROXY_HOST_1="http://app:8080")
    assert classify_rule(config) == INVALID
    assert any("REVERSE_PROXY_HOST_1" in reason for reason in explain(config))


def test_suffix_stripping_never_invents_an_allowed_key():
    # "<allowed>_<n>" only collapses when the base really is allowlisted.
    assert base_setting("REDIRECT_TO_2") == "REDIRECT_TO"
    assert base_setting("REVERSE_PROXY_HOST_1") == "REVERSE_PROXY_HOST_1"
    assert base_setting("LIMIT_CONN_MAX_HTTP1") == "LIMIT_CONN_MAX_HTTP1"
    assert base_setting("SERVER_NAME") == "SERVER_NAME"


def test_suffixed_toggle_still_honours_its_allowed_values():
    # A "multiple" repetition of a disable-only toggle must keep the value gate.
    assert classify_rule(redirect_only(SERVE_FILES_2="yes")) == INVALID


# --------------------------------------------------------------------------
# Unknown / external plugins
# --------------------------------------------------------------------------
def test_unknown_plugin_setting_is_billable_by_default():
    config = redirect_only(SOME_EXTERNAL_PLUGIN_SETTING="anything")
    assert classify_rule(config) == INVALID
    assert any("SOME_EXTERNAL_PLUGIN_SETTING" in reason for reason in explain(config))


def test_unknown_plugin_setting_left_at_default_is_not_reported():
    # The input contract is the NON-DEFAULT persisted config: a setting the
    # operator never touched is simply absent.
    assert classify_rule(redirect_only()) == EXEMPT_REDIRECT


# --------------------------------------------------------------------------
# Custom NGINX snippets and attachable resources
# --------------------------------------------------------------------------
def test_custom_config_forbids_the_exemption():
    config = redirect_only()
    assert classify_rule(config, custom_configs=[{"type": "server-http", "name": "extra"}]) == INVALID
    assert "1 custom config(s) attached" in explain(config, custom_configs=[{"type": "server-http", "name": "extra"}])


def test_several_custom_configs_are_counted():
    reasons = explain(redirect_only(), custom_configs=[{"type": "server-http"}, {"type": "modsec"}])
    assert "2 custom config(s) attached" in reasons


@pytest.mark.parametrize("kind", ["certificate", "redirect"])
def test_allowed_attachments_keep_the_exemption(kind):
    assert classify_rule(redirect_only(), attachments=[kind]) == EXEMPT_REDIRECT
    assert classify_rule(redirect_only(), attachments=[{"type": kind}]) == EXEMPT_REDIRECT


@pytest.mark.parametrize("kind", ["upstream", "workflow", "something-new"])
def test_forbidden_attachments_invalidate_the_exemption(kind):
    config = redirect_only()
    assert classify_rule(config, attachments=[kind]) == INVALID
    assert any(kind in reason for reason in explain(config, attachments=[kind]))


def test_custom_configs_and_attachments_do_not_affect_a_standard_service():
    config = {"SERVER_NAME": "app.example.com"}
    assert classify_rule(config, custom_configs=[{"type": "server-http"}], attachments=["upstream"]) == BILLABLE


# --------------------------------------------------------------------------
# ``methods=True`` entry shape
# --------------------------------------------------------------------------
def test_methods_shape_is_accepted():
    config = {
        "SERVER_NAME": {"value": "a.example.com", "method": "ui", "global": False, "default": ""},
        SERVICE_MODE_SETTING: {"value": MODE_REDIRECT_ONLY, "method": "ui", "global": False, "default": MODE_STANDARD},
        "REDIRECT_TO": {"value": "https://target.example.com", "method": "ui", "global": False, "default": ""},
        "SERVE_FILES": {"value": "no", "method": "ui", "global": False, "default": "yes"},
    }
    assert classify_rule(config) == EXEMPT_REDIRECT
    config["USE_REVERSE_PROXY"] = {"value": "yes", "method": "scheduler", "global": True, "default": "no"}
    assert classify_rule(config) == INVALID


def test_setting_value_normalizes_both_shapes():
    assert setting_value("  yes ") == "yes"
    assert setting_value({"value": " yes "}) == "yes"
    assert setting_value(None) == ""
    assert setting_value({"value": None}) == ""
    assert setting_value(301) == "301"


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------
def test_count_over_a_mapping():
    services = {
        "app.example.com": {"SERVER_NAME": "app.example.com"},
        "old.example.com": redirect_only(SERVER_NAME="old.example.com"),
        "bad.example.com": redirect_only(SERVER_NAME="bad.example.com", USE_REVERSE_PROXY="yes"),
        "draft.example.com": {"SERVER_NAME": "draft.example.com", "IS_DRAFT": "yes"},
    }
    with lot_c():
        counts = count(services)
    assert counts.total == 4
    assert counts.standard == 1
    assert counts.exempt_redirect == 1
    assert counts.invalid == 1
    assert counts.draft == 1
    # Fail closed: an invalid redirect declaration is billed.
    assert counts.billable == 2
    assert counts.algorithm_version == ALGORITHM_VERSION
    assert counts.allowlist_version == ALLOWLIST_VERSION

    # Production today: the gate is shut, so the valid declaration is billed too
    # and only the draft is free.
    counts = count(services)
    assert (counts.total, counts.billable, counts.exempt_redirect, counts.draft) == (4, 3, 0, 1)


def test_count_over_a_bare_iterable():
    with lot_c():
        counts = count([{"SERVER_NAME": "a.example.com"}, redirect_only()])
    assert (counts.total, counts.billable, counts.exempt_redirect) == (2, 1, 1)


def test_count_is_empty_for_no_services():
    counts = count({})
    assert (counts.total, counts.billable, counts.exempt_redirect, counts.invalid, counts.draft) == (0, 0, 0, 0, 0)


def test_per_service_custom_configs_and_attachments_are_keyed_by_name():
    services = {"a.example.com": redirect_only(SERVER_NAME="a.example.com"), "b.example.com": redirect_only(SERVER_NAME="b.example.com")}
    with lot_c():
        counts = count(services, custom_configs={"a.example.com": [{"type": "server-http"}]}, attachments={"b.example.com": ["upstream"]})
        assert counts.invalid == 2
        assert counts.billable == 2

        counts = count(services, custom_configs={"a.example.com": [{"type": "server-http"}]})
        assert (counts.invalid, counts.exempt_redirect, counts.billable) == (1, 1, 1)


# --------------------------------------------------------------------------
# Snapshot slicing
# --------------------------------------------------------------------------
def test_split_services_keeps_only_prefixed_rows():
    snapshot = {
        "SERVER_NAME": "a.example.com b.example.com",
        "LOG_LEVEL": "info",
        "USE_REVERSE_PROXY": "yes",
        "a.example.com_SERVICE_MODE": "redirect_only",
        "a.example.com_REDIRECT_TO": "https://t.example.com",
        "b.example.com_USE_REVERSE_PROXY": "yes",
    }
    services = split_services(snapshot)
    assert set(services) == {"a.example.com", "b.example.com"}
    # Global-context rows are not service capabilities and never leak in.
    assert "LOG_LEVEL" not in services["a.example.com"]
    assert services["a.example.com"] == {"SERVICE_MODE": "redirect_only", "REDIRECT_TO": "https://t.example.com"}


def test_split_services_handles_a_name_that_prefixes_another():
    # Domain labels may legally contain "_"; the longest name must win.
    snapshot = {
        "SERVER_NAME": "a.example.com a.example.com_b",
        "a.example.com_b_REDIRECT_TO": "https://t.example.com",
        "a.example.com_REDIRECT_TO": "https://u.example.com",
    }
    services = split_services(snapshot)
    assert services["a.example.com_b"] == {"REDIRECT_TO": "https://t.example.com"}
    assert services["a.example.com"] == {"REDIRECT_TO": "https://u.example.com"}


def test_count_snapshot_matches_manual_split():
    snapshot = {
        "SERVER_NAME": "a.example.com b.example.com c.example.com",
        "a.example.com_SERVICE_MODE": "redirect_only",
        "a.example.com_REDIRECT_TO": "https://t.example.com",
        "a.example.com_SERVE_FILES": "no",
        "b.example.com_IS_DRAFT": "yes",
        "c.example.com_USE_REVERSE_PROXY": "yes",
    }
    with lot_c():
        counts = count_snapshot(snapshot)
        assert (counts.total, counts.billable, counts.exempt_redirect, counts.draft) == (3, 1, 1, 1)
        assert counts == count(split_services(snapshot))


def test_globally_enabled_capability_disqualifies_every_redirect_service():
    # get_non_default_settings propagates a global multisite override onto every
    # service, so a fleet-wide reverse proxy really does bill the redirects.
    snapshot = {
        "SERVER_NAME": "a.example.com",
        "USE_REVERSE_PROXY": "yes",
        "a.example.com_USE_REVERSE_PROXY": "yes",
        "a.example.com_SERVICE_MODE": "redirect_only",
        "a.example.com_REDIRECT_TO": "https://t.example.com",
    }
    counts = count_snapshot(snapshot)
    assert (counts.invalid, counts.billable, counts.exempt_redirect) == (1, 1, 0)


def test_snapshot_without_multisite_propagation_counts_every_service_billable():
    # MULTISITE=no: no per-service rows at all, one billable service.
    counts = count_snapshot({"SERVER_NAME": "a.example.com"})
    assert (counts.total, counts.billable) == (1, 1)


# --------------------------------------------------------------------------
# Anti-drift: the allowlist is data, and it must name REAL settings
# --------------------------------------------------------------------------
def _declared_settings():
    declared = {}
    general = json.loads((_REPO_ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8"))
    for key, value in general.items():
        declared[key] = value
    for plugin_file in sorted((_REPO_ROOT / "src" / "common" / "core").glob("*/plugin.json")):
        plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
        for key, value in plugin.get("settings", {}).items():
            declared[key] = value
    return declared


def test_every_allowlisted_key_is_a_declared_multisite_setting():
    declared = _declared_settings()
    unknown = sorted(key for key in ALLOWED_SETTINGS if key not in declared)
    assert unknown == [], f"allowlist names settings that do not exist: {unknown}"
    not_multisite = sorted(key for key in ALLOWED_SETTINGS if declared[key].get("context") != "multisite")
    assert not_multisite == [], f"allowlist names non-multisite settings: {not_multisite}"


def test_service_mode_setting_is_declared_with_the_expected_contract():
    declared = _declared_settings()
    assert SERVICE_MODE_SETTING in declared, "SERVICE_MODE must be declared as a real setting"
    setting = declared[SERVICE_MODE_SETTING]
    assert setting["context"] == "multisite"
    assert setting["default"] == MODE_STANDARD
    assert sorted(setting["select"]) == sorted([MODE_STANDARD, MODE_REDIRECT_ONLY])


def test_allowed_values_are_declared_values_of_their_setting():
    declared = _declared_settings()
    for key, allowed in ALLOWED_SETTINGS.items():
        if allowed is None:
            continue
        regex = declared[key].get("regex", "")
        for value in allowed:
            assert __import__("re").match(regex, value), f"{key}={value!r} does not match its own regex {regex!r}"


# --------------------------------------------------------------------------
# The Lot C gate: no service is exempt yet, and that has to be provable
# --------------------------------------------------------------------------
def test_the_exemption_is_off_in_production():
    assert EXEMPTION_ENABLED is False, "flipping this is Lot C's job, in the commit that supplies the evidence"


def test_a_valid_declaration_is_still_billed_today():
    config = redirect_only()
    # The RULE says it holds up...
    assert explain(config) == []
    assert classify_rule(config) == EXEMPT_REDIRECT
    # ...and the gate bills it anyway.
    assert classify(config) == BILLABLE


def test_evidence_free_call_sites_cannot_buy_a_free_service():
    """The fail-open the review found, pinned shut.

    Both wired call sites pass no custom configs and no attachments, so a
    server_http snippet carrying a proxy_pass is invisible to the classifier.
    While the gate is shut that cannot be exploited: the service is billed.
    """
    smuggled = redirect_only()  # would-be exempt, with a proxy_pass snippet the caller never passes
    assert classify(smuggled) == BILLABLE
    assert classify(smuggled, custom_configs=()) == BILLABLE
    # And with the evidence, the rule refuses it outright.
    assert classify_rule(smuggled, custom_configs=[{"type": "server-http", "name": "proxy"}]) == INVALID


def test_the_gate_never_hides_an_invalid_declaration():
    # Only the exempt verdict is gated; invalid must stay visible with its reasons.
    config = redirect_only(USE_REVERSE_PROXY="yes")
    assert classify(config) == INVALID
    assert classify_rule(config) == INVALID
    assert explain(config) != []


def test_counts_are_identical_to_the_pre_wiring_count():
    """Lot B is a pure refactor: billable == every non-draft service, as before.

    The three call sites used to count `len(SERVER_NAME.split())` (drafts already
    excluded at the source) or `len(get_services())`. While the gate is shut the
    shared classifier must return exactly that number for ANY configuration,
    redirect declarations included — otherwise wiring it changed a customer's bill.
    """
    snapshots = [
        {"SERVER_NAME": "a.example.com"},
        {"SERVER_NAME": "a.example.com b.example.com c.example.com"},
        # a valid redirect-only declaration
        {
            "SERVER_NAME": "a.example.com b.example.com",
            "b.example.com_SERVICE_MODE": "redirect_only",
            "b.example.com_REDIRECT_TO": "https://a.example.com",
            "b.example.com_SERVE_FILES": "no",
        },
        # an invalid one
        {
            "SERVER_NAME": "a.example.com b.example.com",
            "b.example.com_SERVICE_MODE": "redirect_only",
            "b.example.com_REDIRECT_TO": "https://a.example.com",
            "b.example.com_USE_REVERSE_PROXY": "yes",
        },
        # a fleet of redirect declarations, which is the case the exemption exists for
        {
            "SERVER_NAME": " ".join(f"r{i}.example.com" for i in range(10)),
            **{f"r{i}.example.com_SERVICE_MODE": "redirect_only" for i in range(10)},
            **{f"r{i}.example.com_REDIRECT_TO": "https://a.example.com" for i in range(10)},
            **{f"r{i}.example.com_SERVE_FILES": "no" for i in range(10)},
        },
    ]
    for snapshot in snapshots:
        legacy = len(snapshot["SERVER_NAME"].split())
        assert count_snapshot(snapshot).billable == legacy, snapshot["SERVER_NAME"]

    # And the moment the gate opens, the fleet stops being billed -- which is the
    # whole point, and the reason the flip is a deliberate, separate decision.
    with lot_c():
        assert count_snapshot(snapshots[-1]).billable == 0
        assert count_snapshot(snapshots[-1]).exempt_redirect == 10


# --------------------------------------------------------------------------
# Capability defaults: a setting nobody touched can still serve content
# --------------------------------------------------------------------------
def test_absent_serve_files_is_a_violation():
    """SERVE_FILES defaults to yes, so silence means "serves the document root".

    Explicit `yes` and inherited `yes` render byte-identical NGINX; classifying
    them differently would be a hole you open by NOT typing a setting.
    """
    config = {
        "SERVER_NAME": "a.example.com",
        SERVICE_MODE_SETTING: MODE_REDIRECT_ONLY,
        "REDIRECT_TO": "https://target.example.com",
    }
    assert classify_rule(config) == INVALID
    assert any("SERVE_FILES" in reason and "default" in reason for reason in explain(config))


def test_explicit_serve_files_no_is_what_makes_the_declaration_hold_up():
    assert classify_rule(redirect_only(SERVE_FILES="no")) == EXEMPT_REDIRECT
    assert explain(redirect_only(SERVE_FILES="no")) == []


def test_explicit_serve_files_yes_is_refused_the_same_way_as_the_default():
    absent = {"SERVER_NAME": "a.example.com", SERVICE_MODE_SETTING: MODE_REDIRECT_ONLY, "REDIRECT_TO": "https://t.example.com"}
    explicit = dict(absent, SERVE_FILES="yes")
    # Same service, same rendered NGINX, same verdict.
    assert classify_rule(absent) == classify_rule(explicit) == INVALID


def test_a_capability_default_survives_the_suffix_stripper():
    # SERVE_FILES_2 is not a real repetition group, so it must not satisfy the
    # "SERVE_FILES was set" check and let the default through unevaluated.
    config = redirect_only()
    config.pop("SERVE_FILES")
    config["SERVE_FILES_2"] = "no"
    assert classify_rule(config) == INVALID


def test_capability_defaults_match_the_real_plugin_defaults():
    """The map hardcodes a default; a drifting default would silently reopen the hole."""
    declared = _declared_settings()
    for key, default in CAPABILITY_DEFAULTS.items():
        assert key in declared, f"CAPABILITY_DEFAULTS names an unknown setting: {key}"
        assert declared[key]["default"] == default, f"{key} defaults to {declared[key]['default']!r}, not {default!r}"
        assert key in ALLOWED_SETTINGS, f"{key} must be allowlisted (with the value that is safe) to be evaluable"


def test_a_template_layer_is_refused_because_it_is_not_resolved():
    """ADR consequence #2, pinned.

    `get_non_default_settings` does not resolve template layers, so a template
    could carry a reverse proxy invisibly. USE_TEMPLATE is therefore forbidden.
    """
    config = redirect_only(USE_TEMPLATE="some-template")
    assert classify_rule(config) == INVALID
    assert any("USE_TEMPLATE" in reason for reason in explain(config))
