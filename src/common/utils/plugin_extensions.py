#!/usr/bin/env python3
"""Discovery and safe loading of plugin-shipped API/DB extensions (BunkerWeb 1.7).

A plugin can extend the control plane by shipping two optional folders next to its
``plugin.json``::

    <plugin>/
      api/router.py   -> must expose ``router = APIRouter(...)``
      db/models.py    -> ``class X(Base): __tablename__ = "bw_<id>_..."``
      db/methods.py   -> optional ``class Database<Plugin>Mixin(DatabaseMixinBase)``

and declaring them explicitly in ``plugin.json``::

    "extensions": {
      "api": { "module": "api/router.py", "prefix": "/<id>" },
      "db":  { "models": "db/models.py", "methods": "db/methods.py", "table_prefix": "bw_<id>_" }
    }

This module is the single discovery point used by the API (router mount + model
registration), the scheduler (model registration before ``create_all``) and the
worker (model registration for job queries). It mirrors the existing safe dynamic
loader used for plugin jobs (``src/worker/executor.py``): collision-proof module
names, a path-traversal guard, and a per-plugin try/except so one bad plugin never
takes down the whole process.

Trust model: ``core`` and ``pro`` plugins are first-party and enabled by default.
``external`` plugins ship third-party Python that would run inside the API process
and define tables in the central DB — a real RCE / schema-poisoning surface — so
their api/db extensions are disabled unless ``PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL=yes``
is set, and even then are checksum-verified against the DB plugin record.
"""

from importlib import import_module
from json import loads
from logging import Logger
from os import getenv, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile
from sys import modules as sys_modules, path as sys_path
from types import ModuleType
from typing import Dict, List, NamedTuple, Optional, Tuple

# Canonical on-disk plugin roots — HARDCODED (mirrors src/worker/executor.py
# ALLOWED_ROOTS). Not env-overridable on purpose: external/pro plugins ship
# executable extensions, so the discovery roots must not be redirectable by an
# attacker-controlled env var. Tests inject locations via the explicit ``paths`` arg.
CORE_PLUGINS_PATH = join(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = join(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = join(sep, "etc", "bunkerweb", "pro", "plugins")

# Where the shared SQLAlchemy ``model`` module and ``db_methods`` package live, so a
# plugin db module can do ``from model import Base`` / subclass ``DatabaseMixinBase``.
_DB_DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "db")

# Relative module paths are restricted to simple ``a/b.py`` shapes — no traversal,
# no absolute paths. Defense in depth on top of the resolved-path guard below.
_REL_MODULE_RX = re_compile(r"^[\w][\w/-]*\.py$")


class PluginExtension(NamedTuple):
    plugin_id: str
    plugin_type: str  # "core" | "pro" | "external"
    directory: Path
    manifest: dict
    api: Optional[dict]
    db: Optional[dict]
    table_prefix: str


def _roots(paths=None):
    """Return an ordered list of ``(base_dir, plugin_type)`` to scan.

    ``paths`` lets tests point discovery at a temp directory instead of the
    container locations.
    """
    if paths is not None:
        return [(Path(base), ptype) for base, ptype in paths]
    return [
        (Path(CORE_PLUGINS_PATH), "core"),
        (Path(PRO_PLUGINS_PATH), "pro"),
        (Path(EXTERNAL_PLUGINS_PATH), "external"),
    ]


def iter_extension_plugins(paths=None, logger=None) -> List[PluginExtension]:
    """Scan plugin roots and return every plugin declaring an ``extensions`` block.

    Plugins whose ids collapse to the same id-derived table namespace (e.g. ``a-b``,
    ``a.b`` and ``a_b`` all -> ``bw_a_b_``) are ALL refused: a collision is either a
    misconfiguration or a namespace-poaching attempt, and silently letting the
    first-loaded win would let one plugin claim another's tables.
    """
    out: List[PluginExtension] = []
    for base, ptype in _roots(paths):
        if not base.is_dir():
            continue
        for plugin_json in sorted(base.glob("*/plugin.json")):
            try:
                manifest = loads(plugin_json.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(manifest, dict):
                continue
            extensions = manifest.get("extensions")
            if not isinstance(extensions, dict):
                continue
            api = extensions.get("api") if isinstance(extensions.get("api"), dict) else None
            db = extensions.get("db") if isinstance(extensions.get("db"), dict) else None
            if not api and not db:
                continue
            plugin_id = manifest.get("id") or plugin_json.parent.name
            table_prefix = (db or {}).get("table_prefix") or enforced_table_prefix(plugin_id)
            out.append(PluginExtension(plugin_id, ptype, plugin_json.parent, manifest, api, db, table_prefix))

    # Refuse namespace collisions (distinct ids that collapse to one bw_<id>_ prefix).
    namespaces: Dict[str, set] = {}
    for ext in out:
        namespaces.setdefault(enforced_table_prefix(ext.plugin_id), set()).add(ext.plugin_id)
    poisoned = {ns for ns, ids in namespaces.items() if len(ids) > 1}
    if poisoned:
        kept = []
        for ext in out:
            if enforced_table_prefix(ext.plugin_id) in poisoned:
                if logger is not None:
                    logger.error(
                        f"Refusing plugin {ext.plugin_id}: its table namespace {enforced_table_prefix(ext.plugin_id)} "
                        "collides with another plugin id (ambiguous after sanitization)"
                    )
                continue
            kept.append(ext)
        out = kept
    return out


def is_trusted(plugin_type: str) -> bool:
    """Tier gate (first line of defense).

    - ``core``: first-party, shipped in the image.
    - ``pro``: first-party, licensed.
    - ``external``: third-party — disabled unless ``PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL=yes``.

    Passing this gate is necessary but NOT sufficient: ``pro`` and ``external`` code
    is also checksum-verified against the DB plugin record before it is executed
    (see :func:`verify_plugin_integrity`). Only ``core`` skips the checksum step.
    """
    if plugin_type in ("core", "pro"):
        return True
    return getenv("PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL", "no").lower() in ("yes", "true", "1", "on")


def enforced_table_prefix(plugin_id: str) -> str:
    """The table namespace a plugin is HARD-bound to, derived solely from its id.

    The manifest's ``table_prefix`` is advisory (used for the Configurator-time check and
    docs); runtime enforcement deliberately ignores it and recomputes from the plugin id,
    so a hostile/edited ``plugin.json`` can never claim another plugin's — or a core —
    table namespace by simply declaring a broader/foreign prefix.
    """
    sanitized = plugin_id.replace("-", "_").replace(".", "_")
    return f"bw_{sanitized}_"


def _stored_plugin_checksum(db, plugin_id: str) -> Optional[str]:
    """Read the persisted sha256 checksum for a plugin from the DB (or None)."""
    _ensure_db_deps_on_path()
    from model import Plugins  # type: ignore
    from sqlalchemy import select  # type: ignore

    with db._db_session() as session:
        row = session.execute(select(Plugins.checksum).filter_by(id=plugin_id)).first()
    return row[0] if row else None


def verify_plugin_integrity(ext: "PluginExtension", db, logger: Logger) -> bool:
    """Tamper check (second line of defense).

    ``core`` plugins ship with the image and have no DB checksum — trusted as-is.
    ``pro``/``external`` plugins are stored in the DB with a sha256 of their packaged
    tar; we recompute the on-disk tar the exact same way the loader/Configurator does
    (``bytes_hash(create_plugin_tar_gz(dir, arc_root=dir.name), "sha256")``) and refuse
    the extension on any mismatch or missing record. Runs BEFORE the plugin's Python
    is imported/executed, so a tampered external/pro plugin never loads its code.
    """
    if ext.plugin_type == "core":
        return True
    if db is None:
        logger.error(f"Cannot verify integrity of {ext.plugin_type} plugin {ext.plugin_id} without a DB handle; refusing its extension")
        return False
    try:
        from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore

        expected = _stored_plugin_checksum(db, ext.plugin_id)
        if not expected:
            logger.error(f"No stored checksum for {ext.plugin_type} plugin {ext.plugin_id}; refusing its extension")
            return False
        actual = bytes_hash(create_plugin_tar_gz(ext.directory, arc_root=ext.directory.name), algorithm="sha256")
        if actual != expected:
            logger.error(f"Checksum mismatch for {ext.plugin_type} plugin {ext.plugin_id} (on-disk != DB) — possible tampering; refusing its extension")
            return False
        return True
    except Exception as e:
        logger.error(f"Integrity verification failed for plugin {ext.plugin_id}: {e}")
        return False


def extension_allowed(ext: "PluginExtension", db, logger: Logger) -> bool:
    """Single security gate: tier trust + integrity. Used by every loader path."""
    if not is_trusted(ext.plugin_type):
        logger.warning(
            f"Skipping extension of untrusted plugin {ext.plugin_id} ({ext.plugin_type}); "
            "set PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL=yes to enable external plugin API/DB extensions"
        )
        return False
    return verify_plugin_integrity(ext, db, logger)


def effective_api_prefix(ext: "PluginExtension") -> str:
    """Mount prefix is locked to ``/<plugin_id>`` so a plugin can never shadow a core
    router (``/instances``, ``/services``, …) or another plugin. Any declared prefix is
    validated to equal ``/<plugin_id>`` in Configurator, so we always derive it here."""
    return f"/{ext.plugin_id}"


def _ensure_db_deps_on_path() -> None:
    if _DB_DEPS_PATH not in sys_path:
        sys_path.append(_DB_DEPS_PATH)


def _ext_package_name(plugin_id: str) -> str:
    # Hyphens are valid in plugin ids but not in python package names.
    return f"bw_ext_{plugin_id.replace('-', '_')}"


def _ensure_ext_package(plugin_id: str, plugin_dir: Path) -> str:
    """Register a synthetic top-level package mapped to the plugin directory.

    Importing the plugin's submodules under this package (``bw_ext_<id>.db.models``)
    gives them natural intra-plugin relative imports (``from .models import X``) while
    keeping them isolated from every other plugin's same-named modules.
    """
    pkg_name = _ext_package_name(plugin_id)
    existing = sys_modules.get(pkg_name)
    resolved_dir = str(plugin_dir.resolve())
    if existing is None:
        pkg = ModuleType(pkg_name)
        pkg.__path__ = [resolved_dir]  # type: ignore[attr-defined]
        pkg.__package__ = pkg_name
        sys_modules[pkg_name] = pkg
    elif resolved_dir not in getattr(existing, "__path__", []):
        # Same plugin id discovered from a different location — keep both search paths.
        existing.__path__.append(resolved_dir)  # type: ignore[attr-defined]
    return pkg_name


def import_plugin_submodule(plugin_id: str, plugin_dir: Path, rel_module: str) -> ModuleType:
    """Safely import ``plugin_dir/<rel_module>`` as ``bw_ext_<id>.<dotted>``.

    Raises ``ValueError`` on a traversal attempt, ``FileNotFoundError`` if missing.
    """
    if not _REL_MODULE_RX.match(rel_module) or ".." in rel_module:
        raise ValueError(f"Invalid extension module path: {rel_module!r}")

    plugin_dir = Path(plugin_dir)
    resolved = (plugin_dir / rel_module).resolve()
    base = plugin_dir.resolve()
    if base != resolved and base not in resolved.parents:
        raise ValueError(f"Extension module {rel_module!r} escapes plugin dir {plugin_dir}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Extension module not found: {resolved}")

    _ensure_db_deps_on_path()
    pkg_name = _ensure_ext_package(plugin_id, plugin_dir)
    dotted = rel_module[:-3].replace("/", ".")  # strip ".py"
    return import_module(f"{pkg_name}.{dotted}")


def _import_with_namespace_guard(plugin_id: str, plugin_dir: Path, rel_module: str) -> Tuple[ModuleType, List[str]]:
    """Import a plugin submodule and enforce that it only registered tables within the
    plugin's id-derived namespace.

    Any out-of-namespace table the import created — as a side effect, including via
    sibling imports — is removed from ``Base.metadata`` and a ``ValueError`` is raised.
    Applied to BOTH the ``models.py`` and ``methods.py`` import paths, so neither can
    smuggle a foreign/core-shadowing table onto the shared metadata. Returns
    ``(module, sorted in-namespace tables newly registered by this import)``.
    """
    _ensure_db_deps_on_path()
    from model import Base  # type: ignore

    prefix = enforced_table_prefix(plugin_id)
    before = set(Base.metadata.tables)
    try:
        module = import_plugin_submodule(plugin_id, plugin_dir, rel_module)
    except Exception:
        # a failed import may have partially registered tables — roll them back
        for name in set(Base.metadata.tables) - before:
            table = Base.metadata.tables.get(name)
            if table is not None:
                Base.metadata.remove(table)
        raise
    new_tables = set(Base.metadata.tables) - before
    bad = sorted(t for t in new_tables if not t.startswith(prefix))
    if bad:
        for name in new_tables:
            table = Base.metadata.tables.get(name)
            if table is not None:
                Base.metadata.remove(table)
        raise ValueError(f"registered table(s) outside enforced '{prefix}' namespace: {bad}")
    return module, sorted(new_tables)


def register_plugin_models(logger: Logger, db=None, paths=None) -> Dict[str, List[str]]:
    """Import each plugin's ``db/models.py`` so its tables register on ``Base.metadata``
    *before* ``Base.metadata.create_all`` runs.

    Enforces the id-derived ``bw_<id>_`` table namespace via
    :func:`_import_with_namespace_guard` (NOT the manifest's declared prefix): any table
    a plugin registers outside its namespace is removed and the plugin's models rejected.
    ``db`` is required to load external/pro models (checksum verification). Returns
    ``{plugin_id: [table names]}`` for tables newly registered by this call (idempotent:
    a second call is a no-op).

    Residual trust: importing a plugin module executes its Python. For external/pro this
    is gated (opt-in flag + checksum), but a checksum-valid external plugin the admin
    opted into can still run arbitrary code (e.g. mutate an already-registered core
    ``Table`` object directly). The namespace guard bounds *newly registered* tables on
    both import paths; it is not a sandbox. The trust boundary is the tier gate +
    integrity check, by design.
    """
    registered: Dict[str, List[str]] = {}
    for ext in iter_extension_plugins(paths, logger=logger):
        if not ext.db or not ext.db.get("models"):
            continue
        if not extension_allowed(ext, db, logger):
            continue
        try:
            _module, new_tables = _import_with_namespace_guard(ext.plugin_id, ext.directory, ext.db["models"])
        except Exception as e:
            logger.error(f"Rejecting DB models for plugin {ext.plugin_id}: {e}")
            continue
        if new_tables:
            registered[ext.plugin_id] = new_tables
            logger.info(f"Registered DB extension table(s) for plugin {ext.plugin_id}: {new_tables}")
    return registered


def discover_db_methods(logger: Logger, db=None, paths=None) -> Dict[str, type]:
    """Return ``{plugin_id: DatabaseMixinBase subclass}`` for plugins shipping
    ``db/methods.py`` — the query helpers exposed via ``Database.ext(plugin_id)``.
    ``db`` is required to load external/pro methods (checksum verification). The import
    is namespace-guarded identically to models, so a ``methods.py`` import side effect
    cannot register a foreign/core-shadowing table either.
    """
    _ensure_db_deps_on_path()
    from db_methods.common import DatabaseMixinBase  # type: ignore

    out: Dict[str, type] = {}
    for ext in iter_extension_plugins(paths, logger=logger):
        if not ext.db or not ext.db.get("methods"):
            continue
        if not extension_allowed(ext, db, logger):
            continue
        try:
            module, _new = _import_with_namespace_guard(ext.plugin_id, ext.directory, ext.db["methods"])
        except Exception as e:
            logger.error(f"Rejecting DB methods for plugin {ext.plugin_id}: {e}")
            continue

        mixin_cls = None
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, DatabaseMixinBase) and obj is not DatabaseMixinBase and obj.__module__ == module.__name__:
                mixin_cls = obj
                break
        if mixin_cls is None:
            logger.error(f"Plugin {ext.plugin_id} db/methods.py exposes no DatabaseMixinBase subclass")
            continue
        out[ext.plugin_id] = mixin_cls
    return out


class _ExtProxyBase:
    """Delegates every attribute not found on the bound mixin to the live Database,
    so query methods see the real ``_db_session``/``readonly``/``logger``/retry config.
    """

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_db"), name)


def make_db_ext(db, mixin_cls: type):
    """Bind a discovered db-methods mixin class to a live ``Database`` instance.

    Returns an object whose own query methods come from ``mixin_cls`` while shared
    members (session factory, readonly flag, retry config) resolve against ``db`` —
    keeping the core ``Database`` MRO frozen and audit-stable.
    """
    proxy_cls = type(f"DbExt_{mixin_cls.__name__}", (mixin_cls, _ExtProxyBase), {})
    obj = object.__new__(proxy_cls)
    object.__setattr__(obj, "_db", db)
    return obj
