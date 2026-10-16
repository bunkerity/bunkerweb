from json import load as json_load
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def read_manual_plugin(plugin_dir: Path, validator: Any, others: Iterable[Dict[str, Any]] = ()) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Read and validate a hand-mounted ``<plugin_dir>/plugin.json``.

    Returns ``(manifest, None)`` when it is usable and ``(manifest, reason)`` when it is not
    (``manifest`` is ``None`` if the file could not be read as a JSON object). It never raises, so
    a malformed manifest cannot take the caller down: callers keep the directory and report ``reason``.
    ``validator`` is a ``Configurator``; ``others`` are the plugins already known to the database.
    """
    try:
        with plugin_dir.joinpath("plugin.json").open("r", encoding="utf-8") as file:
            manifest = json_load(file)
    except (OSError, ValueError, RecursionError) as e:
        return None, f"plugin.json cannot be read ({type(e).__name__}: {e})"
    if not isinstance(manifest, dict):
        return None, "plugin.json must contain a JSON object"

    try:
        valid, message = validator.validate_manual_plugin(manifest, others)
    except Exception as e:  # a manifest is untrusted input: whatever it breaks, it is only invalid
        return manifest, f"plugin.json cannot be validated ({type(e).__name__}: {e})"
    return manifest, None if valid else message
