#!/usr/bin/env python3
"""Drift detection for the ``/etc/bunkerweb/configs`` projection.

That folder is a **projection** of ``bw_custom_configs``, not a source of truth. Two independent
processes rewrite it from the database, both by wiping and re-materializing:

* the scheduler's ``generate_custom_configs`` (``src/scheduler/main.py``), on boot, on SIGHUP and
  on every pass that raised ``CONFIGS_NEED_GENERATION``;
* the worker's ``_materialize_custom_configs`` (``src/common/core/jobs/jobs/push-configs.py``),
  before every push to the instances.

Until now both did it silently, so a file the operator edited or dropped by hand simply vanished
at the next reload with nothing in the logs -- the complaint behind issue #173 and the first
acceptance criterion of the « Refonte des configurations personnalisées » design.

This module is the shared half: it names the drift once, in the same words, for both writers, and
carries the ``CUSTOM_CONFIGS_DRIFT`` policy that decides what happens next.

Scope, deliberately narrow:

* only ``*.conf`` files at the two depths the generator writes -- ``<type>/<name>.conf`` and
  ``<type>/<service>/<name>.conf``. Those are also the only names ``check_configs_changes`` can
  adopt, so a log line about anything else would name a file the operator has no way to keep;
* files reached through symlinks below the projection root are never hashed; the root itself
  may be a deployment symlink;
* a draft row projects no file, so a file sitting where a draft row would have written one reads
  as an orphan -- which is what it is: the next pass deletes it.

``# CREATED BY ENV`` files are **not** exempt. Unedited they produce no line at all (that is what
keeps an env-only install byte-identical, AC 6); edited, they are precisely the case that used to
be discarded in silence by the method arbitration in ``db_methods/custom_configs.py`` and then
overwritten here.

**What "drift" means here, and why it is not "the file differs from the database".** Comparing the
folder against the *current* rows cannot tell the two halves apart: a file the operator edited and
a file the projection simply has not caught up with yet look identical. Every ordinary change --
someone saves a config in the web UI, a ``CUSTOM_CONF_*`` variable moves, a row is deleted -- would
report as drift, which makes the WARNING meaningless and makes ``refuse`` refuse the very change it
was asked to protect, forever.

So the comparison is against a **manifest of what this projection last wrote** (path -> sha256),
kept outside the folder at ``PROJECTION_STATE_PATH``. Drift is then exactly "this file changed
under us since we wrote it", plus "we never wrote this file at all" for a dropped one. A stale
projection compares equal to its own manifest and is silently refreshed, which is what it is.

The manifest is advisory, never load-bearing: missing, unreadable or malformed means the history is
unknown, and an unknown history reports **no** drift at all -- a fresh install, an upgrade and a
recreated container therefore behave exactly as they did before, and the first projection lays the
manifest down.
"""

from contextlib import suppress
from json import dumps as json_dumps, loads as json_loads
from os import getenv, sep
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Union

from common_utils import bytes_hash  # type: ignore

# Outside the projected folder on purpose: anything under it is wiped by the projection, swept by
# the `*/*.conf` glob, and shipped to every instance in the `/custom_configs` tarball. /var/lib is
# none of those, exists in every image and package, and persists across restarts (the all-in-one
# and worker images symlink it into the /data volume).
PROJECTION_STATE_PATH = Path(sep, "var", "lib", "bunkerweb", "custom-configs-projection.json")

DRIFT_POLICIES = ("overwrite", "refuse")
DEFAULT_DRIFT_POLICY = "overwrite"
DRIFT_SETTING = "CUSTOM_CONFIGS_DRIFT"

# Used in both the advisory manifest comparison and log lines. A 48-bit digest collision can
# suppress drift; only the disk-equals-current-row suppression compares full bytes.
_SHORT_LEN = 12


class ConfigDrift(NamedTuple):
    """One projected path whose on-disk content is not what the database holds."""

    path: Path
    reason: str  # "modified" (changed since the manifest) | "orphan" (absent from the manifest)
    method: Optional[str]  # the method that owns the row, for "modified"
    disk_checksum: str
    db_checksum: Optional[str]


def get_drift_policy(raw: Optional[str] = None) -> str:
    """Normalize a ``CUSTOM_CONFIGS_DRIFT`` value, falling back to the process environment.

    This only normalizes; **finding** the value is each reader's own `_drift_policy_value()`, which
    looks at the environment first and the database second. Both halves are needed and neither
    alone is right: the scheduler keeps its own process environment, while the worker runs jobs
    with an environment rebuilt from `db.get_config()` (`worker/tasks.py`), so a `getenv`-only rule
    would have the two writers of one folder follow different policies.
    """
    value = (raw if raw is not None else getenv(DRIFT_SETTING, "")).strip().lower()
    return value if value in DRIFT_POLICIES else DEFAULT_DRIFT_POLICY


def custom_config_path(root: Union[Path, str], config: Dict[str, Any]) -> Path:
    """The one path formula both projections use. Kept here so they cannot diverge."""
    return Path(root).joinpath(
        config["type"].replace("_", "-"),
        config.get("service_id") or "",
        f"{Path(config['name']).stem}.conf",
    )


def _short(data: bytes) -> str:
    return bytes_hash(data, algorithm="sha256")[:_SHORT_LEN]


def _as_bytes(data: Union[str, bytes]) -> bytes:
    return data.encode("utf-8") if isinstance(data, str) else data


def _projected_files(root: Path) -> List[Path]:
    """The projected `.conf` files, never the instance's own bookkeeping trees.

    `pathlib.Path.glob` matches dot-prefixed directories -- unlike a shell glob, which is the
    assumption `api.lua:792-794` states it deliberately does not rely on. On all-in-one and Linux
    this folder IS the instance's `/custom_configs` destination (`api.lua:683-684`), and the push
    handler parks copies inside it: `.bw-staging` for the duration of a push (`api.lua:724`),
    `.bw-trash` when an entry is stuck, and `.bw-rescue.<epoch>` kept for seven days
    (`pushswap.lua:153, 192, 114`). Those hold the instance's own recovery data, at exactly the
    depth the projection writes; judging them would report one drift per parked file, on every
    projection, for as long as the rescue tree lives.
    """
    files = []
    for file in set(root.glob("*/*.conf")) | set(root.glob("*/*/*.conf")):
        parts = file.relative_to(root).parts
        # Check every component below root; root itself may be a deployment symlink.
        if parts[0].startswith(".") or any(root.joinpath(*parts[:depth]).is_symlink() for depth in range(1, len(parts) + 1)):
            continue
        files.append(file)
    return sorted(files)


def read_projection(path: Optional[Union[Path, str]] = None) -> Optional[Dict[str, str]]:
    """The manifest of the last projection, or ``None`` when there is no usable history.

    ``None`` and an empty dict are different answers and the difference matters: ``None`` means
    "we do not know what we wrote", which must report no drift at all, while ``{}`` means "we
    wrote nothing", under which every file present IS an operator's.
    """
    try:
        data = json_loads(Path(path or PROJECTION_STATE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return None
    return {str(key): str(value) for key, value in files.items()}


def write_projection(root: Union[Path, str], path: Optional[Union[Path, str]] = None) -> None:
    """Record what is on disk now, so the next pass can tell an edit from a stale projection.

    Read back from the files rather than from the rows that were meant to be written, so the
    manifest describes the folder that exists rather than the one that was intended. The cost of
    that choice, stated plainly because an earlier revision of this docstring claimed the opposite
    benefit: when a write fails (`main.py` catches the `OSError` and carries on) the bytes left on
    disk are the previous ones -- an operator's, if they had edited that file -- and they are then
    recorded as ours, so the next pass sees no drift where the pass before did. Reporting a drift
    that a failed write is about to erase anyway was judged the smaller half; the failure itself is
    logged by the projection.

    Best effort -- an unwritable manifest costs the next pass its drift detection (it reads as
    "no history"), never the projection itself.
    """
    root = Path(root)
    files: Dict[str, str] = {}
    for file in _projected_files(root):
        if file.is_symlink() or not file.is_file():
            continue
        try:
            files[file.relative_to(root).as_posix()] = _short(file.read_bytes())
        except OSError:
            continue

    path = Path(path or PROJECTION_STATE_PATH)
    with suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json_dumps({"root": root.as_posix(), "files": files}), encoding="utf-8")
        tmp.replace(path)


def detect_drift(
    root: Union[Path, str],
    configs: Optional[Iterable[Dict[str, Any]]],
    projection: Optional[Dict[str, str]],
) -> List[ConfigDrift]:
    """Files under ``root`` that changed under us since the projection wrote them.

    NOT "files that differ from the database": the rows move on their own, and a folder that has
    not caught up with them yet is a pending update, not an operator edit. ``projection`` is the
    manifest the last pass left behind; ``None`` means the history is unknown and nothing can
    honestly be called drift.

    ``configs`` decides exactly one thing -- a file whose bytes ARE the row's bytes is never drift,
    whatever the manifest remembers, which is what lets an adoption clear a refusal (see below) --
    and enriches the message for everything else (which method owns the row, what it now holds).
    """
    root = Path(root)
    if projection is None or not root.is_dir():
        return []

    expected: Dict[Path, Dict[str, Any]] = {}
    for config in configs or ():
        if config.get("is_draft") or not config.get("data"):
            continue
        expected[custom_config_path(root, config)] = config

    drifts: List[ConfigDrift] = []
    for file in _projected_files(root):
        if file.is_symlink() or not file.is_file():
            continue
        try:
            content = file.read_bytes()
        except OSError:
            # Unreadable is not drift we can describe; the projection's own error path reports it.
            continue

        config = expected.get(file)
        if config and _as_bytes(config["data"]) == content:
            # The folder and the database agree, so there is nothing to arbitrate no matter what
            # the manifest remembers. Without this, `refuse` is a one-way trap: the manifest is
            # written only by a projection that COMPLETES, and a refusal is precisely a projection
            # that does not, so adopting the file -- the resolution `log_refusal` names, and the
            # one `check_configs_changes` performs on every reload -- could never clear the
            # refusal and only deleting the file would. It cannot bring back the deadlock the
            # manifest was introduced for: that one was disk == manifest while disk != row, which
            # the manifest rule already suppresses and this rule never sees.
            continue

        disk = _short(content)
        written = projection.get(file.relative_to(root).as_posix())
        if written is None:
            # The projection never wrote this file, so somebody else put it there.
            drifts.append(ConfigDrift(file, "orphan", None, disk, None))
            continue
        if written == disk:
            continue

        data = config.get("data") if config else None
        drifts.append(ConfigDrift(file, "modified", config.get("method") if config else None, disk, _short(_as_bytes(data)) if data else None))

    return drifts


def log_drift(
    logger,
    root: Union[Path, str],
    configs: Optional[Iterable[Dict[str, Any]]],
    policy: str,
    projection: Optional[Dict[str, str]],
) -> List[ConfigDrift]:
    """Emit exactly one WARNING per drifted file and hand the list back to the caller.

    A file still matching what the projection wrote produces nothing even when the database has
    since moved on -- that is an ordinary pending update, and logging it would put a line in front
    of the operator for every config they save in the web UI.
    """
    drifts = detect_drift(root, configs, projection)
    for drift in drifts:
        outcome = "the projection is left untouched"
        if policy == "overwrite":
            outcome = "it will be overwritten from the database" if drift.db_checksum is not None else "it will be deleted"
        if drift.reason == "modified":
            logger.warning(
                f"Custom config drift: {drift.path} was changed outside the database since it was last written "
                f"(database method={drift.method}, disk sha256={drift.disk_checksum}, database sha256={drift.db_checksum}); "
                f"{DRIFT_SETTING}={policy}, {outcome}"
            )
        else:
            logger.warning(
                f"Custom config drift: {drift.path} was not written by the projection "
                f"(disk sha256={drift.disk_checksum}); "
                f"{DRIFT_SETTING}={policy}, " + ("it will be deleted" if policy == "overwrite" else "the projection is left untouched")
            )
    return drifts


def log_refusal(logger, root: Union[Path, str], drifts: List[ConfigDrift]) -> None:
    """The ``refuse`` half: say what is blocked, what that costs, and how the operator unblocks it.

    Deliberately explicit that NOTHING is written rather than "the drifted file is kept". Nothing
    from the database reaches this folder while the drift stands -- including custom configs that
    have nothing to do with it -- and on all-in-one and Linux this folder is the one NGINX
    includes, so the files below are what is being served. An operator who reads "the last good
    projection is kept" would conclude the opposite of both.
    """
    logger.error(
        f"{DRIFT_SETTING}=refuse: {len(drifts)} file(s) under {Path(root)} differ from the database, "
        f"so NOTHING was written there from the database -- no custom config change is being applied, "
        f"and on all-in-one and Linux installs this folder is the one NGINX includes, so these files are what is served. "
        f"Resolve it by deleting the file(s), or adopt them into the database -- reload the scheduler to "
        f"rescan the folder, or send them through the API or the web UI; a config owned by a CUSTOM_CONF_* "
        f"variable or by an orchestrator label cannot be adopted from disk and has to be changed at its source; "
        f"drifted: {', '.join(drift.path.as_posix() for drift in drifts)}"
    )
