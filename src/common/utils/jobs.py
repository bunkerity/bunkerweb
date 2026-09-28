#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from gzip import GzipFile
from inspect import currentframe, getframeinfo
from io import BytesIO
from json import dumps as json_dumps, loads as json_loads
from logging import Logger
from os import getenv
from os.path import sep
from pathlib import Path
from re import compile as re_compile
from shutil import rmtree
from tarfile import open as tar_open
from threading import Lock
from time import time_ns
from traceback import format_exc
from typing import Any, Dict, Iterable, Literal, Optional, Set, Tuple, Union

from common_utils import bytes_hash, file_hash
from cache_restore import (
    cache_tree,
    checked_cache_path,
    checked_folder_target,
    is_preserved,
    recover_directory,
    restore_directory,
    restore_mtls_cache,
    transaction_markers,
    write_atomic as _write_atomic,
)

LOCK = Lock()
EXPIRE_TIME = {
    "hour": timedelta(hours=1).total_seconds(),
    "day": timedelta(days=1).total_seconds(),
    "week": timedelta(weeks=1).total_seconds(),
    "month": timedelta(days=30).total_seconds(),
}

# OCSP SPKI shard keys under /var/cache/bunkerweb/ssl/{h1}/{h2}/{fp64}/…
_OCSP_SHARD_FILE_RE = re_compile(r"^([0-9a-fA-F])/([0-9a-fA-F])/([0-9a-fA-F]{64})/(ocsp\.der|ocsp\.json|issuer\.pem)$")
_OCSP_FLOOR_FILE_RE = re_compile(r"^ocsp-floor/([0-9a-fA-F]{64})$")


def parse_ocsp_shard_cache_name(file_name: str) -> Optional[Tuple[str, str]]:
    """
    If file_name is an OCSP shard cache key, return (fingerprint_lower, leaf_name).
    leaf_name is one of ocsp.der, ocsp.json, issuer.pem.
    """
    if not file_name:
        return None
    match = _OCSP_SHARD_FILE_RE.match(str(file_name).replace("\\", "/"))
    if not match:
        return None
    hex1, hex2, fingerprint, leaf = match.groups()
    fp = fingerprint.lower()
    if fp[0] != hex1.lower() or fp[1] != hex2.lower():
        return None
    return fp, leaf


def parse_ocsp_floor_cache_name(file_name: str) -> Optional[str]:
    """If file_name is ocsp-floor/{fp64}, return fingerprint_lower."""
    if not file_name:
        return None
    match = _OCSP_FLOOR_FILE_RE.match(str(file_name).replace("\\", "/"))
    if not match:
        return None
    return match.group(1).lower()


def ocsp_job_run_id_rank(run_id: Any) -> int:
    """
    Rank job_run_id (pid.time_ns) by the ns token; 0 if unreadable.

    Local forensic / same-host tie-break only. Do not treat as colony consensus:
    time_ns is per-process and not comparable across scheduler hosts.
    """
    if not isinstance(run_id, str) or not run_id:
        return 0
    parts = run_id.rsplit(".", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def _ocsp_job_run_id_rank(run_id: Any) -> int:
    return ocsp_job_run_id_rank(run_id)


def _ocsp_meta_unix(meta: Dict[str, Any], key: str) -> int:
    raw = meta.get(key)
    if isinstance(raw, (int, float)) and int(raw) > 0:
        return int(raw)
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return 0


def parse_ocsp_floor_bytes(data: Optional[bytes]) -> Optional[Dict[str, Any]]:
    """
    Parse an ocsp-floor file body into {published_unix, job_run_id?}.

    Preferred body is compact JSON. Also accepts a plain decimal published_unix.
    Legacy plain job_run_id (pid.time_ns) is ignored for colony ordering (no published_unix).
    """
    if not data:
        return None
    try:
        text = data.decode("utf-8").strip()
    except Exception:
        return None
    if not text:
        return None
    if text.startswith("{"):
        try:
            obj = json_loads(text)
        except Exception:
            return None
        if not isinstance(obj, dict):
            return None
        published = _ocsp_meta_unix(obj, "published_unix")
        out: Dict[str, Any] = {}
        if published > 0:
            out["published_unix"] = published
        run_id = obj.get("job_run_id")
        if isinstance(run_id, str) and run_id:
            out["job_run_id"] = run_id
        return out or None
    token = text.split()[0]
    if token.isdigit():
        published = int(token)
        if published > 0:
            return {"published_unix": published}
        return None
    # Legacy job_run_id-only floor: not colony-comparable.
    return None


def load_disk_ocsp_floor(cache_root: Path, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Read on-disk cluster floor payload for fingerprint, or None."""
    if not fingerprint or len(fingerprint) != 64:
        return None
    path = Path(cache_root) / "ocsp-floor" / fingerprint.lower()
    if not path.is_file():
        return None
    try:
        return parse_ocsp_floor_bytes(path.read_bytes())
    except Exception:
        return None


def ocsp_floor_published_unix(floor: Optional[Dict[str, Any]]) -> int:
    if not isinstance(floor, dict):
        return 0
    return _ocsp_meta_unix(floor, "published_unix")


def clear_ocsp_peer_refuse(cache_root: Path, fingerprint: str, logger: Optional[Logger] = None) -> bool:
    """Drop HTTP↔stream generation refuse marker for this SPKI (new page / restore)."""
    if not fingerprint or len(fingerprint) != 64:
        return False
    fp = fingerprint.lower()
    try:
        refuse_dir = Path(cache_root) / "ocsp-refuse"
        refuse_dir.mkdir(parents=True, exist_ok=True)
        path = refuse_dir / fp
        if path.is_file():
            path.unlink()
            if logger is not None:
                logger.debug(f"OCSP cleared peer-refuse bus for fp={fp[:16]}...")
        return True
    except Exception as e:
        if logger is not None:
            logger.debug(f"OCSP could not clear peer-refuse for {fp[:16]}...: {e}")
        return False


def bump_ocsp_cache_epoch(cache_root: Path, logger: Optional[Logger] = None) -> bool:
    """
    Bump shared on-disk generation counter so HTTP and stream L1 both drop stale
    OCSP entries after publish or DB restore. Workers compare packed L1 epoch to
    this file; they cannot cross-delete each other's shared dicts.
    """
    try:
        root = Path(cache_root)
        root.mkdir(parents=True, exist_ok=True)
        _write_atomic(root / ".ocsp_epoch", f"{time_ns()}\n".encode("ascii"))
        if logger is not None:
            logger.debug("OCSP bumped .ocsp_epoch after restore/publish coherence")
        return True
    except Exception as e:
        if logger is not None:
            logger.debug(f"OCSP could not bump cache epoch: {e}")
        return False


def publish_ocsp_restore_coherence(
    cache_root: Path,
    fingerprints: Iterable[str],
    logger: Optional[Logger] = None,
) -> None:
    """
    After DB restore wrote one or more OCSP shard leaves for these fingerprints,
    clear sticky peer-refuse markers and bump .ocsp_epoch once (same side effects
    as ocsp-refresh publish). Skipped/fenced fingerprints must not be passed in.
    """
    fps: Set[str] = set()
    for fingerprint in fingerprints:
        if isinstance(fingerprint, str) and len(fingerprint) == 64 and fingerprint.isalnum():
            fps.add(fingerprint.lower())
    if not fps:
        return
    for fp in sorted(fps):
        clear_ocsp_peer_refuse(cache_root, fp, logger)
    bump_ocsp_cache_epoch(cache_root, logger)
    if logger is not None:
        logger.info(f"OCSP restore coherence: cleared refuse + bumped epoch for {len(fps)} shard(s)")


def encode_ocsp_floor_payload(published_unix: int, job_run_id: Optional[str] = None) -> bytes:
    """Serialize colony floor: wall-clock published_unix is the comparable field."""
    payload: Dict[str, Any] = {"published_unix": int(published_unix)}
    if isinstance(job_run_id, str) and job_run_id:
        payload["job_run_id"] = job_run_id
    return (json_dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def should_keep_disk_ocsp_floor(
    disk_floor: Optional[Dict[str, Any]],
    incoming_floor: Optional[Dict[str, Any]],
) -> bool:
    """
    True when the on-disk cluster floor must not be overwritten by restore.

    Floor is max-only on published_unix (wall clock, colony-comparable).
    Equal → keep disk. Missing disk published_unix → allow restore.
    """
    disk_pub = ocsp_floor_published_unix(disk_floor)
    if disk_pub <= 0:
        return False
    return disk_pub >= ocsp_floor_published_unix(incoming_floor)


def should_skip_ocsp_floor_restore(
    disk_floor: Optional[Dict[str, Any]],
    incoming_floor: Optional[Dict[str, Any]],
    floor_cap: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Whether restore must not write this floor row.

    Caps floor raises when the shard fence kept a still-GOOD trio: restoring a
    higher colony floor would leave healthy-looking files while Must-Staple stays
    closed (cluster_floor). Live peer advances outside restore are unchanged.
    """
    if should_keep_disk_ocsp_floor(disk_floor, incoming_floor):
        return True, (
            f"disk_floor_newer_or_equal disk_pub={ocsp_floor_published_unix(disk_floor)} "
            f"incoming_pub={ocsp_floor_published_unix(incoming_floor)}"
        )
    if isinstance(floor_cap, int) and floor_cap > 0:
        incoming_pub = ocsp_floor_published_unix(incoming_floor)
        if incoming_pub > floor_cap:
            return True, f"floor_capped_to_fenced_shard cap={floor_cap} incoming_pub={incoming_pub}"
    return False, ""


def parse_ocsp_meta_bytes(data: Optional[bytes]) -> Optional[Dict[str, Any]]:
    if not data:
        return None
    try:
        meta = json_loads(data.decode("utf-8"))
    except Exception:
        return None
    return meta if isinstance(meta, dict) else None


def load_disk_ocsp_meta(shard_dir: Path) -> Optional[Dict[str, Any]]:
    meta_path = shard_dir / "ocsp.json"
    if not meta_path.is_file():
        return None
    try:
        return parse_ocsp_meta_bytes(meta_path.read_bytes())
    except Exception:
        return None


def should_keep_disk_ocsp_shard(
    disk_meta: Optional[Dict[str, Any]],
    incoming_meta: Optional[Dict[str, Any]],
) -> bool:
    """
    True when an on-disk OCSP shard must not be overwritten by a DB/restore payload.

    Order: tombstone vs GOOD by published_unix (wall clock; denial must not lose to an
    older far-future GOOD), then expires_unix, published_unix, and job_run_id only as a
    same-host forensic tie-break (pid.time_ns is not colony consensus). Equal → keep disk.
    Missing disk meta → allow restore. Missing incoming meta while disk has meta → keep disk.
    """
    if not isinstance(disk_meta, dict):
        return False
    if not isinstance(incoming_meta, dict):
        return True

    disk_tomb = disk_meta.get("tombstoned") is True
    inc_tomb = incoming_meta.get("tombstoned") is True
    disk_pub = _ocsp_meta_unix(disk_meta, "published_unix")
    inc_pub = _ocsp_meta_unix(incoming_meta, "published_unix")

    # Tombstone vs GOOD: wall-clock publish time, never cross-host job_run_id ranks.
    if disk_tomb and not inc_tomb:
        if disk_pub > 0 or inc_pub > 0:
            return inc_pub <= disk_pub
        # No comparable wall times: keep the tombstone (fail closed).
        return True
    if inc_tomb and not disk_tomb:
        if disk_pub > 0 or inc_pub > 0:
            return inc_pub < disk_pub
        # Prefer the incoming tombstone when wall times are absent.
        return False

    disk_exp = _ocsp_meta_unix(disk_meta, "expires_unix")
    inc_exp = _ocsp_meta_unix(incoming_meta, "expires_unix")
    if disk_exp != inc_exp:
        return disk_exp > inc_exp

    if disk_pub != inc_pub:
        return disk_pub > inc_pub

    # Last resort only: local forensic id, not a cluster vote.
    return _ocsp_job_run_id_rank(disk_meta.get("job_run_id")) >= _ocsp_job_run_id_rank(incoming_meta.get("job_run_id"))


def ocsp_restore_skip_fingerprints(cache_files: list, cache_root: Path) -> Dict[str, str]:
    """Compatibility wrapper: fingerprint → fence reason only."""
    skip, _caps = ocsp_restore_plan(cache_files, cache_root)
    return skip


def ocsp_restore_plan(cache_files: list, cache_root: Path) -> Tuple[Dict[str, str], Dict[str, int]]:
    """
    Plan OCSP restore coherence for one cache batch.

    Returns:
      skip: fingerprint → reason for shards that must not be overwritten
      floor_caps: fingerprint → max floor published_unix allowed when that shard
        was fenced as a still-GOOD trio (prevents floor sitting ahead of kept files)
    """
    by_fp: Dict[str, Dict[str, Any]] = {}
    incoming_floors: Dict[str, Optional[Dict[str, Any]]] = {}
    for entry in cache_files:
        if not isinstance(entry, dict):
            continue
        file_name = entry.get("file_name") or ""
        floor_fp = parse_ocsp_floor_cache_name(file_name)
        if floor_fp:
            incoming_floors[floor_fp] = parse_ocsp_floor_bytes(entry.get("data"))
            continue
        parsed = parse_ocsp_shard_cache_name(file_name)
        if not parsed:
            continue
        fp, leaf = parsed
        bucket = by_fp.setdefault(fp, {})
        if leaf == "ocsp.json" and entry.get("data"):
            bucket["incoming_meta"] = parse_ocsp_meta_bytes(entry["data"])
        elif leaf == "ocsp.der":
            # Row presence is enough; generate_caches plans with with_data=False.
            bucket["has_der"] = True

    skip: Dict[str, str] = {}
    floor_caps: Dict[str, int] = {}
    root = Path(cache_root)
    for fp, bucket in by_fp.items():
        shard_dir = root / fp[0] / fp[1] / fp
        disk_meta = load_disk_ocsp_meta(shard_dir)
        if not isinstance(disk_meta, dict):
            continue
        incoming_meta = bucket.get("incoming_meta")
        # DER-only restore without meta: keep disk when it already has usable meta.
        if incoming_meta is None and bucket.get("has_der"):
            skip[fp] = "disk_meta_present_incoming_meta_missing"
            disk_pub = _ocsp_meta_unix(disk_meta, "published_unix")
            if disk_pub > 0 and disk_meta.get("tombstoned") is not True:
                floor_caps[fp] = disk_pub
            continue
        if not should_keep_disk_ocsp_shard(disk_meta, incoming_meta):
            continue

        disk_pub = _ocsp_meta_unix(disk_meta, "published_unix")
        # Effective floor after a naive max-only floor restore.
        effective_floor = max(
            ocsp_floor_published_unix(load_disk_ocsp_floor(root, fp)),
            ocsp_floor_published_unix(incoming_floors.get(fp)),
        )
        # Prefer a DB generation that meets the floor over fencing a lagging GOOD
        # that would leave Must-Staple closed on healthy-looking files.
        if (
            disk_meta.get("tombstoned") is not True
            and disk_pub > 0
            and effective_floor > disk_pub
            and isinstance(incoming_meta, dict)
            and incoming_meta.get("tombstoned") is not True
            and _ocsp_meta_unix(incoming_meta, "published_unix") >= effective_floor
            and bucket.get("has_der")
        ):
            continue

        skip[fp] = (
            f"disk_newer_or_equal expires_unix={_ocsp_meta_unix(disk_meta, 'expires_unix')} "
            f"job_run_id={disk_meta.get('job_run_id')}"
        )
        if disk_meta.get("tombstoned") is not True and disk_pub > 0:
            floor_caps[fp] = disk_pub
    return skip, floor_caps


class Job:
    def __init__(self, logger: Logger, job_path: Optional[Union[str, Path]] = None, db=None, *, deprecated: bool = False):
        """Initialize Job class."""
        if job_path:
            job_path = Path(job_path)
            plugin_id = job_path.parent.parent.name
            job_name = job_path.stem
        else:
            frame = currentframe()
            if not frame:
                raise ValueError("frame could not be determined.")

            source_path = Path(getframeinfo(frame.f_back).filename)

            if not source_path.exists():
                raise ValueError("source_file could not be determined.")

            plugin_id = source_path.parent.parent.name
            job_name = job_name or source_path.name.replace(".py", "")

        if not job_name:
            raise ValueError("Could not determine job name.")

        # Set job_path and job_name
        self.job_path = Path(sep, "var", "cache", "bunkerweb", plugin_id)
        self.job_name = job_name

        # Additional validation for job_path
        if self.job_path == Path(sep, "var", "cache", "bunkerweb"):
            raise ValueError("Could not determine job path. Ensure passed_plugin_id is valid.")

        self.job_path.mkdir(parents=True, exist_ok=True)

        self.db = db
        if not self.db:
            from Database import Database  # type: ignore

            self.db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"))
        self.logger = logger or self.db.logger

        # Tracks whether the most recent cache restore succeeded. Callers that subsequently
        # re-cache their on-disk state (e.g. certbot-new / certbot-renew) MUST check this
        # flag before overwriting the DB — otherwise a failed restore + successful re-cache
        # silently wipes the good cached data from both disk and DB.
        self.restore_ok = True

        if not deprecated:
            try:
                db_metadata = self.db.get_metadata()
                if not isinstance(db_metadata, str) and not db_metadata["scheduler_first_start"]:
                    self.restore_ok = self.restore_cache(manual=False)
            except BaseException as e:
                # Any unexpected failure during auto-restore must fail closed so that
                # downstream re-caching guards still hold — a crash here would have
                # skipped the guards entirely and left job scripts thinking restore_ok
                # was still the default True.
                self.restore_ok = False
                self.logger.error(f"Exception while auto-restoring cache in Job.__init__ for plugin '{self.job_path.name}': {e}")

    def restore_cache(self, *, job_name: str = "", plugin_id: str = "", manual: bool = True) -> bool:
        """Restore job cache files from database."""
        ret = True
        job_cache_files = self.db.get_jobs_cache_files(plugin_id=plugin_id or self.job_path.name)  # type: ignore

        job_name = job_name or self.job_name
        plugin_cache_files = set()
        ignored_dirs = set()
        crs_manifest = None
        crs_archive_name = f"folder:{self.job_path / 'crs/plugins'}.tgz"
        mtls_pair = self.job_path.name == "mtls" and job_name == "client-cert"

        if mtls_pair:
            try:
                with LOCK:
                    ignored_dirs.update(restore_mtls_cache(self.job_path, [row for row in job_cache_files if row["job_name"] == job_name]))
            except Exception as e:
                self.logger.error(f"Error restoring mTLS cache pairs: {e}")
                return False

        if self.job_path.name == "modsecurity" and job_name == "download-crs-plugins":
            try:
                with LOCK:
                    recover_directory(self.job_path / "crs/plugins")
            except Exception as e:
                self.logger.error(f"Error recovering CRS plugin publication: {e}")
                return False
            crs_rows = {row["file_name"]: row for row in job_cache_files if row["job_name"] == job_name}
            if ("crs-plugins.json" in crs_rows) != (crs_archive_name in crs_rows):
                self.logger.error("Incomplete CRS plugin cache pair; keeping the existing directory and manifest")
                return False
            crs_manifest = crs_rows.get("crs-plugins.json")

        # Recover all pending swaps before restoring a companion file from the DB.
        for row in job_cache_files:
            if row["job_name"] != job_name or not row["file_name"].endswith(".tgz"):
                continue
            target = self.job_path.joinpath(row["service_id"] or "", row["file_name"]).parent
            try:
                if row["file_name"].startswith("folder:"):
                    target = checked_folder_target(row["file_name"])
                with LOCK:
                    recover_directory(target)
            except Exception as e:
                self.logger.error(f"Error recovering cache directory {target}: {e}")
                return False

        # Never regress a newer on-disk OCSP shard with an older DB complete trio.
        # Floor caps keep cluster floor from sitting ahead of a fenced still-GOOD trio.
        ocsp_skip: Dict[str, str] = {}
        ocsp_floor_caps: Dict[str, int] = {}
        restored_ocsp_fps: Set[str] = set()
        if self.job_path.name == "ssl":
            try:
                ocsp_skip, ocsp_floor_caps = ocsp_restore_plan(list(job_cache_files or []), self.job_path)
            except Exception as e:
                self.logger.debug(f"OCSP restore fence unavailable: {e}")

        for job_cache_file in job_cache_files:
            cache_path = self.job_path.joinpath(job_cache_file["service_id"] or "", job_cache_file["file_name"])
            plugin_cache_files.add(cache_path)
            if crs_manifest is not None and job_cache_file is crs_manifest:
                continue
            if mtls_pair and job_cache_file["job_name"] == job_name and job_cache_file["file_name"] in ("ca.pem", "crl.pem"):
                continue

            try:
                if job_cache_file["file_name"].endswith(".tgz"):
                    extract_path = cache_path.parent
                    if job_cache_file["file_name"].startswith("folder:"):
                        extract_path = checked_folder_target(job_cache_file["file_name"])
                    if job_cache_file["job_name"] != job_name:
                        ignored_dirs.add(extract_path)
                        ignored_dirs.update(transaction_markers(extract_path))
                        continue
                    with LOCK:
                        if crs_manifest is not None and job_cache_file["file_name"] == crs_archive_name:
                            restore_directory(extract_path, job_cache_file["data"], self.job_path / "crs-plugins.json", crs_manifest["data"])
                        else:
                            restore_directory(extract_path, job_cache_file["data"])
                        ignored_dirs.add(extract_path)
                        ignored_dirs.update(transaction_markers(extract_path))
                        self.logger.debug(f"Restored cache directory {extract_path}")
                    continue
                elif job_cache_file["job_name"] != job_name:
                    continue
                parsed = parse_ocsp_shard_cache_name(job_cache_file.get("file_name") or "")
                if parsed and parsed[0] in ocsp_skip:
                    self.logger.info(
                        f"OCSP restore skip fp={parsed[0][:16]}... leaf={parsed[1]} reason={ocsp_skip[parsed[0]]}"
                    )
                    ignored_dirs.add(cache_path.parent)
                    continue
                # Cluster floor: max-only, but never raise above a fenced still-GOOD shard.
                floor_fp = parse_ocsp_floor_cache_name(job_cache_file.get("file_name") or "")
                if floor_fp:
                    incoming_floor = parse_ocsp_floor_bytes(job_cache_file.get("data"))
                    disk_floor = load_disk_ocsp_floor(self.job_path, floor_fp)
                    skip_floor, floor_reason = should_skip_ocsp_floor_restore(
                        disk_floor, incoming_floor, ocsp_floor_caps.get(floor_fp)
                    )
                    if skip_floor:
                        self.logger.info(f"OCSP floor restore skip fp={floor_fp[:16]}... reason={floor_reason}")
                        ignored_dirs.add(cache_path.parent)
                        continue
                _write_atomic(checked_cache_path(self.job_path, job_cache_file["service_id"] or "", job_cache_file["file_name"]), job_cache_file["data"])
                ignored_dirs.add(cache_path.parent)
                if parsed:
                    restored_ocsp_fps.add(parsed[0])
                self.logger.debug(
                    "Restored cache file " + ((job_cache_file["service_id"] + "/") if job_cache_file["service_id"] else "") + job_cache_file["file_name"]
                )
            except BaseException as e:
                self.logger.error(
                    "Exception while restoring cache file "
                    + ((job_cache_file["service_id"] + "/") if job_cache_file["service_id"] else "")
                    + job_cache_file["file_name"]
                    + f" :\n{e}"
                )
                ret = False

        if restored_ocsp_fps:
            try:
                publish_ocsp_restore_coherence(self.job_path, restored_ocsp_fps, self.logger)
            except Exception as e:
                self.logger.warning(f"OCSP restore coherence failed: {e}")

        with LOCK:
            # An empty row set means the plugin's cache is unknown, not that everything on disk is
            # unused: `startswith(())` is always False, so the sweep below would delete every file
            # under job_path while ret stays True. For Let's Encrypt that is the accounts, archives
            # and live symlinks, destroyed by deleting one cache row from the web UI.
            if not job_cache_files and self.job_path.is_dir() and any(self.job_path.iterdir()):
                self.logger.warning(f"No cache row for plugin '{self.job_path.name}'; keeping the files already in {self.job_path} instead of clearing them.")
            elif ret and not manual and self.job_path.is_dir():
                # Deepest first: unlink stale non-cached files, then drop only now-empty dirs —
                # never rmtree the job_path root (its children are freshly restored cache dirs).
                for file in sorted(cache_tree(self.job_path), key=lambda p: len(p.parts), reverse=True):
                    if is_preserved(file, ignored_dirs):
                        continue

                    self.logger.debug(f"Checking if {file} should be removed")
                    if (file.is_symlink() or file.is_file()) and file not in plugin_cache_files:
                        rel = file.relative_to(self.job_path).as_posix()
                        if self.job_path.name == "ssl" and (rel == ".ocsp_epoch" or rel.startswith("ocsp-refuse/")):
                            continue
                        parsed = parse_ocsp_shard_cache_name(rel)
                        if parsed and parsed[0] in ocsp_skip:
                            continue
                        # Never wipe a local cluster floor (max-only; may outrank DB).
                        if parse_ocsp_floor_cache_name(rel):
                            continue
                        self.logger.debug(f"Removing non-cached file {file}")
                        file.unlink(missing_ok=True)
                    elif not file.is_symlink() and file.is_dir() and file != self.job_path and not any(file.iterdir()):
                        if self.job_path.name == "ssl" and (
                            file == self.job_path / "ocsp-floor"
                            or file.parent == self.job_path / "ocsp-floor"
                            or file == self.job_path / "ocsp-refuse"
                            or file.parent == self.job_path / "ocsp-refuse"
                        ):
                            continue
                        self.logger.debug(f"Removing empty directory {file}")
                        rmtree(file, ignore_errors=True)

        return ret

    def get_cache(
        self, name: Union[str, Path], *, job_name: str = "", service_id: str = "", plugin_id: str = "", with_info: bool = False, with_data: bool = True
    ) -> Optional[Union[Dict[str, Any], bytes]]:
        """Get cache file from database or from local cache file."""
        if isinstance(name, Path):
            name = str(name)

        try:
            cache_path = checked_cache_path(self.job_path, service_id, name)
        except ValueError as error:
            self.logger.error(f"Refusing to read cache entry {name!r}: {error}")
            return None
        ret_data = {}
        if cache_path.is_file():
            if with_data and not with_info:
                return cache_path.read_bytes()
            if with_data:
                ret_data["data"] = cache_path.read_bytes()

        if not ret_data:
            return self.db.get_job_cache_file(job_name or self.job_name, name, service_id=service_id, plugin_id=plugin_id or self.job_path.name, with_info=with_info, with_data=with_data)  # type: ignore
        ret_data.update(self.db.get_job_cache_file(job_name or self.job_name, name, service_id=service_id, plugin_id=plugin_id or self.job_path.name, with_info=True, with_data=False) or {})  # type: ignore
        return ret_data

    def is_cached_file(
        self, name: Union[str, Path], expire: Literal["hour", "day", "week", "month"], *, job_name: str = "", service_id: str = "", plugin_id: str = ""
    ) -> bool:
        """Check if cache file is cached and if it's still fresh."""
        if isinstance(name, Path):
            name = str(name)

        is_cached = False
        try:
            cache_info = self.get_cache(name, job_name=job_name, service_id=service_id, plugin_id=plugin_id, with_info=True, with_data=False)
            if isinstance(cache_info, dict) and cache_info.get("last_update"):
                current_time = datetime.now().astimezone().timestamp()
                if current_time < cache_info["last_update"]:
                    return False
                is_cached = current_time - cache_info["last_update"] < EXPIRE_TIME[expire]
        except BaseException:
            is_cached = False
        return is_cached

    def cache_file(
        self,
        name: Union[str, Path],
        file_cache: Union[bytes, str, Path],
        *,
        job_name: str = "",
        service_id: str = "",
        checksum: Optional[str] = None,
        delete_file: bool = True,
        overwrite_file: bool = True,
    ) -> Tuple[bool, str]:
        """Cache file in database and in local cache file."""
        if isinstance(name, Path):
            name = str(name)

        ret, err = True, "success"
        cache_path = self.job_path.joinpath(service_id, name)
        if not name.startswith("folder:"):
            try:
                cache_path = checked_cache_path(self.job_path, service_id, name)
            except ValueError as error:
                return False, str(error)

        if isinstance(file_cache, bytes):
            content = file_cache
        else:
            if isinstance(file_cache, str):
                file_cache = Path(file_cache)
            assert isinstance(file_cache, Path)
            content = file_cache.read_bytes()

        if not name.startswith("folder:") and (overwrite_file or not cache_path.is_file()):
            _write_atomic(cache_path, content)

        if not checksum:
            checksum = bytes_hash(content)

        try:
            err = self.db.upsert_job_cache(service_id, name, content, job_name=job_name or self.job_name, checksum=checksum)  # type: ignore
            if err:
                ret = False

            if ret and isinstance(file_cache, Path) and delete_file and file_cache.resolve() != cache_path:
                file_cache.unlink(missing_ok=True)
        except:
            return False, f"exception :\n{format_exc()}"
        return ret, err

    def cache_dir(self, dir_path: Union[str, Path], *, job_name: str = "", service_id: str = "") -> Tuple[bool, str]:
        """Cache directory in database and in local cache file."""
        if isinstance(dir_path, str):
            dir_path = Path(dir_path)
        assert isinstance(dir_path, Path)

        file_name = f"folder:{dir_path.as_posix()}.tgz"
        content = BytesIO()
        # Pin the gzip header (mtime=0, no stored name) so an unchanged directory always produces
        # the same bytes. The header otherwise carries the current time, every rebuild got a fresh
        # checksum, and upsert_job_cache rewrote the whole blob each call -- ~48 MiB per reload for
        # failover-backup. tarfile.add() already walks the tree in sorted order.
        with GzipFile(filename="", fileobj=content, mode="wb", compresslevel=9, mtime=0) as gz:
            with tar_open(fileobj=gz, mode="w") as tgz:
                tgz.add(dir_path, arcname=".")
        content.seek(0, 0)

        return self.cache_file(file_name, content.getvalue(), job_name=job_name, service_id=service_id)

    def del_cache(self, name: Union[str, Path], *, job_name: str = "", service_id: str = "") -> Tuple[bool, str]:
        """Delete cache file from database and local cache file.

        Returns (deleted, error): error is "" on success, including when no database row existed."""
        if isinstance(name, Path):
            name = str(name)

        ret, err = True, "success"
        job_name = job_name or self.job_name
        job_path = self.job_path.joinpath(service_id)
        try:
            cache_path = checked_cache_path(self.job_path, service_id, name)
        except ValueError as error:
            return False, str(error)

        if cache_path.is_file():
            cache_path.unlink(missing_ok=True)

        if job_path.is_dir() and not list(job_path.iterdir()):
            rmtree(job_path, ignore_errors=True)

        try:
            err = self.db.delete_job_cache(name, job_name=job_name, service_id=service_id)  # type: ignore
            if err:
                return False, err
        except:
            return False, f"exception :\n{format_exc()}"
        return ret, ""

    def cache_hash(self, name: Union[str, Path], *, job_name: str = "", service_id: str = "", plugin_id: str = "") -> Optional[str]:
        """Get cache file hash from database or from local cache file."""
        if isinstance(name, Path):
            name = str(name)

        try:
            cache_path = checked_cache_path(self.job_path, service_id, name)
        except ValueError as error:
            self.logger.error(f"Refusing to hash cache entry {name!r}: {error}")
            return None
        if cache_path.is_file():
            return file_hash(cache_path)

        cache_info = self.get_cache(name, with_info=True, with_data=False, job_name=job_name, service_id=service_id, plugin_id=plugin_id)

        if isinstance(cache_info, dict):
            return cache_info.get("checksum")
        return None


# ? Backward compatibility functions


def is_cached_file(file: Union[str, Path], expire: Literal["hour", "day", "week", "month"], db) -> bool:
    job = Job(None, db, deprecated=True)
    job.logger.warning("is_cached_file is deprecated, use the Job.is_cached_file method instead.")
    if not isinstance(file, Path):
        file = Path(file)
    return job.is_cached_file(file.name, expire)


def get_file_in_db(file: Union[str, Path], db, *, job_name: str = "") -> Optional[bytes]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("get_file_in_db is deprecated, use the Job.get_cache method instead.")
    if not isinstance(file, Path):
        file = Path(file)
    cache = job.get_cache(file.name, job_name=job_name, with_data=True)
    if isinstance(cache, dict):
        return cache.get("data")
    return None


def set_file_in_db(name: str, content: bytes, db, *, job_name: str = "", service_id: str = "", checksum: Optional[str] = None) -> Tuple[bool, str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("set_file_in_db is deprecated, use the Job.cache_file method instead.")
    return job.cache_file(name, content, job_name=job_name, service_id=service_id, checksum=checksum)


def del_file_in_db(name: str, db, *, service_id: str = "") -> Tuple[bool, str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("del_file_in_db is deprecated, use the Job.del_cache method instead.")
    return job.del_cache(name, service_id=service_id)


def cache_hash(cache: Union[str, Path], db) -> Optional[str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("cache_hash is deprecated, use the Job.cache_hash method instead.")
    if not isinstance(cache, Path):
        cache = Path(cache)
    return job.cache_hash(cache.name)


def cache_file(
    file: Union[str, Path], cache: Union[str, Path], _hash: Optional[str], db, *, delete_file: bool = True, service_id: str = ""
) -> Tuple[bool, str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("cache_file is deprecated, use the Job.cache_file method instead.")
    if not isinstance(file, Path):
        file = Path(file)
    if not isinstance(cache, Path):
        cache = Path(cache)
    return job.cache_file(cache.name, file, job_name=cache.name, service_id=service_id, checksum=_hash, delete_file=delete_file)
