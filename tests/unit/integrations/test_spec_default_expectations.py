"""Integration specs that pin a product default they do not set.

Several `tests/core/*.yml` assertions encode a value that comes from a `plugin.json` default: the
spec sets nothing, sends a request, and requires the shipped default back. That is deliberate --
those actions are the only thing standing between a silent default change and production -- but
nothing tells the person changing the default which specs are wired that way, so the drift is
discovered by a red integration run rather than by the diff that caused it. `4998a9301` is the
worked example: the `PERMISSIONS_POLICY` default went from 54 features to 93, and
`headers.yml check_headers` was resynced afterwards, from CI.

This test closes that loop where it is cheap to close: it re-derives each pin from `plugin.json`
with the same matcher the runner uses, so changing a default without touching the spec fails here,
in the unit suite, next to the change.

It is not a coverage claim. It pins the assertions listed below, not every default a spec relies
on; the rest are inventoried in `.cache/results-2026-08-24/e2e-coverage-matrix.md` (P2).
"""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "tests" / "core"
PLUGINS = ROOT / "src" / "common" / "core"


def _default(plugin: str, setting: str) -> str:
    settings = json.loads((PLUGINS / plugin / "plugin.json").read_text(encoding="utf-8"))["settings"]
    assert setting in settings, f"{setting} is no longer declared by the {plugin} plugin"
    return settings[setting]["default"]


def _action(spec: str, name: str, integration: str = "") -> dict:
    actions = yaml.safe_load((CORE / spec).read_text(encoding="utf-8"))["actions"]
    assert name in actions, f"action {name} disappeared from {spec}"
    action = actions[name]
    if not integration:
        return action
    override = action.get(integration)
    assert isinstance(override, dict), f"{spec}:{name} has no {integration} override any more"
    return {**action, **override}


# (spec, action, response header, plugin, setting). The runner matches a `response_headers` value
# with `re.match(regex, header)` (tests/core_handlers/http_header_handler.py), so the check below
# is that same call against the default -- an anchored regex that no longer matches its own default
# is exactly the drift.
HEADER_PINS = [
    ("headers.yml", "check_headers", "", "Permissions-Policy", "headers", "PERMISSIONS_POLICY"),
    ("headers.yml", "check_headers", "", "Referrer-Policy", "headers", "REFERRER_POLICY"),
    ("headers.yml", "check_headers", "", "X-Frame-Options", "headers", "X_FRAME_OPTIONS"),
    ("headers.yml", "check_headers", "", "X-Content-Type-Options", "headers", "X_CONTENT_TYPE_OPTIONS"),
    ("headers.yml", "check_headers", "", "X-DNS-Prefetch-Control", "headers", "X_DNS_PREFETCH_CONTROL"),
    # The Kubernetes arm has no PHP, so nothing upstream sends a CSP and BunkerWeb emits its own
    # default there -- which makes that override a pin like any other.
    ("headers.yml", "check_headers", "Kubernetes", "Content-Security-Policy", "headers", "CONTENT_SECURITY_POLICY"),
    # Not set by this action either: it tweaks five *other* headers, so the STS value it gets back
    # is the shipped default.
    ("headers.yml", "tweaked_headers_ssl", "", "Strict-Transport-Security", "headers", "STRICT_TRANSPORT_SECURITY"),
    # The report-only variant and the keep-upstream one both assert BunkerWeb's own CSP default
    # (the upstream `index.php` CSP is suppressed there by narrowing KEEP_UPSTREAM_HEADERS).
    ("headers.yml", "check_content_security_policy_header_report_only", "", "Content-Security-Policy-Report-Only", "headers", "CONTENT_SECURITY_POLICY"),
    ("headers.yml", "tweaked_keep_upstream_headers", "", "Content-Security-Policy", "headers", "CONTENT_SECURITY_POLICY"),
    ("clientcache.yml", "activated", "", "Cache-Control", "clientcache", "CLIENT_CACHE_CONTROL"),
]

# (spec, action, plugin, setting) -- `path` actions whose expectation is a default URI.
PATH_PINS = [
    ("antibot.yml", "default_endpoint", "antibot", "ANTIBOT_URI"),
    ("securitytxt.yml", "default_endpoint", "securitytxt", "SECURITYTXT_URI"),
]

# (spec, action, plugin, setting) -- `status` actions whose expectation is a default status code.
STATUS_PINS = [
    ("redirect.yml", "check_status", "redirect", "REDIRECT_TO_STATUS_CODE"),
]


@pytest.mark.parametrize("spec,action,integration,header,plugin,setting", HEADER_PINS, ids=lambda v: str(v))
def test_header_expectation_still_matches_the_shipped_default(spec, action, integration, header, plugin, setting):
    regex = _action(spec, action, integration)["response_headers"][header]
    assert regex is not None, f"{spec}:{action} now asserts {header} is absent; this pin is stale"
    default = _default(plugin, setting)
    assert re.match(regex, default), (
        f"{spec}:{action} pins {header} with {regex!r}, which no longer matches the {setting} "
        f"default {default!r}. Resync the spec with the new default in the same change."
    )


@pytest.mark.parametrize("spec,action,plugin,setting", PATH_PINS, ids=lambda v: str(v))
def test_path_expectation_still_matches_the_shipped_default(spec, action, plugin, setting):
    assert _action(spec, action)["path"] == _default(plugin, setting)


@pytest.mark.parametrize("spec,action,plugin,setting", STATUS_PINS, ids=lambda v: str(v))
def test_status_expectation_still_matches_the_shipped_default(spec, action, plugin, setting):
    assert str(_action(spec, action)["status"]) == _default(plugin, setting)


# ── The meta-guard ──────────────────────────────────────────────────────────────────────────────
# The list above is hand-written, and a hand-written list of tripwires rots: the next person to add
# a header expectation that encodes a default has no reason to come here. So the list is checked
# for completeness mechanically.
#
# The rule: a `response_headers` expectation is default-derived unless the action that makes it (or
# its spec's global `config`) sets the setting that produces the header. Only headers this map
# knows are considered — a `Content-Encoding` or an `ETag` is produced by the code, not by a
# settable value, and has no default to drift away from.
HEADER_SETTINGS = {
    "Permissions-Policy": ("headers", "PERMISSIONS_POLICY"),
    "Referrer-Policy": ("headers", "REFERRER_POLICY"),
    "X-Frame-Options": ("headers", "X_FRAME_OPTIONS"),
    "X-Content-Type-Options": ("headers", "X_CONTENT_TYPE_OPTIONS"),
    "X-DNS-Prefetch-Control": ("headers", "X_DNS_PREFETCH_CONTROL"),
    "Strict-Transport-Security": ("headers", "STRICT_TRANSPORT_SECURITY"),
    "Content-Security-Policy": ("headers", "CONTENT_SECURITY_POLICY"),
    "Content-Security-Policy-Report-Only": ("headers", "CONTENT_SECURITY_POLICY"),
    "Cache-Control": ("clientcache", "CLIENT_CACHE_CONTROL"),
}

# Expectations that carry one of those header names without being that plugin's default. Each entry
# needs the reason, because "it is not a default" is exactly the claim a future reader has to be
# able to re-check.
NOT_A_DEFAULT = {
    # The challenge page builds its own CSP around a per-request nonce; the `headers` plugin's
    # value never reaches it.
    ("antibot.yml", "capjs_csp", "Content-Security-Policy"),
    ("antibot.yml", "capjs_csp_parent", "Content-Security-Policy"),
    # `tests/misc/index.php` sends this CSP and BunkerWeb keeps it verbatim, because
    # Content-Security-Policy is in the default KEEP_UPSTREAM_HEADERS list. The Kubernetes arm has
    # no PHP, which is why *that* override is a real pin and is in HEADER_PINS above. Keyed on the
    # header, not the action: the other five expectations in `check_headers` ARE defaults.
    ("headers.yml", "check_headers", "Content-Security-Policy"),
    # `templates.yml` drives Referrer-Policy from a USE_TEMPLATE LAYER, never from the `headers`
    # plugin default: `low` sets "no-referrer-when-downgrade", `high` sets "no-referrer", and the
    # three actions below exist precisely because the two disagree -- the value that comes back
    # names which layer won. The rule this meta-guard applies ("the action set the setting, so
    # there is no default to drift") has no notion of USE_TEMPLATE, so a template-sourced value
    # reads to it as a default. Re-checkable in one step: `grep REFERRER_POLICY
    # src/common/core/templates/templates/{low,high}.json` -- neither value is the plugin default
    # ("strict-origin-when-cross-origin"), which is what a real pin here would have to be.
    ("templates.yml", "order_low_then_high", "Referrer-Policy"),
    ("templates.yml", "order_high_then_low", "Referrer-Policy"),
    ("templates.yml", "unknown_layer_is_skipped_and_reported", "Referrer-Policy"),
}


def _spec_globals(spec: str) -> dict:
    return yaml.safe_load((CORE / spec).read_text(encoding="utf-8")).get("config") or {}


def _default_derived_expectations():
    """(spec, action, header) for every top-level expectation that pins a settable header's default.

    Per-integration overrides are deliberately out: an override is a deviation from the arm the
    action was written for, and reading one as a default pin would flag every legitimate one. The
    Kubernetes CSP override is pinned by hand above for that reason.
    """
    found = []
    for path in sorted(CORE.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        globals_ = document.get("config") or {}
        for name, action in (document.get("actions") or {}).items():
            if not isinstance(action, dict):
                continue
            for header, expectation in (action.get("response_headers") or {}).items():
                if expectation is None or header not in HEADER_SETTINGS:
                    continue
                if (path.name, name, header) in NOT_A_DEFAULT:
                    continue
                setting = HEADER_SETTINGS[header][1]
                if setting in (action.get("config") or {}) or setting in globals_:
                    continue  # the action chose the value; there is no default to drift
                found.append((path.name, name, header))
    return found


def test_every_default_derived_header_expectation_is_pinned():
    pinned = {(spec, action, header) for spec, action, _, header, _, _ in HEADER_PINS}
    unpinned = [entry for entry in _default_derived_expectations() if entry not in pinned]
    assert not unpinned, (
        "these response_headers expectations pin a plugin default that nothing re-derives:\n  "
        + "\n  ".join(f"{spec}:{action} -> {header}" for spec, action, header in unpinned)
        + "\nAdd them to HEADER_PINS, or to NOT_A_DEFAULT with the reason they are not one."
    )


def test_the_meta_guard_sees_something():
    """A completeness check that matches nothing is a completeness check that passes forever."""
    assert len(_default_derived_expectations()) >= 5
