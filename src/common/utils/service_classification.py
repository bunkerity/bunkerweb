#!/usr/bin/env python3
"""Central quota classification for BunkerWeb services (PRO accounting).

One shared, pure module so the API, the UI, the Scheduler, the PRO license job
and any audit report answer the SAME number. See the "Services de redirection
et comptabilisation PRO" conception (Outline ``As4MVahtAJ``) and the ADR at
``docs/superpowers/specs/2026-08-24-service-mode-classification-adr.md``.

Commercial rule (validated by the PO): a service explicitly declared
``SERVICE_MODE=redirect_only`` and carrying **nothing but** a redirect profile
is exempt from the PRO quota, without a cap on how many of them exist. The
exemption is never inferred — in particular it is NEVER derived from
``REDIRECT_TO``, which is location-scoped and reachable from templates,
external plugins and attachable resources.

Four classes, per the conception::

    draft            -- IS_DRAFT=yes, never serves traffic, never counted
    billable         -- an ordinary (standard or mixed) service
    exempt_redirect  -- a VALID redirect_only service, consumes no quota
    invalid          -- declared redirect_only but carrying a forbidden
                        capability; billed (fail closed, "défaut billable")

**The exemption is gated off** until Lot C -- see ``EXEMPTION_ENABLED``. The rule
below is complete and tested, but ``classify()`` returns ``billable`` where it
would return ``exempt_redirect``, so today's counts are identical to the counts
before any of this existed.

``ServiceCounts.billable`` is the number to send to the license path and to
show as "services consumed": it is ``standard + invalid``. ``invalid`` is
reported separately so the operator can see *why* a service is being billed.

Input contract
--------------
Classification runs on the **normalized persisted configuration**, never on
form input: the caller passes what the database actually holds for a service,
i.e. the output of ``Database.get_non_default_settings()`` (or the API's
``GET /global_settings?global_only=false``), NOT the fully-defaulted
``get_config()`` snapshot. A key that is absent means "left at its default";
a key that is present means the operator (or a global override) set it.

Values may be plain strings or the ``methods=True`` mapping
``{"value": ..., "method": ..., ...}`` — both shapes are accepted.

The allowlist is DATA, versioned by ``ALLOWLIST_VERSION``. Widening it is a
one-line change plus a version bump; it is deliberately not a heuristic.
"""

from re import compile as re_compile
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Union

# Bump on ANY change to the allowlist below. The pair (algorithm, allowlist) is
# what makes two components provably agree, and what the license contract will
# eventually carry (open PO decision #2 — see the ADR).
ALLOWLIST_VERSION = "1"
ALGORITHM_VERSION = "1"

# The exemption is NOT live yet, and this flag is what makes that a fact rather
# than a claim. Lot C owns the write path (a dedicated form that refuses an
# incompatible capability before it is applied) AND the evidence plumbing --
# every call site passing the service's custom configs and attached resources.
# Until both exist, `classify()` never returns `exempt_redirect`: a declaration
# that holds up is still billed, so wiring the counters is a PURE REFACTOR with
# provably identical numbers, and a custom NGINX snippet nobody passed cannot
# buy a free service. The rule and its tests are complete underneath; Lot C
# flips this to True in the same commit that supplies the evidence.
EXEMPTION_ENABLED = False

SERVICE_MODE_SETTING = "SERVICE_MODE"
MODE_STANDARD = "standard"
MODE_REDIRECT_ONLY = "redirect_only"
SERVICE_MODES = (MODE_STANDARD, MODE_REDIRECT_ONLY)

DRAFT = "draft"
BILLABLE = "billable"
EXEMPT_REDIRECT = "exempt_redirect"
INVALID = "invalid"

# Resource kinds (bw_resources.type) an exempt redirect service may carry.
# "upstream" is proxying and "workflow" is a security capability -> forbidden.
ALLOWED_ATTACHMENT_TYPES = frozenset({"certificate", "redirect"})

_ANY: Optional[frozenset] = None  # allowlist entry: any value is acceptable
_NO = frozenset({"no"})  # tolerated only in the capability-DISABLING direction

# --------------------------------------------------------------------------
# Allowlist v1 — every key a redirect_only service may carry, explicitly.
#
# Mapping: setting id -> allowed values, or ``_ANY`` for "any value".
# A key absent from this mapping is a forbidden capability, which is what makes
# an UNKNOWN external plugin setting fall through to "billable" by default.
#
# The ``_NO`` entries exist so that *disabling* an optional plugin on a redirect
# service (a perfectly reasonable thing to do, and a thing an operator may well
# do globally) never costs the exemption, while *enabling* it does.
# --------------------------------------------------------------------------
ALLOWED_SETTINGS: Dict[str, Optional[frozenset]] = {
    # -- entry identity ----------------------------------------------------
    "SERVER_NAME": _ANY,
    SERVICE_MODE_SETTING: _ANY,
    "IS_DRAFT": _ANY,
    # Mode flags that cannot add a serving capability.
    "SECURITY_MODE": _ANY,
    # Redirect is an HTTP-only plugin ("stream": "no" in redirect/plugin.json),
    # so the type is pinned. Pinning it here is what makes the stream listener
    # settings below inert rather than a hole.
    "SERVER_TYPE": frozenset({"http"}),
    # -- redirect contract (target / code / path-query conservation) -------
    "REDIRECT_FROM": _ANY,
    "REDIRECT_TO": _ANY,
    "REDIRECT_TO_REQUEST_URI": _ANY,
    "REDIRECT_TO_STATUS_CODE": _ANY,
    # -- listener ----------------------------------------------------------
    "LISTEN_HTTP": _ANY,
    # Multisite since the per-service listen ports landed: without these two a
    # redirect service that just moves to another port would be classified
    # `invalid` and start counting against the quota, which a port number has no
    # business doing. A port cannot add a serving capability.
    "HTTP_PORT": _ANY,
    "HTTPS_PORT": _ANY,
    "HTTP2": _ANY,
    "HTTP3": _ANY,
    "HTTP3_ALT_SVC_PORT": _ANY,
    "REDIRECT_HTTP_TO_HTTPS": _ANY,
    "AUTO_REDIRECT_HTTP_TO_HTTPS": _ANY,
    # Inert while SERVER_TYPE is pinned to "http"; listed so that a GLOBAL
    # override of one of them does not disqualify every redirect service.
    "LISTEN_STREAM": _ANY,
    "LISTEN_STREAM_PORT": _ANY,
    "LISTEN_STREAM_PORT_SSL": _ANY,
    "USE_TCP": _ANY,
    "USE_UDP": _ANY,
    # -- TLS ---------------------------------------------------------------
    "SSL_PROTOCOLS": _ANY,
    "SSL_CIPHERS_LEVEL": _ANY,
    "SSL_CIPHERS_CUSTOM": _ANY,
    "SSL_ECDH_CURVE": _ANY,
    "SSL_SESSION_CACHE_SIZE": _ANY,
    "USE_CUSTOM_SSL": _ANY,
    "CUSTOM_SSL_CERT_PRIORITY": _ANY,
    "CUSTOM_SSL_CERT": _ANY,
    "CUSTOM_SSL_KEY": _ANY,
    "CUSTOM_SSL_CERT_DATA": _ANY,
    "CUSTOM_SSL_KEY_DATA": _ANY,
    "GENERATE_SELF_SIGNED_SSL": _ANY,
    "SELF_SIGNED_SSL_ALGORITHM": _ANY,
    "SELF_SIGNED_SSL_EXPIRY": _ANY,
    "SELF_SIGNED_SSL_SUBJ": _ANY,
    # -- ACME / Let's Encrypt (whole plugin: certificate issuance only) -----
    "AUTO_LETS_ENCRYPT": _ANY,
    "LETS_ENCRYPT_PASSTHROUGH": _ANY,
    "EMAIL_LETS_ENCRYPT": _ANY,
    "LETS_ENCRYPT_SERVER": _ANY,
    "LETS_ENCRYPT_ZEROSSL_API_KEY": _ANY,
    "LETS_ENCRYPT_ZEROSSL_API_RETRY": _ANY,
    "LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY": _ANY,
    "LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT": _ANY,
    "LETS_ENCRYPT_ZEROSSL_API_MAX_TIME": _ANY,
    "LETS_ENCRYPT_CHALLENGE": _ANY,
    "LETS_ENCRYPT_DNS_PROVIDER": _ANY,
    "LETS_ENCRYPT_DNS_PROPAGATION": _ANY,
    "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM": _ANY,
    "LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64": _ANY,
    "USE_LETS_ENCRYPT_WILDCARD": _ANY,
    "USE_LETS_ENCRYPT_STAGING": _ANY,
    "LETS_ENCRYPT_PROFILE": _ANY,
    "LETS_ENCRYPT_CUSTOM_PROFILE": _ANY,
    "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES": _ANY,
    "LETS_ENCRYPT_MAX_RETRIES": _ANY,
    # -- logs / metrics ----------------------------------------------------
    "USE_METRICS": _ANY,
    # -- capability toggles, DISABLING direction only ----------------------
    # (enabling any of these is exactly what "mixte -> billable" means)
    "USE_REVERSE_PROXY": _NO,
    "USE_GRPC": _NO,
    "SERVE_FILES": _NO,
    "USE_PROXY_CACHE": _NO,
    "USE_OPEN_FILE_CACHE": _NO,
    "USE_AUTH_BASIC": _NO,
    "USE_MTLS": _NO,
    "USE_ANTIBOT": _NO,
    "USE_CORS": _NO,
    "USE_CLIENT_CACHE": _NO,
    "USE_GZIP": _NO,
    "USE_BROTLI": _NO,
    "USE_REAL_IP": _NO,
    "USE_ROBOTSTXT": _NO,
    "USE_SECURITYTXT": _NO,
    "USE_UI": _NO,
    "USE_MODSECURITY": _NO,
    "USE_MODSECURITY_CRS": _NO,
    "USE_MODSECURITY_CRS_PLUGINS": _NO,
    "USE_WHITELIST": _NO,
    "USE_BLACKLIST": _NO,
    "USE_GREYLIST": _NO,
    "USE_DNSBL": _NO,
    "USE_BUNKERNET": _NO,
    "USE_BAD_BEHAVIOR": _NO,
    "USE_CROWDSEC": _NO,
    "USE_REVERSE_SCAN": _NO,
    "USE_LIMIT_REQ": _NO,
    "USE_LIMIT_REQ_GLOBAL": _NO,
    "USE_LIMIT_CONN": _NO,
}

# Settings whose PLUGIN DEFAULT is itself a forbidden capability, so their
# ABSENCE from the persisted config is the violation.
#
# `SERVE_FILES` defaults to "yes": a redirect-only service that never touches it
# still serves the document root on every path its redirect does not cover, and
# "explicitly yes" and "inherited yes" render byte-identical NGINX. Without this
# map the classifier would refuse the explicit one and exempt the inherited one
# — the same service, two answers. A `redirect_only` service must therefore turn
# file serving off explicitly (Lot C's form emits it; the minimal rendering is
# what will make it redundant).
#
# Keep this map minimal: an entry belongs here only when the DEFAULT grants a
# capability, never merely because the default is a non-allowlisted value.
CAPABILITY_DEFAULTS: Dict[str, str] = {"SERVE_FILES": "yes"}

# ``multiple`` settings are persisted as ``KEY_<n>``; the allowlist is keyed by
# the base id. Only a purely numeric suffix is stripped, so ids that merely end
# in a digit (LIMIT_CONN_MAX_HTTP1) keep their name.
_SUFFIX_RX = re_compile(r"^(?P<base>.+?)_(?P<suffix>\d+)$")


class ServiceCounts(NamedTuple):
    """Aggregate consumed by the license path, the UI and audits.

    ``billable`` is THE quota number: standard services plus the redirect
    services whose declaration does not hold up (fail closed). ``standard`` and
    ``invalid`` are broken out so the count stays explainable.
    """

    total: int
    billable: int
    standard: int
    exempt_redirect: int
    invalid: int
    draft: int
    algorithm_version: str = ALGORITHM_VERSION
    allowlist_version: str = ALLOWLIST_VERSION


def base_setting(key: str) -> str:
    """Return the base setting id of ``key`` (``REDIRECT_TO_2`` -> ``REDIRECT_TO``)."""
    match = _SUFFIX_RX.match(key)
    if not match:
        return key
    base = match.group("base")
    # Only treat the suffix as a repetition index when the base is a setting we
    # know; otherwise keep the raw key so an unknown plugin cannot smuggle a
    # forbidden setting in as "<allowed>_1".
    return base if base in ALLOWED_SETTINGS else key


def setting_value(entry: Any) -> str:
    """Normalize one config entry to its string value.

    Accepts the plain ``methods=False`` value and the ``methods=True`` mapping.
    """
    if isinstance(entry, Mapping):
        entry = entry.get("value", "")
    return "" if entry is None else str(entry).strip()


def _forbidden(
    service_config: Mapping[str, Any],
    custom_configs: Iterable[Any],
    attachments: Iterable[Any],
) -> List[str]:
    """Return the reasons ``service_config`` cannot be an exempt redirect."""
    reasons: List[str] = []
    has_target = False

    for key, entry in service_config.items():
        base = base_setting(key)
        allowed = ALLOWED_SETTINGS.get(base, ...)
        value = setting_value(entry)
        if base == "REDIRECT_TO" and value:
            has_target = True
        if allowed is ...:
            reasons.append(f"setting {key} is not on redirect-only allowlist v{ALLOWLIST_VERSION}")
        elif allowed is not None and value not in allowed:
            reasons.append(f"setting {key}={value!r} is only allowed as {'|'.join(sorted(allowed))}")

    # A capability that arrives by default never appears in the persisted config,
    # so it has to be evaluated from its absence.
    for key, default in CAPABILITY_DEFAULTS.items():
        # Membership is checked on the RAW key, never the suffix-stripped base:
        # `SERVE_FILES_2` is not a repetition of anything (SERVE_FILES is not a
        # `multiple` setting), so it must not read as "SERVE_FILES was set" and
        # leave the real default unevaluated.
        if key in service_config:
            continue
        allowed = ALLOWED_SETTINGS.get(key, ...)
        if allowed is ...:
            reasons.append(f"setting {key} is absent and defaults to {default!r}, which is not on redirect-only allowlist v{ALLOWLIST_VERSION}")
        elif allowed is not None and default not in allowed:
            reasons.append(f"setting {key} is absent and defaults to {default!r}, which is only allowed as {'|'.join(sorted(allowed))}")

    # A redirect service with no target redirects nothing: it would be a free
    # parking slot. The conception's profile makes the target part of the
    # contract, so its absence invalidates the declaration.
    if not has_target:
        reasons.append("no REDIRECT_TO target set")

    # Conception, anti-contournement: custom NGINX snippets are FORBIDDEN on a
    # redirect-only service (the "most verifiable" of the two options).
    custom_config_count = sum(1 for _ in custom_configs)
    if custom_config_count:
        reasons.append(f"{custom_config_count} custom config(s) attached")

    for attachment in attachments:
        kind = attachment.get("type", "") if isinstance(attachment, Mapping) else str(attachment)
        if kind not in ALLOWED_ATTACHMENT_TYPES:
            reasons.append(f"resource attachment of type {kind!r} is not allowed")

    return reasons


def explain(
    service_config: Mapping[str, Any],
    *,
    custom_configs: Iterable[Any] = (),
    attachments: Iterable[Any] = (),
) -> List[str]:
    """Return why a ``redirect_only`` declaration is refused (empty = valid).

    Meaningless on a service that is not declared ``redirect_only``; callers
    should look at :func:`classify` first.
    """
    return _forbidden(service_config, custom_configs, attachments)


def classify(
    service_config: Mapping[str, Any],
    *,
    custom_configs: Iterable[Any] = (),
    attachments: Iterable[Any] = (),
) -> str:
    """Classify ONE service: ``draft``/``billable``/``exempt_redirect``/``invalid``.

    ``service_config`` is that service's normalized persisted settings, keyed by
    unprefixed setting id (see the module docstring for the input contract).
    ``custom_configs`` and ``attachments`` are the service's custom NGINX
    snippets and attached resources; a caller that cannot supply them gets a
    classification that trusts the settings alone — which is exactly why
    ``EXEMPTION_ENABLED`` is False and no service is exempt yet.
    """
    if setting_value(service_config.get("IS_DRAFT", "no")) == "yes":
        return DRAFT

    mode = setting_value(service_config.get(SERVICE_MODE_SETTING, MODE_STANDARD)) or MODE_STANDARD
    if mode != MODE_REDIRECT_ONLY:
        # Unknown mode values are not a third class: anything that is not an
        # explicit redirect_only declaration is an ordinary service.
        return BILLABLE

    if _forbidden(service_config, custom_configs, attachments):
        return INVALID
    # See EXEMPTION_ENABLED: a declaration that holds up is still billed until
    # Lot C supplies the evidence every call site currently omits.
    return EXEMPT_REDIRECT if EXEMPTION_ENABLED else BILLABLE


def count(
    services: Union[Mapping[str, Mapping[str, Any]], Iterable[Mapping[str, Any]]],
    *,
    custom_configs: Optional[Mapping[str, Iterable[Any]]] = None,
    attachments: Optional[Mapping[str, Iterable[Any]]] = None,
) -> ServiceCounts:
    """Aggregate :func:`classify` over every service.

    ``services`` is either ``{service_name: config}`` or a bare iterable of
    configs. ``custom_configs`` / ``attachments`` are keyed by service name and
    therefore only usable with the mapping form.
    """
    if isinstance(services, Mapping):
        items = list(services.items())
    else:
        items = [(setting_value(config.get("SERVER_NAME", "")).split(" ")[0], config) for config in services]

    totals = {DRAFT: 0, BILLABLE: 0, EXEMPT_REDIRECT: 0, INVALID: 0}
    for name, config in items:
        kind = classify(
            config,
            custom_configs=(custom_configs or {}).get(name, ()),
            attachments=(attachments or {}).get(name, ()),
        )
        totals[kind] += 1

    return ServiceCounts(
        total=len(items),
        # Fail closed: an invalid redirect declaration is billed (conception,
        # "Risques": contournement setting/plugin -> allowlist + défaut billable).
        billable=totals[BILLABLE] + totals[INVALID],
        standard=totals[BILLABLE],
        exempt_redirect=totals[EXEMPT_REDIRECT],
        invalid=totals[INVALID],
        draft=totals[DRAFT],
    )


def split_services(snapshot: Mapping[str, Any], service_names: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Slice a service-prefixed config snapshot into ``{service: settings}``.

    ``snapshot`` is what ``get_non_default_settings(global_only=False)`` returns:
    global rows under their plain id and per-service rows under
    ``<service>_<SETTING>``. Only the prefixed rows are kept — a global-context
    setting is not a service capability, and a multisite setting set globally is
    already propagated per service by that same method.

    Names are matched longest-first so a service whose id is a prefix of another
    cannot steal its keys.
    """
    if service_names is None:
        service_names = setting_value(snapshot.get("SERVER_NAME", "")).split()

    services: Dict[str, Dict[str, Any]] = {name: {} for name in service_names}
    claimed = set()
    # Longest name first, so a service whose id is a prefix of another (domain
    # labels may legally contain "_") cannot claim its sibling's rows.
    for name in sorted(service_names, key=len, reverse=True):
        prefix = f"{name}_"
        for key, entry in snapshot.items():
            if key in claimed or not key.startswith(prefix):
                continue
            claimed.add(key)
            services[name][key.removeprefix(prefix)] = entry
    return services


def count_snapshot(
    snapshot: Mapping[str, Any],
    *,
    custom_configs: Optional[Mapping[str, Iterable[Any]]] = None,
    attachments: Optional[Mapping[str, Iterable[Any]]] = None,
) -> ServiceCounts:
    """:func:`split_services` + :func:`count` — the one-liner every caller wants."""
    return count(split_services(snapshot), custom_configs=custom_configs, attachments=attachments)
