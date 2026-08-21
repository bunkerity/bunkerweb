#!/usr/bin/env python3
"""Settings resolution for the per-service CrowdSec configuration.

Every CROWDSEC_* setting is context=multisite, so each service resolves its own
value: the ``{service}_NAME`` key when it exists, the unprefixed key otherwise, and
finally the plugin default. Kept free of BunkerWeb imports so it can be unit tested
on its own; callers pass ``os.getenv`` (never a ``from os import environ`` binding,
which freezes on a start-time snapshot of the job environment).
"""

# Template variable -> plugin.json default
SETTINGS = {
    "CROWDSEC_API": "http://crowdsec:8080",
    "CROWDSEC_API_KEY": "",
    "CROWDSEC_MODE": "live",
    "CROWDSEC_ENABLE_INTERNAL": "no",
    "CROWDSEC_REQUEST_TIMEOUT": "1000",
    "CROWDSEC_EXCLUDE_LOCATION": "",
    "CROWDSEC_CACHE_EXPIRATION": "1",
    "CROWDSEC_UPDATE_FREQUENCY": "10",
    "CROWDSEC_APPSEC_URL": "",
    "CROWDSEC_APPSEC_FAILURE_ACTION": "passthrough",
    "CROWDSEC_APPSEC_CONNECT_TIMEOUT": "100",
    "CROWDSEC_APPSEC_SEND_TIMEOUT": "100",
    "CROWDSEC_APPSEC_PROCESS_TIMEOUT": "500",
    "CROWDSEC_ALWAYS_SEND_TO_APPSEC": "no",
    "CROWDSEC_APPSEC_SSL_VERIFY": "no",
}

# Rendered as the true/false literals the bouncer config parser expects
BOOLEAN_SETTINGS = frozenset(
    {
        "CROWDSEC_ENABLE_INTERNAL",
        "CROWDSEC_ALWAYS_SEND_TO_APPSEC",
        "CROWDSEC_APPSEC_SSL_VERIFY",
    }
)


def get_setting(getenv, name: str, service: str = "", default: str = "") -> str:
    """Resolve one setting for one service, falling back to global then to default."""
    if service:
        value = getenv(f"{service}_{name}")
        if value is not None:
            return value
    return getenv(name, default)


def get_services(getenv):
    """Return (enabled, disabled) service ids.

    In multisite a service id is the server name; otherwise the whole instance is the
    single service with an empty id, which is also the empty ``service_id`` the job
    cache uses for instance-wide files.
    """
    if getenv("MULTISITE", "no") != "yes":
        if get_setting(getenv, "USE_CROWDSEC", default="no") == "yes":
            return [""], []
        return [], []

    enabled, disabled = [], []
    for server in getenv("SERVER_NAME", "").strip().split():
        if get_setting(getenv, "USE_CROWDSEC", server, "no") == "yes":
            enabled.append(server)
        else:
            disabled.append(server)
    return enabled, disabled


def render_variables(getenv, service: str = ""):
    """Template variables for one service's crowdsec.conf."""
    variables = {}
    for name, default in SETTINGS.items():
        value = get_setting(getenv, name, service, default)
        if name in BOOLEAN_SETTINGS:
            value = "true" if value == "yes" else "false"
        variables[name] = value
    return variables
