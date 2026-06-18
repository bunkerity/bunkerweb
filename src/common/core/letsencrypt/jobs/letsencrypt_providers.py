# -*- coding: utf-8 -*-
"""DNS provider translation layer for certbot-dns-multi.

BunkerWeb used to ship ~29 hand-written Pydantic provider classes, each driving a
dedicated ``certbot-dns-<provider>`` plugin. They are replaced by the single
``certbot-dns-multi`` certbot plugin, which embeds lego's DNS providers. This module
turns the operator-facing provider name + credential items into a ``dns-multi``
credentials INI body of the form::

    dns_multi_provider = <lego_code>
    <LEGO_ENV_KEY> = <value>
    ...

certbot-dns-multi exports every INI key (except ``dns_multi_provider``) verbatim as an
environment variable to lego, so credentials, route53 AWS keys, and lego tuning knobs
all travel through the same file.

Two vendored data files drive the translation (both in ``lego/`` next to this module):

* ``lego_providers.json`` — generated from lego's TOML metadata (see
  ``src/deps/misc/gen_lego_providers.py``); the authoritative list of lego codes and the
  env-var names each accepts.
* ``legacy_aliases.json`` — hand-authored backward-compat map: the historical BunkerWeb
  provider names and their legacy credential-item key spellings → lego code + lego env
  names (incl. the 5 name remaps and the ionos/rfc2136/google special cases).
"""

from json import dumps as json_dumps, loads as json_loads
from pathlib import Path
from typing import Dict, Optional, Tuple

from common_utils import bytes_hash  # type: ignore

_LEGO_DIR = Path(__file__).resolve().parent / "lego"


def _load_json(name: str) -> dict:
    with (_LEGO_DIR / name).open("r", encoding="utf-8") as fh:
        data = json_loads(fh.read())
    data.pop("_meta", None)
    return data


# lego_code -> {"name", "credentials_env": [...], "additional_env": [...]}
LEGO_PROVIDERS: Dict[str, dict] = _load_json("lego_providers.json")
# legacy BunkerWeb provider name -> {"lego_code", "cred_key_map", "required", "defaults", "special", ...}
LEGACY_ALIASES: Dict[str, dict] = _load_json("legacy_aliases.json")

# Every value the LETS_ENCRYPT_DNS_PROVIDER setting may take: all lego codes plus the
# historical BunkerWeb names that remap to a different code (cloudflare, google, ...).
SUPPORTED_PROVIDER_INPUTS = frozenset(LEGO_PROVIDERS) | frozenset(LEGACY_ALIASES)


def resolve_lego_code(provider_input: str) -> Optional[str]:
    """Resolve an operator-facing provider name to its lego code, or ``None`` if unknown.

    Legacy BunkerWeb names map through ``legacy_aliases.json`` (5 of them remap, e.g.
    ``google`` -> ``gcloud``); any value that is already a lego code is returned as-is.
    """
    if not provider_input:
        return None
    alias = LEGACY_ALIASES.get(provider_input)
    if alias:
        return alias["lego_code"]
    if provider_input in LEGO_PROVIDERS:
        return provider_input
    return None


def is_supported_provider(provider_input: str) -> bool:
    """True when ``provider_input`` resolves to a known lego code."""
    return resolve_lego_code(provider_input) is not None


def is_base64_skip_code(lego_code: Optional[str]) -> bool:
    """True for providers whose secrets are legitimately base64 and must not be decoded.

    rfc2136 (lego code ``dnsupdate``) TSIG secrets are base64 payloads.
    """
    return lego_code == "dnsupdate"


def _known_env(lego_code: str) -> frozenset:
    entry = LEGO_PROVIDERS.get(lego_code, {})
    return frozenset(entry.get("credentials_env", [])) | frozenset(entry.get("additional_env", []))


def provider_display_name(lego_code: str) -> str:
    return LEGO_PROVIDERS.get(lego_code, {}).get("name", lego_code)


class DnsMultiProvider:
    """A resolved set of lego credentials for the certbot-dns-multi authenticator.

    ``env`` holds ``{LEGO_ENV_KEY: value}`` pairs written to the credentials INI.
    ``sidecars`` holds ``{basename: (content_bytes, env_key)}`` for providers that need a
    companion file (currently only google service-account JSON -> GCE_SERVICE_ACCOUNT_FILE);
    the caller (certbot-new.py) materialises each sidecar into the cache dir and rewrites
    ``env[env_key]`` to the absolute path before the INI is written.
    """

    __slots__ = ("lego_code", "env", "sidecars")

    def __init__(self, lego_code: str, env: Dict[str, str], sidecars: Optional[Dict[str, Tuple[bytes, str]]] = None):
        self.lego_code = lego_code
        self.env = dict(env)
        self.sidecars = dict(sidecars or {})

    def get_formatted_credentials(self) -> bytes:
        """Return the dns-multi credentials INI body (deterministic key order for stable hashing)."""
        lines = [f"dns_multi_provider = {self.lego_code}"]
        for key in sorted(self.env):
            lines.append(f"{key} = {self.env[key]}")
        return "\n".join(lines).encode("utf-8")

    @staticmethod
    def get_file_type() -> str:
        """certbot-dns-multi always reads an INI credentials file."""
        return "ini"

    def __repr__(self) -> str:
        # Never expose secret values in logs/debug output.
        redacted = {k: ("***" if v not in ("", None) else v) for k, v in self.env.items()}
        return f"DnsMultiProvider(lego_code={self.lego_code!r}, env={redacted!r}, sidecars={sorted(self.sidecars)!r})"


def _apply_ionos_combine(env: Dict[str, str]) -> None:
    """lego's ionos provider takes a single ``IONOS_API_KEY`` of the form ``<prefix>.<secret>``."""
    prefix = env.pop("__IONOS_PREFIX", "")
    secret = env.pop("__IONOS_SECRET", "")
    if prefix and secret and not env.get("IONOS_API_KEY"):
        env["IONOS_API_KEY"] = f"{prefix}.{secret}"


def _apply_rfc2136_port(env: Dict[str, str]) -> None:
    """lego's dnsupdate provider folds the port into ``DNSUPDATE_NAMESERVER`` (``host:port``)."""
    port = env.pop("__RFC2136_PORT", "")
    nameserver = env.get("DNSUPDATE_NAMESERVER", "")
    if port and nameserver and ":" not in nameserver:
        env["DNSUPDATE_NAMESERVER"] = f"{nameserver}:{port}"


def _apply_google_sa(spec: dict, credential_items: Dict[str, str], env: Dict[str, str]) -> Dict[str, Tuple[bytes, str]]:
    """Reassemble a legacy inline google service-account into a JSON sidecar file.

    lego's gcloud provider cannot read inline service-account fields; it reads
    ``GCE_SERVICE_ACCOUNT_FILE`` (a path) or ``GCE_SERVICE_ACCOUNT`` (raw JSON). An inline
    JSON value cannot live in the INI safely (certbot's configobj parser splits commas), so
    the legacy per-field credentials are rebuilt into a JSON document written to a 0o600
    sidecar; ``env["GCE_SERVICE_ACCOUNT_FILE"]`` is finalised by the caller to the cache path.
    """
    sa: Dict[str, str] = {}
    for canonical, aliases in spec.get("sa_key_map", {}).items():
        for alias in aliases:
            if alias in credential_items:
                sa[canonical] = credential_items[alias]
                break

    # No inline service-account material -> the operator supplied GCE_* directly (passthrough).
    if "private_key" not in sa and "client_email" not in sa:
        return {}

    for default_key, default_value in spec.get("sa_defaults", {}).items():
        sa.setdefault(default_key, default_value)

    if env.get("GCE_PROJECT"):
        sa["project_id"] = env["GCE_PROJECT"]
    elif sa.get("project_id"):
        env["GCE_PROJECT"] = sa["project_id"]

    content = json_dumps(sa, indent=2).encode("utf-8")
    basename = f"gce_service_account_{bytes_hash(content, algorithm='sha256')[:12]}.json"
    return {basename: (content, "GCE_SERVICE_ACCOUNT_FILE")}


def translate_credentials(
    lego_code: str,
    provider_input: str,
    credential_items: Dict[str, str],
    logger=None,
) -> Optional[DnsMultiProvider]:
    """Translate parsed credential items into a :class:`DnsMultiProvider`, or ``None`` on failure.

    For historical providers, ``legacy_aliases.json`` maps each known legacy key spelling to
    its lego env-var name (and raw lego env names are also accepted). For new providers, keys
    pass through uppercased (they are already lego env-var names). Required env vars declared
    for legacy providers are checked so a misconfiguration fails early instead of at issuance.
    """
    spec = LEGACY_ALIASES.get(provider_input)
    env: Dict[str, str] = {}
    sidecars: Dict[str, Tuple[bytes, str]] = {}

    if spec:
        known = _known_env(lego_code)
        cred_map = spec.get("cred_key_map", {})
        for key, value in credential_items.items():
            if key in cred_map:
                env[cred_map[key]] = value
            elif key.upper() in known:
                # Operators may also use raw lego env-var names with a legacy provider name.
                env[key.upper()] = value
            # Unknown keys for a known legacy provider are ignored (not silently passed to lego).

        for default_key, default_value in spec.get("defaults", {}).items():
            env.setdefault(default_key, default_value)

        special = spec.get("special")
        if special == "ionos_combine":
            _apply_ionos_combine(env)
        elif special == "rfc2136_port":
            _apply_rfc2136_port(env)
        elif special == "google_sa":
            sidecars = _apply_google_sa(spec, credential_items, env)

        missing = [var for var in spec.get("required", []) if not env.get(var)]
        if missing:
            if logger is not None:
                logger.error(f"Missing required credential(s) for provider '{provider_input}' " f"({provider_display_name(lego_code)}): {', '.join(missing)}.")
            return None
    else:
        # New lego provider configured directly: keys are already lego env-var names.
        for key, value in credential_items.items():
            env[key.upper()] = value

    # Drop any internal sentinels that a special handler did not consume.
    env = {key: value for key, value in env.items() if not key.startswith("__")}

    if not env and not sidecars:
        return None

    return DnsMultiProvider(lego_code, env, sidecars)
