"""The redirect-only rule, judged on REAL persisted state instead of a hand-written dict.

`tests/unit/common/test_service_classification.py` proves the rule. It proves it on synthetic
mappings handed straight to `classify()`/`explain()`, which is the right shape for a rule test and
the wrong shape for the question this file asks: does the rule still hold when the configuration
went through `Database.save_config` -- the ONE write path the API's `PATCH /services/{id}`, its
`PUT /configs/bulk` and the UI's service form all funnel into -- and when the evidence comes out of
`get_non_default_settings()`, `get_custom_configs()` and the resource-attachment tables the way the
live callers read it?

Every scenario below therefore writes, then re-reads, then classifies. Nothing is asserted about a
value that was not persisted first.

Two properties are load-bearing and are what each scenario is really pinning:

* **fail closed.** There is no write-time refusal on the generic paths (that is what the explicit
  conversion endpoint added, for itself only), so an operator CAN save an incompatible
  `redirect_only` declaration. When they do, the read-time classification must call it `invalid`
  and BILL it. A hole here is a free service.
* **never inferred.** A service that happens to hold nothing but a redirect is NOT exempt. Only an
  explicit `SERVICE_MODE=redirect_only` declaration is, and `REDIRECT_TO` -- reachable from
  templates, external plugins and attached resources -- never grants it.

PO ruling 2026-09-10: the exemption applies ONLY to the PRO counts. Everywhere else a redirect-only
service is a full service, and the last scenario pins exactly that.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

import service_classification  # type: ignore
from service_classification import (  # type: ignore
    BILLABLE,
    CAPABILITY_DEFAULTS,
    EXEMPTION_ENABLED,
    INVALID,
    MODE_REDIRECT_ONLY,
    MODE_STANDARD,
    classify,
    count_snapshot,
    explain,
    split_services,
)


@contextmanager
def _gate_open():
    """`EXEMPTION_ENABLED` flipped for the span of one assertion, and only that.

    Same device as `classify_rule` in `test_service_classification.py`, for the same reason: while
    the gate is shut `classify()` answers `billable` for BOTH a valid declaration and an ordinary
    service, so any claim about the RULE -- "the exemption is never inferred" first among them --
    is unfalsifiable unless it is asked with the gate open.
    """
    original = service_classification.EXEMPTION_ENABLED
    service_classification.EXEMPTION_ENABLED = True
    try:
        yield
    finally:
        service_classification.EXEMPTION_ENABLED = original


from fixtures.seed import add_custom_config_row, add_service, seed_minimal, session

REDIRECT_SERVICE = "old.example.com"
PROXY_SERVICE = "app1.example.com"  # seeded by seed_minimal


@pytest.fixture
def multisite_db(db):
    """A real multisite database carrying the settings a redirect profile needs.

    `save_config` writes only KNOWN settings, so the three the redirect-only allowlist reads have
    to exist as rows -- exactly as they do in a real deployment, where they come from
    `misc/plugin.json` and `redirect/plugin.json`.
    """
    from model import Global_values, Settings, Template_settings, Templates  # type: ignore

    seed_minimal(db)
    add_service(db, REDIRECT_SERVICE)
    with session(db) as s:
        s.add_all(
            [
                Settings(
                    id="SERVICE_MODE",
                    name="SERVICE_MODE",
                    plugin_id="general",
                    context="multisite",
                    help="h",
                    regex="^(standard|redirect_only)$",
                    type="select",
                    default=MODE_STANDARD,
                ),
                Settings(id="REDIRECT_TO", name="REDIRECT_TO", plugin_id="general", context="multisite", help="h", regex="^.*$", type="text", default=""),
                Settings(
                    id="SERVE_FILES", name="SERVE_FILES", plugin_id="general", context="multisite", help="h", regex="^(yes|no)$", type="check", default="yes"
                ),
            ]
        )
        s.add(Global_values(setting_id="MULTISITE", value="yes", method="manual", suffix=0))
        now = datetime.now(timezone.utc)
        s.add(Templates(id="low", name="low", plugin_id="general", method="manual", creation_date=now, last_update=now))
        s.flush()
        # The layer really CARRIES a forbidden capability. `get_non_default_settings` does not
        # resolve template layers, so this value is invisible to the classifier -- which is the
        # whole point: the refusal must come from USE_TEMPLATE being declared at all, and it has to
        # be provable that the content was never what tripped it.
        s.add(Template_settings(template_id="low", setting_id="USE_REVERSE_PROXY", step_id=0, default="yes", suffix=0, order=0))
    return db


def _redirect_profile(service, **extra):
    """The settings a valid redirect-only service carries, prefixed for `save_config`.

    `SERVE_FILES=no` is not optional: its plugin default is `yes`, so a service that never mentions
    it still serves the document root on every path its redirect does not cover (ADR §5bis).
    """
    profile = {
        f"{service}_REDIRECT_TO": "https://new.example.com",
        f"{service}_SERVE_FILES": "no",
    }
    profile.update({f"{service}_{key}": value for key, value in extra.items()})
    return profile


def _write(db, services, **overrides):
    """Persist a whole-config payload through the shared write path and return the new snapshot."""
    config = {"MULTISITE": "yes", "SERVER_NAME": " ".join(services)}
    for service in services:
        config[f"{service}_SERVER_NAME"] = service
    config.update(overrides)
    result = db.save_config(config, "manual", changed=True)
    assert not isinstance(result, str), result
    return db.get_non_default_settings(global_only=False, methods=False, with_drafts=False)


def _evidence(db):
    """``(custom_configs, attachments)`` keyed by service, read the way the live callers read them.

    A local mirror of what `src/api/app/routers/services.py` gathers, on purpose: what is being
    tested here is that the DATABASE really produces this shape for a real attachment, not that the
    router's copy of the loop is spelled the same way. The router's own version is covered by
    `tests/unit/api/test_service_mode_conversion.py`.
    """
    custom_configs = {}
    for config in db.get_custom_configs(with_drafts=True, with_data=False):
        if config.get("service_id"):
            custom_configs.setdefault(config["service_id"], []).append(config)

    attachments = {}
    for kind, accessor, rows_key in (
        ("redirect", "get_redirects", "services"),
        ("upstream", "get_upstreams", "services"),
        ("certificate", "get_certificates", "attachments"),
        ("workflow", "get_workflows", "services"),
    ):
        for resource in getattr(db, accessor)(limit=500)["items"]:
            for entry in resource.get(rows_key) or ():
                service = entry.get("service_id") if isinstance(entry, dict) else entry
                if service:
                    attachments.setdefault(service, []).append({"type": kind})
    return custom_configs, attachments


def _classify(db, snapshot, service):
    custom_configs, attachments = _evidence(db)
    return classify(
        split_services(snapshot)[service],
        custom_configs=custom_configs.get(service, ()),
        attachments=attachments.get(service, ()),
    )


def test_capability_defaults_holds_exactly_one_entry():
    """ADR §5bis (:131-136): an entry belongs here ONLY when the default IS a capability.

    `SERVE_FILES=yes` serves the document root, so it is one. The ten other `_NO`-allowlisted
    settings that also default to "yes" -- USE_MODSECURITY, USE_MODSECURITY_CRS,
    USE_MODSECURITY_CRS_PLUGINS, USE_WHITELIST, USE_BLACKLIST, USE_DNSBL, USE_BUNKERNET,
    USE_BAD_BEHAVIOR, USE_LIMIT_REQ, USE_LIMIT_CONN -- default to yes as PROTECTION, not as a
    capability to serve anything, so a service that only redirects and inherits the WAF defaults is
    still redirect-only. Adding them was proposed during this lane's review and OVERRULED
    (coordinator, 2026-09-10): the ADR says an entry must not be added "merely because the default
    is a non-allowlisted value -- otherwise every setting in BunkerWeb would need one".

    This pins the decision, not the mechanism: `test_capability_defaults_match_the_real_plugin_defaults`
    already validates the entries that ARE here. Changing this dict changes what customers are
    billed, so it changes with a PO ruling and an `ALLOWLIST_VERSION` bump, never quietly.
    """
    assert CAPABILITY_DEFAULTS == {"SERVE_FILES": "yes"}


# --------------------------------------------------------------------------------------
# 1. An incompatible declaration is WRITTEN, and then BILLED.
# --------------------------------------------------------------------------------------
def test_a_declared_redirect_only_service_that_still_proxies_is_billed(multisite_db):
    """No write-time refusal exists on this path, and that is the design: the generic write paths
    stay generic and the classifier is the backstop. So the save must succeed AND the result must
    be billed -- if either half flips, an operator buys a free service with one setting."""
    snapshot = _write(
        multisite_db,
        [REDIRECT_SERVICE],
        **_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY, USE_REVERSE_PROXY="yes"),
    )

    assert snapshot[f"{REDIRECT_SERVICE}_SERVICE_MODE"] == MODE_REDIRECT_ONLY, "the declaration must really be persisted"
    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) == INVALID
    assert count_snapshot(snapshot).billable == 1, "an invalid declaration is billed (fail closed)"


# --------------------------------------------------------------------------------------
# 2. A redirect profile is NOT an exemption until it is declared.
# --------------------------------------------------------------------------------------
def test_a_redirect_profile_left_at_standard_is_billed_but_reported_as_a_candidate(multisite_db):
    """The one genuinely new fact lot D adds: the service is billed (nothing is ever inferred from
    `REDIRECT_TO`), and the audit says so -- it would qualify IF it were declared."""
    snapshot = _write(multisite_db, [REDIRECT_SERVICE], **_redirect_profile(REDIRECT_SERVICE))

    assert f"{REDIRECT_SERVICE}_SERVICE_MODE" not in snapshot, "nothing declared it"
    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) == BILLABLE
    # Asked with the gate OPEN, or the assertion above is unfalsifiable: a shut gate answers
    # `billable` for a valid declaration too, so it cannot tell "not declared" from "not live".
    with _gate_open():
        assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) == BILLABLE, "the exemption must never be inferred from REDIRECT_TO"

    custom_configs, attachments = _evidence(multisite_db)
    counterfactual = dict(split_services(snapshot)[REDIRECT_SERVICE], SERVICE_MODE=MODE_REDIRECT_ONLY)
    assert explain(counterfactual, custom_configs=custom_configs.get(REDIRECT_SERVICE, ()), attachments=attachments.get(REDIRECT_SERVICE, ())) == []


# --------------------------------------------------------------------------------------
# 3. A bulk save mixing a valid and an invalid declaration.
# --------------------------------------------------------------------------------------
def test_one_bulk_save_carrying_a_valid_and_an_invalid_declaration(multisite_db):
    """Both rows land, and the snapshot the real save produced splits exactly the way the
    pure-function `test_count_over_a_mapping` predicts for synthetic input."""
    payload = {}
    payload.update(_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY))
    payload.update(_redirect_profile(PROXY_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY, USE_REVERSE_PROXY="yes"))

    snapshot = _write(multisite_db, [REDIRECT_SERVICE, PROXY_SERVICE], **payload)

    assert _classify(multisite_db, snapshot, PROXY_SERVICE) == INVALID
    custom_configs, attachments = _evidence(multisite_db)
    counts = count_snapshot(snapshot, custom_configs=custom_configs, attachments=attachments)
    assert counts.total == 2
    assert counts.invalid == 1
    # The valid one is STILL billed: the exemption is gated off, so `billable` is 2, not 1.
    assert counts.billable == 2 and counts.exempt_redirect == 0
    assert EXEMPTION_ENABLED is False, "flipping the gate makes the two assertions above wrong -- read the ADR first"


def test_a_custom_snippet_saved_against_the_service_invalidates_it(multisite_db):
    """The snippet lives in `bw_custom_configs`, not in the settings: a classification that reads
    only the config cannot see it, which is why every call site has to pass it (ADR §3bis)."""
    snapshot = _write(multisite_db, [REDIRECT_SERVICE], **_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY))
    add_custom_config_row(multisite_db, service_id=REDIRECT_SERVICE, type="server_http", name="extra")

    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) == INVALID


# --------------------------------------------------------------------------------------
# 4. Resource indirection: an attachment, through the real attach path.
# --------------------------------------------------------------------------------------
def test_an_attached_upstream_invalidates_the_declaration(multisite_db):
    """An upstream pool is proxying by another name, and it is ATTACHED rather than configured --
    so the service's own settings stay a clean redirect profile while it proxies. This is the
    circumvention the attachment evidence exists to close."""
    snapshot = _write(multisite_db, [REDIRECT_SERVICE], **_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY))
    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) != INVALID, "the settings alone are a valid profile"

    resource_id, error = multisite_db.create_upstream(name="pool", servers=[{"host": "10.0.0.1:8080"}])
    assert not error, error
    assert not multisite_db.attach_upstream(resource_id, REDIRECT_SERVICE, match_path="/api")

    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) == INVALID


def test_an_attached_redirect_resource_does_not_invalidate_anything(multisite_db):
    """The other direction, so the test above is about the TYPE and not about attachments at all:
    `redirect` and `certificate` are on `ALLOWED_ATTACHMENT_TYPES`."""
    snapshot = _write(multisite_db, [REDIRECT_SERVICE], **_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY))

    resource_id, error = multisite_db.create_redirect(name="legacy", from_path="/old", to_url="https://new.example.com")
    assert not error, error
    assert not multisite_db.attach_redirect(resource_id, REDIRECT_SERVICE)

    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) != INVALID


# --------------------------------------------------------------------------------------
# 5. A template layer, on real persisted data.
# --------------------------------------------------------------------------------------
def test_declaring_a_template_at_all_invalidates_the_declaration(multisite_db):
    """Template CONTENT is never resolved by the classifier, so the refusal has to come from the
    PRESENCE of `USE_TEMPLATE` (ADR Consequences #2). Pinned on a real persisted layer, because
    "the rule is about presence" is only true if the row is what trips it."""
    snapshot = _write(
        multisite_db,
        [REDIRECT_SERVICE],
        **_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY, USE_TEMPLATE="low"),
    )

    assert snapshot[f"{REDIRECT_SERVICE}_USE_TEMPLATE"] == "low"
    assert f"{REDIRECT_SERVICE}_USE_REVERSE_PROXY" not in snapshot, "the layer's content is NOT resolved into the snapshot"
    assert _classify(multisite_db, snapshot, REDIRECT_SERVICE) == INVALID
    reasons = explain(dict(split_services(snapshot)[REDIRECT_SERVICE]))
    # USE_TEMPLATE, not USE_REVERSE_PROXY: the layer really carries a reverse proxy and the
    # classifier cannot see it. Declaring the layer is what trips the refusal.
    assert any("USE_TEMPLATE" in reason for reason in reasons)
    assert not any("USE_REVERSE_PROXY" in reason for reason in reasons)


# --------------------------------------------------------------------------------------
# 6. PO ruling 2026-09-10: the exemption is a PRO count and NOTHING else.
# --------------------------------------------------------------------------------------
def test_a_conversion_changes_no_count_but_the_pro_one(multisite_db):
    """ "Redirect-only services are not counted as services" applies ONLY to the PRO counts.
    Everywhere else -- the services list, the online/draft split, quotas, dashboards, metrics --
    a redirect-only service is a full service. So converting one may move `billable` /
    `exempt_redirect` and nothing else."""
    before = _write(multisite_db, [REDIRECT_SERVICE, PROXY_SERVICE], **_redirect_profile(REDIRECT_SERVICE))
    counts_before = count_snapshot(before)
    roster_before = sorted(before["SERVER_NAME"].split())
    services_before = {row["id"]: (row["method"], row["is_draft"]) for row in multisite_db.get_services(with_drafts=True)}

    after = _write(
        multisite_db,
        [REDIRECT_SERVICE, PROXY_SERVICE],
        **_redirect_profile(REDIRECT_SERVICE, SERVICE_MODE=MODE_REDIRECT_ONLY),
    )
    counts_after = count_snapshot(after)

    assert after[f"{REDIRECT_SERVICE}_SERVICE_MODE"] == MODE_REDIRECT_ONLY, "the conversion really happened"
    assert sorted(after["SERVER_NAME"].split()) == roster_before, "the service must stay in the roster"
    assert {row["id"]: (row["method"], row["is_draft"]) for row in multisite_db.get_services(with_drafts=True)} == services_before
    assert counts_after.total == counts_before.total
    assert counts_after.draft == counts_before.draft
    # And, while the gate is shut, not even the PRO count moves.
    assert counts_after.billable == counts_before.billable
    assert EXEMPTION_ENABLED is False
