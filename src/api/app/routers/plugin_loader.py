#!/usr/bin/env python3
"""Auto-discovery and mounting of plugin-shipped API routers (BunkerWeb 1.7).

Called once from ``create_app()`` after the core routers are mounted. For every
plugin that declares ``extensions.api`` and passes the security gate (tier trust +
checksum verification for pro/external), its ``api/router.py`` is imported and
mounted at ``/<plugin_id>`` with the standard auth guard + rate limiter injected at
mount time — so a plugin author can never forget authentication.

Defenses:
- Tier/integrity gate (``plugin_extensions.extension_allowed``) runs before the
  plugin's Python is imported.
- Mount prefix is locked to ``/<plugin_id>`` and refused if it collides with an
  existing router — a plugin can never shadow ``/instances``, ``/bans``, etc.
- Per-plugin try/except: one broken plugin logs an error and is simply absent; the
  rest of the API keeps serving.
"""

from fastapi import Depends, FastAPI

from ..auth.guard import guard
from ..rate_limit import limiter_dep_dynamic
from ..utils import LOGGER


def _existing_top_prefixes(app: FastAPI) -> set:
    prefixes = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path:
            prefixes.add("/" + path.lstrip("/").split("/", 1)[0])
    return prefixes


def discover_plugin_routers(app: FastAPI) -> None:
    """Mount every trusted, integrity-verified plugin API router onto ``app``."""
    try:
        from plugin_extensions import (  # type: ignore
            iter_extension_plugins,
            extension_allowed,
            import_plugin_submodule,
            effective_api_prefix,
        )
    except Exception as e:
        LOGGER.error(f"Plugin API extension loader unavailable: {e}")
        return

    try:
        from ..utils import get_db

        db = get_db(log=False)
    except Exception:
        db = None

    existing_prefixes = _existing_top_prefixes(app)

    for ext in iter_extension_plugins(logger=LOGGER):
        if not ext.api or not ext.api.get("module"):
            continue
        if not extension_allowed(ext, db, LOGGER):
            continue

        prefix = effective_api_prefix(ext)
        if prefix in existing_prefixes:
            LOGGER.error(f"Refusing to mount plugin {ext.plugin_id}: prefix {prefix} collides with an existing router")
            continue

        try:
            module = import_plugin_submodule(ext.plugin_id, ext.directory, ext.api["module"])
            router = getattr(module, "router", None)
            if router is None:
                raise ValueError("api module exposes no `router` (expected `router = APIRouter(...)`)")
            app.include_router(router, prefix=prefix, dependencies=[Depends(guard), limiter_dep_dynamic()])
            existing_prefixes.add(prefix)
            LOGGER.info(f"Mounted API extension for plugin {ext.plugin_id} ({ext.plugin_type}) at {prefix}")
        except Exception as e:
            LOGGER.error(f"Failed to mount API extension for plugin {ext.plugin_id}: {e}")
