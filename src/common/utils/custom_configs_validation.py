#!/usr/bin/env python3
"""Single validator for the six custom-config write sources.

Custom configs (NGINX snippets stored in ``bw_custom_configs``) are written by six
different front doors -- env variables (``[<service>_]CUSTOM_CONF_<TYPE>_<name>``),
Docker labels (``bunkerweb.CUSTOM_CONF_<TYPE>_<name>``), Swarm config objects
(``bunkerweb.CONFIG_TYPE`` / ``bunkerweb.CONFIG_SITE`` labels), Kubernetes ConfigMaps
(``bunkerweb.io/CONFIG_TYPE`` / ``bunkerweb.io/CONFIG_SITE`` annotations), the API, and
the UI -- and before this module each one carried its own copy of the type set and the
name rule, with the env source accepting any name at all
(``src/common/gen/save_config.py``, pre-unification) and Docker labels silently unable
to express the three fleet-global types. This module is the one place that knows the
canonical type set, the name rule, and the (still informational) size cap, so every
source asks the same question and gets the same answer -- see ``report-CC-2.md`` for
the per-source divergence table this replaced.

Two things are intentionally *not* enforced uniformly yet, both by PO decision
(``report-CC-A.md`` AC 6, ``brainstorm-CC.md``):

* The name rule is WARN-only on env, Docker labels, Swarm config objects and Kubernetes
  ConfigMaps (:data:`WARN_ONLY_SOURCES`) -- refusing there would shrink what an
  env-only or autoconf-only install accepts today, which AC 6 forbids for 1.7. It is
  already enforced on the API and UI, where refusal is already the existing behaviour.
  Flipping the four WARN-only sources to refuse is the 1.8 follow-up.
* :data:`MAX_CONFIG_SIZE` is exposed for callers and documentation but ``validate()``
  never refuses on it for any source -- no source enforces a per-config size cap today
  (only the UI's blunt HTTP request-body cap), so adding a refusal here would be new
  behaviour beyond the "no schema, hygiene cut" scope of this lane.
"""

from re import Pattern, compile as re_compile
from typing import NamedTuple, Optional, Tuple

# Canonical form mirrors CUSTOM_CONFIGS_TYPES_ENUM exactly (src/common/db/model.py:35-46,
# read-only -- this module never imports the DB layer, see the import-cycle note below).
CUSTOM_CONFIG_TYPES: Tuple[str, ...] = (
    "http",
    "stream",
    "server_http",
    "server_stream",
    "default_server_http",
    "modsec",
    "modsec_crs",
    "crs_plugins_before",
    "crs_plugins_after",
)
_CUSTOM_CONFIG_TYPES_SET = frozenset(CUSTOM_CONFIG_TYPES)

# A Docker label lives on one container; letting one container's label inject
# fleet-global config (`http`, `stream`, `default_server_http`) would step that
# container up from "declare my own service" to "reconfigure everybody" -- a real
# privilege boundary in a shared-daemon deployment. Swarm config objects and Kubernetes
# ConfigMaps are cluster-scoped objects, not container labels, so they keep all nine
# (report-CC-A.md §4.3, decision confirmed by the PO 2026-09-14: keep the restriction).
DOCKER_LABEL_GLOBAL_TYPES = frozenset({"http", "stream", "default_server_http"})
DOCKER_LABEL_ALLOWED_TYPES: Tuple[str, ...] = tuple(t for t in CUSTOM_CONFIG_TYPES if t not in DOCKER_LABEL_GLOBAL_TYPES)

DOCKER_LABEL_GLOBAL_TYPE_MESSAGE = (
    "Docker labels cannot declare the fleet-global custom config type {type!r}: a label on one container "
    "would affect every service. Use a Swarm config object labelled bunkerweb.CONFIG_TYPE (`docker config "
    "create`), a Kubernetes ConfigMap annotated bunkerweb.io/CONFIG_TYPE, or the API/UI instead."
)

# Same value everywhere on purpose (design AC 2: every source rejects the same input
# with the same message). `\Z`, not `$`: `$` also matches immediately before a trailing
# newline, so a name of "x\n" would pass and become a filename that breaks the
# line-based directory listing used when pushing configs to instances.
NAME_RX: Pattern = re_compile(r"^[\w_-]{1,255}\Z")
NAME_ERROR_MESSAGE = "Invalid name: must match ^[\\w_-]{1,255}\\Z (letters, digits, underscore and hyphen only)"
TYPE_ERROR_MESSAGE = f"Invalid type: must be one of {', '.join(CUSTOM_CONFIG_TYPES)}"

# Informational only -- see the module docstring. Matches the UI's existing
# MAX_CONTENT_LENGTH default (src/ui/main.py), which is a blunt whole-request cap, not
# a per-config one.
MAX_CONFIG_SIZE = 50 * 1024 * 1024  # 50 MB

# The four autoconf/env sources keep accepting what they accept today (AC 6); only the
# API and UI, which already refuse an invalid name, keep refusing.
WARN_ONLY_SOURCES = frozenset({"env", "docker_label", "swarm_config", "configmap"})
ENFORCED_SOURCES = frozenset({"api", "ui"})
KNOWN_SOURCES = WARN_ONLY_SOURCES | ENFORCED_SOURCES


def normalize_type(raw: str) -> Optional[str]:
    """Normalize a config type to its canonical underscore-lowercase form.

    Accepts either separator and any case (the API's pre-unification
    ``normalize_config_type`` did the same). Returns ``None`` when the normalized value
    is not one of the nine canonical types.
    """
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().replace("-", "_").lower()
    return normalized if normalized in _CUSTOM_CONFIG_TYPES_SET else None


def validate_name(name: str) -> Optional[str]:
    """Return an error message for an invalid config name, or ``None`` when it is valid."""
    if not name or not NAME_RX.match(name):
        return NAME_ERROR_MESSAGE
    return None


class ValidationResult(NamedTuple):
    ok: bool
    normalized_type: Optional[str]
    error: Optional[str]
    warning: Optional[str]


def validate(
    config_type: str,
    name: str,
    data: Optional[bytes | str] = None,
    *,
    service_id: Optional[str] = None,
    source: str,
) -> ValidationResult:
    """Validate one custom config the same way for every write source.

    ``source`` is one of :data:`KNOWN_SOURCES` -- ``env``, ``docker_label``,
    ``swarm_config``, ``configmap``, ``api`` or ``ui``. The type check always refuses:
    every source already filters its own type set before reaching here (the env regex's
    alternation, the controllers' ``_supported_config_types`` / label regex, the API's
    pydantic ``ConfigType``), so a type outside the canonical nine is a caller bug, not
    user input. The Docker fleet-global refusal only applies to ``source="docker_label"``.
    The name check is WARN-only on :data:`WARN_ONLY_SOURCES` and refuses on
    :data:`ENFORCED_SOURCES` (see the module docstring for why). ``service_id`` is
    accepted for message context only; it does not change the verdict.
    """
    if source not in KNOWN_SOURCES:
        raise ValueError(f"unknown custom-config validation source: {source!r}")

    suffix = f" (service={service_id})" if service_id else ""

    normalized_type = normalize_type(config_type)
    if normalized_type is None:
        return ValidationResult(False, None, f"{TYPE_ERROR_MESSAGE}{suffix}", None)

    if source == "docker_label" and normalized_type in DOCKER_LABEL_GLOBAL_TYPES:
        return ValidationResult(False, normalized_type, f"{DOCKER_LABEL_GLOBAL_TYPE_MESSAGE.format(type=normalized_type)}{suffix}", None)

    name_error = validate_name(name)
    size_warning = None
    if data is not None:
        size = len(data) if isinstance(data, (bytes, bytearray)) else len(data.encode("utf-8"))
        if size > MAX_CONFIG_SIZE:
            size_warning = f"Config {normalized_type}/{name}{suffix} is {size} bytes, over the informational {MAX_CONFIG_SIZE}-byte cap"

    if name_error:
        if source in ENFORCED_SOURCES:
            return ValidationResult(False, normalized_type, f"{name_error}{suffix}", None)
        warning = f"{name_error}{suffix} -- accepted from {source} for compatibility, will be refused starting in 1.8"
        if size_warning:
            warning = f"{warning}; {size_warning}"
        return ValidationResult(True, normalized_type, None, warning)

    return ValidationResult(True, normalized_type, None, size_warning)


def build_env_style_key_rx(*, with_service_prefix: bool, types: Tuple[str, ...] = CUSTOM_CONFIG_TYPES) -> Pattern:
    """Build a compound ``[<service>_]CUSTOM_CONF_<TYPE>_<name>`` extraction regex.

    Shared by the three parsers that each spell out this pattern by hand: the env
    source (``src/common/gen/save_config.py``), Docker labels
    (``src/autoconf/controllers/DockerController.py``, prefixed with ``bunkerweb.``
    instead of anchored at the string start) and the UI's raw-paste importer
    (``src/ui/app/routes/utils.py``) -- their own comments call out that the env and UI
    copies "have already drifted once". Types are joined longest-first so a prefix
    relationship between two type names (``modsec`` is a prefix of ``modsec_crs``)
    can never make the alternation match the shorter one first and mis-split the name.

    Uses ``\\Z``, not ``$``: ``$`` also matches immediately before a trailing newline, so
    a key ending in ``\\n`` would match and silently alias two different keys onto one
    config.
    """
    alternation = "|".join(sorted((t.upper() for t in types), key=len, reverse=True))
    prefix = r"(?P<service>[0-9a-z\.-]*)_?" if with_service_prefix else ""
    return re_compile(rf"^{prefix}CUSTOM_CONF_(?P<type>{alternation})_(?P<name>.+)\Z")


def build_docker_label_key_rx(types: Tuple[str, ...] = DOCKER_LABEL_ALLOWED_TYPES) -> Pattern:
    """Build the ``bunkerweb.CUSTOM_CONF_<TYPE>_<name>`` Docker label extraction regex.

    Same type-alternation ordering rule as :func:`build_env_style_key_rx`. Defaults to
    the six non-global types (:data:`DOCKER_LABEL_ALLOWED_TYPES`); pass
    :data:`CUSTOM_CONFIG_TYPES` to build the broader pattern used only to *detect* (and
    then explicitly refuse) a label naming one of the three fleet-global types.

    The ``.`` in ``bunkerweb.`` is deliberately left unescaped, matching the original
    ``DockerController`` pattern (AC 6: a WARN-only source keeps accepting exactly what it
    accepted before) -- widening it to a real bug fix is out of scope here.

    One anchor is NOT preserved byte-for-byte: the original pattern ended in ``$``, this one
    in ``\\Z`` (same fix as :func:`build_env_style_key_rx`, applied here for the same reason --
    ``$`` also matches immediately before a trailing newline). This is a real, if vanishingly
    unlikely, narrowing for AC 6: a Docker label key ending in a literal newline byte matched
    before and does not now -- and, because the same anchor also guards the fleet-global
    detection pattern above, it produces no diagnostic either way (Criticos round 1, finding
    (a) on brief-CC-2b.md). Judged acceptable and left as ``\\Z``: the alternative is
    reintroducing, specifically for Docker labels, the exact key-aliasing defect class every
    other guard in this codebase was already swept to close (see
    ``tests/unit/ui/test_name_validation_rejects_trailing_newline.py``).
    """
    alternation = "|".join(sorted((t.upper() for t in types), key=len, reverse=True))
    return re_compile(rf"^bunkerweb.CUSTOM_CONF_(?P<type>{alternation})_(?P<name>.+)\Z")
