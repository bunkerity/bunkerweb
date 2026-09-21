"""The data surface plugin UI code may rely on.

1.7 stopped giving the web UI a database connection: everything a page shows comes from the
central API through ``app.dependencies.API_CLIENT``. That object is the UI's *private* client --
it also creates users, resolves WebAuthn credentials and drops sessions -- so plugins get
``PLUGIN_API``, a facade over the same client restricted to :data:`PLUGIN_API_METHODS`. That
frozenset is the compatibility promise ``docs/plugins.md`` makes between two minor versions;
anything else on the client is internal and may move without notice.

``DB``, the 1.6 handle, is gone. It is kept as :class:`RetiredDB` rather than ``None`` so the
first dereference raises an actionable ``RuntimeError`` naming the plugin instead of
``AttributeError: 'NoneType' object has no attribute 'get_config'`` a stack frame deeper.
"""

from logging import getLogger
from os import sep
from pathlib import Path
from sys import _getframe

from app.api_client import ApiClientError

LOGGER = getLogger("UI")

DOC_REF = 'the "UI plugins: supported surface" section of docs/plugins.md'

#: What a plugin blueprint, ``ui/actions.py`` or ``ui/hooks.py`` may call on ``PLUGIN_API``.
#: Read-only except for custom configs, the one thing plugin pages have always written directly;
#: settings are written through ``BW_CONFIG`` (``edit_global_conf`` / ``edit_service``), which
#: validates them, and never straight through the API client.
PLUGIN_API_METHODS = frozenset(
    {
        # Settings and plugin metadata
        "get_global_settings",
        "get_plugins",
        # Services
        "get_services",
        "get_service",
        # Custom configs
        "get_configs",
        "get_config_item",
        "create_config",
        "update_config",
        "delete_config",
        # Job cache and job runs
        "get_cache_files",
        "get_cache_file",
        "get_jobs",
        "get_last_job_run",
        # State
        "readonly",
    }
)

_PLUGIN_ROOTS = (
    Path(sep, "etc", "bunkerweb", "pro", "plugins"),
    Path(sep, "etc", "bunkerweb", "plugins"),
    Path(sep, "usr", "share", "bunkerweb", "core"),
)


def _caller_plugin(frame) -> str:
    """Best-effort plugin id for the frame that reached for the attribute.

    The installed path is authoritative and is tried first. Only code loaded from somewhere else --
    an ``actions.py`` extracted from a database blob into a uuid directory, or a test -- falls back
    to the generated module name, which carries the plugin directory (``src/ui/main.py``).
    """
    path = Path(frame.f_code.co_filename)
    for root in _PLUGIN_ROOTS:
        if path.is_relative_to(root):
            return path.relative_to(root).parts[0]

    module = frame.f_globals.get("__name__", "")

    # `bw_ui_actions_<plugin>_<uuid hex>` (`routes/plugins.py`) -- the only handle on a plugin whose
    # `actions.py` was extracted from a database blob into a uuid directory.
    if module.startswith("bw_ui_actions_"):
        return module.removeprefix("bw_ui_actions_").rsplit("_", 1)[0] or "unknown"

    # `bw_ui_<kind>_<plugin dir>_<file stem>` (`src/ui/main.py:377`, `:492`). Both halves routinely
    # contain `_` -- `saml/ui/blueprints/saml_config.py` is `bw_ui_blueprint_saml_saml_config` --
    # so the stem is removed by name, never by splitting on the last separator. The module name is
    # built from the NON-proxy stem while the file may be the `*_proxy.py` variant
    # (`src/ui/main.py:381-383`, `:488-490`), so that suffix comes off first.
    stem = path.stem.removesuffix("_proxy")
    for prefix in ("bw_ui_blueprint_", "bw_ui_hooks_"):
        if module.startswith(prefix):
            return module.removeprefix(prefix).removesuffix(f"_{stem}") or "unknown"

    return f"{path.name}:{frame.f_lineno}"


class PluginApi:
    """Delegates the :data:`PLUGIN_API_METHODS` subset to the UI's API client, and nothing else."""

    def __init__(self, api_client):
        self._api_client = api_client

    def get_cache_file_or_none(self, service, plugin, job, filename, download=False):
        """``get_cache_file``, but a missing cache file returns ``None`` instead of raising.

        Mirrors the retired ``db.get_job_cache_file``, which returned ``None`` on a miss --
        several plugin pages branch on that ("not registered yet", "no backup yet"). Also unwraps
        ``download=True``'s ``requests.Response`` into its ``.content`` bytes, which is what every
        ``download=True`` caller actually wants (see `src/ui/app/routes/cache.py:51-52`).

        A real (not a defined-here) method rather than routed through ``__getattr__``: it is not a
        raw passthrough to the client, so it stays out of :data:`PLUGIN_API_METHODS`.
        """
        try:
            result = self._api_client.get_cache_file(service, plugin, job, filename, download=download)
        except ApiClientError as e:
            if e.status_code == 404:
                return None
            raise
        return result.content if download else result

    def __getattr__(self, name: str):
        if name not in PLUGIN_API_METHODS:
            plugin = _caller_plugin(_getframe(1))
            raise AttributeError(
                f"PLUGIN_API has no attribute {name!r} (plugin {plugin!r}). Only "
                f"{', '.join(sorted(PLUGIN_API_METHODS))} are part of the supported plugin surface; see {DOC_REF}."
            )
        return getattr(self._api_client, name)

    def __dir__(self):
        return sorted(PLUGIN_API_METHODS)

    def __repr__(self):
        return f"<PluginApi {len(PLUGIN_API_METHODS)} methods>"


class RetiredDBError(RuntimeError, AttributeError):
    """Raised by :class:`RetiredDB`.

    ``RuntimeError`` because that is the loud, actionable failure a plugin author must see;
    ``AttributeError`` as well so the feature-probe idiom keeps the meaning it had while ``DB``
    was ``None`` -- ``hasattr(DB, "x")`` is ``False`` and ``getattr(DB, "x", None)`` is ``None``
    instead of blowing up code that was written to degrade. A real call still raises, and the
    ERROR log below fires either way, so a swallowed probe is never silent.
    """


class RetiredDB:
    """Stands in for the 1.6 ``DB`` handle and refuses every use, loudly."""

    def __bool__(self) -> bool:
        # 1.6 plugins guard with `if DB:` before falling back; keep that branch taking the
        # same turn it took when `DB` was exported as None.
        return False

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            # Protocol probing (copy, pickle, `hasattr`) must not be answered with a RuntimeError
            # the prober cannot catch; only a real plugin call deserves the noise below.
            raise AttributeError(name)

        plugin = _caller_plugin(_getframe(1))
        message = (
            f"app.dependencies.DB was removed in BunkerWeb 1.7 -- the web UI holds no database connection. "
            f"Plugin {plugin!r} used DB.{name}: read through PLUGIN_API instead "
            f"(`from app.dependencies import PLUGIN_API`), or write settings through BW_CONFIG. See {DOC_REF}."
        )
        LOGGER.error(message)
        raise RetiredDBError(message)

    def __repr__(self):
        return "<RetiredDB: use PLUGIN_API>"
