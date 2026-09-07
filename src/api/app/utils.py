#!/usr/bin/env python3

from os.path import sep
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from regex import compile as re_compile

from app.models.api_database import APIDatabase
from logger import getLogger  # type: ignore
from ports import port_list_setting  # type: ignore
from password_utils import (  # type: ignore  # noqa: F401
    BCRYPT_HASH_RX as BCRYPT_HASH_RX,
    MAX_PASSWORD_BYTES as MAX_PASSWORD_BYTES,
    MIN_BCRYPT_COST as MIN_BCRYPT_COST,
    RECOMMENDED_BCRYPT_COST as RECOMMENDED_BCRYPT_COST,
    USER_PASSWORD_RX as USER_PASSWORD_RX,
    _bcrypt_secret as _bcrypt_secret,
    bcrypt_cost as bcrypt_cost,
    check_password as check_password,
    gen_password_hash as gen_password_hash,
    is_bcrypt_hash as is_bcrypt_hash,
    password_exceeds_bcrypt_limit as password_exceeds_bcrypt_limit,
)

from Database import Database  # type: ignore

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

LOGGER = getLogger("API")

# Cached singletons for pooled DB engines
_DB_INSTANCE: Optional[Database] = None  # type: ignore
_API_DB_INSTANCE = None  # Late-bound type to avoid import cycles


def get_db(*, log: bool = True) -> Database:
    """Return a shared pooled Database instance.

    Creates it on first use; reuses the same engine/session factory afterwards.
    """
    global _DB_INSTANCE
    if _DB_INSTANCE is None or getattr(_DB_INSTANCE, "sql_engine", None) is None:  # type: ignore[attr-defined]
        from Database import Database  # type: ignore

        _DB_INSTANCE = Database(LOGGER, log=log)  # type: ignore
    return _DB_INSTANCE  # type: ignore


def get_api_db(*, log: bool = True) -> APIDatabase:
    """Return a shared pooled APIDatabase instance for API models."""
    global _API_DB_INSTANCE
    if _API_DB_INSTANCE is None or getattr(_API_DB_INSTANCE, "sql_engine", None) is None:  # type: ignore[attr-defined]
        from .models.api_database import APIDatabase

        _API_DB_INSTANCE = APIDatabase(LOGGER, log=log)
    return _API_DB_INSTANCE


def reportable_config(conf: Dict[str, Any], *, methods: bool, service: Optional[str] = None) -> Dict[str, Any]:
    """Reduce a full config to the settings that differ from a fresh install.

    Takes `Database.get_config(methods=True)` output, so a value a template supplies is already
    resolved the way the generator resolves it. `get_non_default_settings` cannot be used for
    this: it reports stored rows only, so a service whose template overrides an inherited global
    value was answered with the global value the generator was about to discard.

    An entry is kept when it is explicitly set (a row exists, so `method` is not the synthetic
    `default`) or when a template supplies it. The rest is the plugin default and stays out.

    The port families are the one thing this view must NARROW rather than report.
    `get_non_default_settings` deliberately refuses to materialise them onto services
    (`db_methods/config_read.py:199-213`) because a service REPLACES the global port list rather
    than extending it (`ports.drop_inherited_ports`), and the presence of a row is the only thing
    that can say "this service declared a port". `get_config` DOES materialise them -- it has to,
    the per-service editor needs them -- and shares the global entry's dict, so an inherited copy
    is recognisable by `global` being true on a service-scoped key. Reporting those copies is not
    cosmetic: the UI hands this snapshot back to `save_config` (bulk draft convert, service
    delete, and saving the global settings page), and `_moved_port_groups`
    (`db_methods/config_save.py:269-334`) reads a partial list as a MOVE and writes every posted
    member -- so a fleet with a second listen port had services silently rebound.

    `IS_DRAFT` is the exception and it is NOT decoration. `get_config` synthesises
    `{service}_IS_DRAFT` from the `bw_services` column under the synthetic method `default`
    (`db_methods/config_read.py:185`), so the rule above would drop it -- and this endpoint is the
    snapshot the UI hands straight back to `save_config` (`src/ui/app/models/config.py:104-127`,
    `src/ui/app/routes/services.py:604-609` and `:694-698`). `save_config` reads an ABSENT
    `{service}_IS_DRAFT` as "not a draft" and actively publishes it
    (`db_methods/config_save.py:1159`, `:1174-1190`), so dropping the key silently un-drafts every
    service the operator did not touch. It is never a plugin default: the row is the only source.
    """
    # DEV-2b5 (Criticos round 2 REQUIRED 1): drop the inherited port copies.
    # The service view has already had its prefix stripped, so every key there is service-scoped;
    # in the global view only the prefixed ones are, and the bare global port keys are `global`
    # too and must stay.
    services = () if service else tuple(sorted(_reported_services(conf), key=len, reverse=True))

    reportable = {}
    for key, data in conf.items():
        if not isinstance(data, dict):
            reportable[key] = data
            continue
        bare = _bare_key(key, service, services)
        if data.get("global") and bare is not None and port_list_setting(bare) is not None:
            continue
        if key.endswith("IS_DRAFT") or data.get("method", "default") != "default" or data.get("template"):
            reportable[key] = data if methods else data["value"]
    return reportable


def _reported_services(conf: Dict[str, Any]) -> List[str]:
    """The server names in a `get_config` answer. `SERVER_NAME` is always set (`config_read.py:300`)."""
    server_name = conf.get("SERVER_NAME")
    if isinstance(server_name, dict):
        server_name = server_name.get("value", "")
    return str(server_name or "").split()


def _bare_key(key: str, service: Optional[str], services: Tuple[str, ...]) -> Optional[str]:
    """The setting id behind a service-scoped key, or None when the key is not service-scoped."""
    if service:
        return key
    # Longest first: service ids may contain `_` (`SERVER_NAME`'s regex allows it), so with `app`
    # and `app_staging` in the roster a shortest-first scan splits `app_staging_HTTP_PORT_1` into
    # the bare key `staging_HTTP_PORT_1`, which matches no port family -- the entry then leaks and
    # the guard is inert for exactly that service.
    for name in services:
        prefix = f"{name}_"
        if key.startswith(prefix):
            return key[len(prefix) :]  # noqa: E203
    return None


# `\Z`, not `$`: `$` also matches before a trailing newline, so `"plugin\n"` would pass and
# become a directory name. Same defect as the config-name regexes. The ".bw-" prefix is the
# instance-side swap's own bookkeeping namespace (`pushswap.RESERVED_PREFIX`): an entry carrying it
# is exempt from the stale-entry sweep, so a plugin named that way survives its own deletion. Kept
# identical to the two live gates (`app/routers/plugins.py`, `src/ui/app/utils.py`) — this copy has
# no importer today and is the one the next author would start from.
PLUGIN_NAME_RX = re_compile(r"^(?!\.bw-)[\w.-]{4,64}\Z")

BISCUIT_PUBLIC_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_public_key")
BISCUIT_PRIVATE_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_private_key")
