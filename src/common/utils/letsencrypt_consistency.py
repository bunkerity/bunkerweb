"""Single source of truth for Let's Encrypt cache consistency.

Both the UI blueprint and the scheduler jobs validate that every
`renewal/<cert>.conf` references an ACME account whose `regr.json` exists
on disk. Keeping the implementation in one place avoids the drift that
killed every previous attempt at "keep these two functions in sync".

Imported by:
  - src/common/core/letsencrypt/jobs/letsencrypt_utils.py (scheduler)
  - src/common/core/letsencrypt/jobs/certbot-renew.py     (scheduler)
  - src/common/core/letsencrypt/jobs/certbot-new.py       (scheduler)
  - src/common/core/letsencrypt/ui/blueprints/letsencrypt.py (UI)
  - src/common/core/letsencrypt/ui/hooks.py                  (UI)
"""

import fcntl
import os
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from os.path import sep
from pathlib import Path
from shutil import move, rmtree
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Shared sentinel: UI heal/delete and scheduler renew/new flock this path so the last writer
# of the LE DB cache row doesn't silently win. Must stay OUTSIDE /var/cache/bunkerweb/letsencrypt:
# that dir is a Job.job_path whose restore_cache cleanup deletes stray files in it.
LE_CACHE_LOCK_PATH = Path(sep, "var", "cache", "bunkerweb", ".letsencrypt-cache-write.lock")

# Where sanitize_le_cache moves broken lineages. Same rationale as LE_CACHE_LOCK_PATH: it MUST live
# outside /var/cache/bunkerweb/letsencrypt so the job's restore/re-tar cycle never sees it and can
# neither wipe the quarantine nor fold a broken lineage back into the DB cache blob.
QUARANTINE_ROOT = Path(sep, "var", "cache", "bunkerweb", ".letsencrypt-quarantine")


@contextmanager
def le_cache_write_lock() -> Iterator[None]:
    """Serialize LE DB cache-row writes across the UI and scheduler processes (flock LOCK_EX).

    Per-host only; multi-host UI would need DB-side optimistic concurrency (follow-up).
    """
    LE_CACHE_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LE_CACHE_LOCK_PATH.as_posix(), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def letsencrypt_cache_consistent(data_path: Path) -> Tuple[bool, str]:
    """Reject Let's Encrypt cache snapshots that would break renewals.

    Certbot stores each ACME account as a directory containing regr.json +
    private_key.json + meta.json. The path under accounts/ varies by CA:

      Let's Encrypt: accounts/<host>/directory/<account-id>/
      ZeroSSL:       accounts/acme.zerossl.com/v2/DV90/<account-id>/

    Certbot derives the path from the ACME server URL — `/directory` suffix
    in the URL becomes a path segment, no suffix means no segment. We discover
    accounts CA-agnostically by walking `accounts_root.rglob("regr.json")`;
    the parent directory's name IS the account id stored in renewal confs.

    If renewal/*.conf references an account id whose `regr.json` is missing,
    `certbot renew` aborts with AccountNotFound for every cert pointing at it,
    and a blind re-cache from that empty state self-propagates the broken
    snapshot back into the DB cache row.

    The `account = None` sentinel emitted by certbot when no account is
    registered is NOT treated as a referenced account (see certbot
    _internal/constants.py and tests/testdata/sample-renewal*.conf).

    Returns (consistent, reason). `consistent=False` means callers MUST refuse
    to overwrite the canonical DB cache row.
    """
    renewal_dir = data_path.joinpath("renewal")
    accounts_root = data_path.joinpath("accounts")
    if not renewal_dir.is_dir():
        return True, ""

    referenced_accounts = set()
    for conf in renewal_dir.glob("*.conf"):
        try:
            for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
                key, sep_char, value = line.partition("=")
                if sep_char and key.strip() == "account":
                    account_id = value.strip()
                    if account_id and account_id != "None":
                        referenced_accounts.add(account_id)
                    break
        except OSError:
            continue

    if not referenced_accounts:
        return True, ""

    if not accounts_root.is_dir():
        return False, f"renewal/ references {len(referenced_accounts)} account(s) but accounts/ dir is missing"

    on_disk_accounts = set()
    with suppress(OSError):
        for regr in accounts_root.rglob("regr.json"):
            if regr.is_file() and regr.parent.is_dir():
                on_disk_accounts.add(regr.parent.name)

    missing = referenced_accounts - on_disk_accounts
    if missing:
        sample_missing = sorted(missing)[:10]
        sample_on_disk = sorted(on_disk_accounts)[:10]
        return False, (
            f"renewal/ references missing account(s) {sample_missing}"
            f"{'...' if len(missing) > 10 else ''}; "
            f"on-disk accounts: {sample_on_disk or '[]'}"
            f"{'...' if len(on_disk_accounts) > 10 else ''}"
        )
    return True, ""


def detect_orphan_renewals(data_path: Path) -> List[Dict[str, str]]:
    """List every renewal/*.conf whose ACME account is missing on disk.

    These are the "orphan" certs that block cache writeback and will fail
    `certbot renew` with AccountNotFound. Returns one dict per orphan:
    `{ cert_name, account, server }`.
    """
    orphans: List[Dict[str, str]] = []
    renewal_dir = data_path.joinpath("renewal")
    accounts_root = data_path.joinpath("accounts")
    if not renewal_dir.is_dir():
        return orphans

    on_disk_accounts = set()
    if accounts_root.is_dir():
        with suppress(OSError):
            for regr in accounts_root.rglob("regr.json"):
                if regr.is_file() and regr.parent.is_dir():
                    on_disk_accounts.add(regr.parent.name)

    for conf in renewal_dir.glob("*.conf"):
        account_id = ""
        server = ""
        try:
            for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
                key, sep_char, value = line.partition("=")
                if not sep_char:
                    continue
                k = key.strip()
                v = value.strip()
                if k == "account" and v and v != "None":
                    account_id = v
                elif k == "server" and v:
                    server = v
        except OSError:
            continue

        if account_id and account_id not in on_disk_accounts:
            orphans.append({"cert_name": conf.stem, "account": account_id, "server": server})
    return orphans


# Filesystem-safe cert name regex. Same character class certbot uses internally,
# minus path-traversal sentinels that would resolve out of `live/`, `archive/`,
# `renewal/` when joined naively. Empty / pure-dot strings rejected.
_CERT_NAME_FORBIDDEN = frozenset({"", ".", ".."})


def is_safe_cert_name(cert_name: str) -> bool:
    """Validate a cert_name received from an HTTP route.

    Allowed: `[A-Za-z0-9._-]+` minus standalone `.` and `..` (path-traversal).
    Rejects empty strings, single/double-dot, and anything containing path
    separators or other shell metacharacters. Use in conjunction with a
    post-join resolved-path containment check for defense in depth.
    """
    import re

    if cert_name in _CERT_NAME_FORBIDDEN:
        return False
    if not re.fullmatch(r"[A-Za-z0-9._-]+", cert_name):
        return False
    return True


def path_is_inside(child: Path, parent: Path) -> bool:
    """Return True iff `child` resolves under `parent` after symlink resolution.

    Belt-and-suspenders check against path traversal even if a regex slips.
    Both args are resolved via `Path.resolve(strict=False)`.
    """
    try:
        child_resolved = child.resolve(strict=False)
        parent_resolved = parent.resolve(strict=False)
    except (OSError, ValueError):
        return False
    try:
        child_resolved.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def _read_lineage_paths(conf_path: Path) -> Optional[Dict[str, str]]:
    """Parse a renewal conf's top-section path keys, or None if the file can't be read.

    Returns the archive_dir / cert / fullchain values (whichever are present). These keys
    only appear in the top section certbot writes, so a flat partition parse is unambiguous.
    """
    keys: Dict[str, str] = {}
    try:
        text = conf_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        key, sep_char, value = line.partition("=")
        if not sep_char:
            continue
        k = key.strip()
        if k in ("archive_dir", "cert", "fullchain") and k not in keys:
            keys[k] = value.strip()
    return keys


def _body_lineage_names(keys: Dict[str, str]) -> List[str]:
    """Lineage dir names a renewal conf body points at: archive_dir's name and cert's parent name."""
    names: List[str] = []
    if keys.get("archive_dir"):
        names.append(Path(keys["archive_dir"]).name)
    if keys.get("cert"):
        names.append(Path(keys["cert"]).parent.name)
    return [name for name in names if name]


def detect_broken_lineages(data_path: Path) -> List[Dict[str, Any]]:
    """List renewal/*.conf whose lineage is broken independently of the ACME account.

    A conf is broken when ANY of:
      (a) it can't be read, or carries neither an archive_dir nor a cert path;
      (b) a lineage name in its body (archive/<name>, live/<name>) differs from the filename
          stem — the signature that makes `certbot certificates`/`renew` fail to parse;
      (c) no certificate material exists (no live/<name>/fullchain.pem under data_path for the
          conf stem or any body-derived lineage name);
      (d) live/<stem>/fullchain.pem exists but is a regular file, not a symlink. Certbot
          requires every live/<name>/*.pem to be a symlink into archive/; a dereferenced
          regular file makes `certbot renew` raise CertStorageError ("expected ... to be a
          symlink") and certbot then issues unbounded duplicate -NNNN lineages.

    Healthy, wildcard, and `-ecdsa` lineages all keep body names equal to the stem and their
    live/ files as symlinks into archive/, so they are never flagged. Returns one dict per
    broken conf:
    { cert_name, reason, renewal_conf, lineage_names }.
    """
    broken: List[Dict[str, Any]] = []
    renewal_dir = data_path.joinpath("renewal")
    if not renewal_dir.is_dir():
        return broken

    for conf in sorted(renewal_dir.glob("*.conf")):
        stem = conf.stem
        keys = _read_lineage_paths(conf)
        body_names: List[str] = []
        reason = ""

        if keys is None:
            reason = "renewal conf could not be read"
        elif "archive_dir" not in keys and "cert" not in keys:
            reason = "renewal conf has neither an archive_dir nor a cert path"
        else:
            body_names = _body_lineage_names(keys)
            mismatched = sorted({name for name in body_names if name != stem})
            if mismatched:
                reason = f"lineage name mismatch: conf stem '{stem}' vs body {mismatched}"
            else:
                # Material presence must be a pure function of data_path. The body's `fullchain`
                # key is an absolute certbot path that, in the UI scratch context, would resolve
                # against the live host tree rather than this snapshot; check only data_path-anchored
                # live/<name>/fullchain.pem for the conf stem and any body-derived lineage name.
                live_fullchain = data_path.joinpath("live", stem, "fullchain.pem")
                has_material = any(data_path.joinpath("live", name, "fullchain.pem").exists() for name in {stem, *body_names})
                if not has_material:
                    reason = f"no certificate material for lineage '{stem}'"
                elif live_fullchain.exists() and not live_fullchain.is_symlink():
                    reason = f"live certificate files for lineage '{stem}' are not symlinks"

        if reason:
            broken.append(
                {
                    "cert_name": stem,
                    "reason": reason,
                    "renewal_conf": conf.as_posix(),
                    "lineage_names": sorted({stem, *body_names}),
                }
            )
    return broken


def purge_lineage(data_path: Path, conf_path: Path, quarantine_root: Optional[Path], logger=None) -> List[str]:
    """Remove or quarantine a renewal conf plus its live/ and archive/ dirs.

    Candidate lineage names are the conf stem AND any name its body points at (broken confs
    reference live/archive dirs under a name that differs from the stem, so removing only the
    stem's dirs would leave the real ones behind). A live/archive dir whose name is still the
    stem of another surviving renewal/*.conf is left untouched (shared-lineage guard). Every
    path is containment-checked against data_path before it is touched.

    quarantine_root=None hard-deletes; otherwise each path is moved (preserving its relative
    layout) under quarantine_root/<UTC timestamp>-<stem>/. Returns the paths acted on; never
    raises on an individual failure.
    """
    acted: List[str] = []

    names = {conf_path.stem}
    keys = _read_lineage_paths(conf_path)
    if keys:
        names.update(_body_lineage_names(keys))

    surviving_stems = set()
    renewal_dir = data_path.joinpath("renewal")
    if renewal_dir.is_dir():
        for other in renewal_dir.glob("*.conf"):
            if other != conf_path:
                surviving_stems.add(other.stem)

    stamp_dir: Optional[Path] = None
    if quarantine_root is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stamp_dir = quarantine_root.joinpath(f"{stamp}-{conf_path.stem}")

    def _act(path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        # Strict descendant only: reject anything that escapes data_path OR resolves to data_path
        # itself (a `..` component or a symlink would otherwise turn a per-lineage purge into a
        # whole-tree rmtree/move).
        if not path_is_inside(path, data_path) or path.resolve() == data_path.resolve():
            if logger is not None:
                logger.error(f"Refusing to purge {path}: it escapes or equals {data_path}")
            return
        try:
            # stamp_dir is None exactly when quarantine_root is None; testing it here narrows the
            # Optional for the move branch below.
            if stamp_dir is None:
                if path.is_dir() and not path.is_symlink():
                    rmtree(path, ignore_errors=False)
                else:
                    path.unlink(missing_ok=True)
            else:
                try:
                    rel = path.relative_to(data_path)
                except ValueError:
                    rel = Path(path.name)
                dest = stamp_dir.joinpath(rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                move(path.as_posix(), dest.as_posix())
            acted.append(path.as_posix())
        except OSError as e:
            if logger is not None:
                logger.error(f"Failed to purge {path}: {e}")

    _act(conf_path)
    for name in sorted(names):
        # Candidate names include the conf stem and body-derived names, both attacker-influenceable
        # after a DB compromise. A name like '..' would resolve live/<name> back to data_path itself,
        # so gate every name through is_safe_cert_name (rejects '', '.', '..', and path separators).
        if not is_safe_cert_name(name):
            if logger is not None:
                logger.error(f"Refusing to purge lineage dir for unsafe name {name!r}")
            continue
        if name in surviving_stems:
            continue
        _act(data_path.joinpath("live", name))
        _act(data_path.joinpath("archive", name))
    return acted


# ponytail: fixed 30-day retention; make it configurable if operators ever need to keep quarantined
# lineages longer for forensics.
_QUARANTINE_MAX_AGE_SECONDS = 30 * 24 * 3600


def _reap_quarantine() -> None:
    """Delete quarantine subdirs older than _QUARANTINE_MAX_AGE_SECONDS. Best-effort; never raises.

    Without this the quarantine grows without bound — a restore_ok=False loop re-quarantines the
    same lineage every tick.
    """
    if not QUARANTINE_ROOT.is_dir():
        return
    cutoff = datetime.now(timezone.utc).timestamp() - _QUARANTINE_MAX_AGE_SECONDS
    with suppress(OSError):
        for child in QUARANTINE_ROOT.iterdir():
            with suppress(OSError):
                if child.stat().st_mtime >= cutoff:
                    continue
                if child.is_dir():
                    rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)


def sanitize_le_cache(data_path: Path, logger) -> List[str]:
    """Quarantine every broken lineage under data_path; return the quarantined cert names."""
    _reap_quarantine()
    quarantined: List[str] = []
    for entry in detect_broken_lineages(data_path):
        acted = purge_lineage(data_path, Path(entry["renewal_conf"]), quarantine_root=QUARANTINE_ROOT, logger=logger)
        if not acted:
            continue
        quarantined.append(entry["cert_name"])
        if logger is not None:
            logger.warning(
                f"Quarantined broken Let's Encrypt lineage '{entry['cert_name']}' ({entry['reason']}); "
                f"moved {len(acted)} path(s) under {QUARANTINE_ROOT.as_posix()}"
            )
    return quarantined


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    def _write_conf(renewal_dir: Path, stem: str, lineage: str, root: Path) -> None:
        renewal_dir.joinpath(f"{stem}.conf").write_text(
            "version = 2.11.0\n"
            f"archive_dir = {root.joinpath('archive', lineage).as_posix()}\n"
            f"cert = {root.joinpath('live', lineage, 'cert.pem').as_posix()}\n"
            f"fullchain = {root.joinpath('live', lineage, 'fullchain.pem').as_posix()}\n"
            "\n[renewalparams]\n"
            "authenticator = manual\n"
            "account = deadbeef\n",
            encoding="utf-8",
        )

    def _make_material(root: Path, lineage: str) -> None:
        """Certbot layout: real files under archive/<lineage>/, live/<lineage>/ are symlinks into it."""
        archive = root.joinpath("archive", lineage)
        archive.mkdir(parents=True, exist_ok=True)
        live = root.joinpath("live", lineage)
        live.mkdir(parents=True, exist_ok=True)
        for name in ("cert", "chain", "fullchain", "privkey"):
            archive.joinpath(f"{name}1.pem").write_text(f"{name}-material", encoding="utf-8")
            live.joinpath(f"{name}.pem").symlink_to(Path("..", "..", "archive", lineage, f"{name}1.pem"))

    def _make_material_flat(root: Path, lineage: str) -> None:
        """The (d) breakage: live/<lineage>/ holds dereferenced regular files, not symlinks."""
        archive = root.joinpath("archive", lineage)
        archive.mkdir(parents=True, exist_ok=True)
        live = root.joinpath("live", lineage)
        live.mkdir(parents=True, exist_ok=True)
        for name in ("cert", "chain", "fullchain", "privkey"):
            archive.joinpath(f"{name}1.pem").write_text(f"{name}-material", encoding="utf-8")
            live.joinpath(f"{name}.pem").write_text(f"{name}-material", encoding="utf-8")

    with TemporaryDirectory() as tmp:
        root = Path(tmp, "etc")
        renewal = root.joinpath("renewal")
        renewal.mkdir(parents=True, exist_ok=True)

        # Healthy, wildcard base, and -ecdsa lineages all keep body name == stem.
        for stem in ("healthy.example.org", "example.com", "example.com-ecdsa"):
            _write_conf(renewal, stem, stem, root)
            _make_material(root, stem)

        # The #3733 signature: stem domain.se but body points at live/archive/domain.se.conf.
        _write_conf(renewal, "domain.se", "domain.se.conf", root)
        _make_material(root, "domain.se.conf")

        # Healthy-named lineage (stem == body names) but live/ was dereferenced into regular
        # files instead of symlinks into archive/ — the (d) breakage.
        _write_conf(renewal, "flattened.example.org", "flattened.example.org", root)
        _make_material_flat(root, "flattened.example.org")

        broken = detect_broken_lineages(root)
        assert [b["cert_name"] for b in broken] == ["domain.se", "flattened.example.org"], broken
        # Body-name alias: lineage_names carries BOTH the conf stem and the body name, so the UI can
        # match a row keyed off either. This is the contract /heal's alias resolution relies on.
        assert {"domain.se", "domain.se.conf"} <= set(broken[0]["lineage_names"]), broken[0]
        assert "not symlinks" in broken[1]["reason"], broken[1]

        quarantine = Path(tmp, "quarantine")
        acted = purge_lineage(root, renewal.joinpath("domain.se.conf"), quarantine_root=quarantine, logger=None)

        # Broken conf + its body-referenced dirs are gone from the tree, moved to quarantine.
        assert not renewal.joinpath("domain.se.conf").exists()
        assert not root.joinpath("live", "domain.se.conf").exists()
        assert not root.joinpath("archive", "domain.se.conf").exists()
        assert acted, "purge_lineage acted on nothing"
        assert list(quarantine.glob("*/renewal/domain.se.conf")), "conf not quarantined"

        # Healthy / wildcard / ecdsa lineages are untouched.
        for stem in ("healthy.example.org", "example.com", "example.com-ecdsa"):
            assert renewal.joinpath(f"{stem}.conf").exists(), stem
            assert root.joinpath("live", stem, "fullchain.pem").exists(), stem
            assert root.joinpath("archive", stem).exists(), stem

    # Path-traversal guard: a conf whose body points live/archive at a '..' component must NOT let
    # purge_lineage rmtree the whole tree (candidate names are attacker-influenceable).
    with TemporaryDirectory() as tmp:
        root = Path(tmp, "etc")
        renewal = root.joinpath("renewal")
        renewal.mkdir(parents=True, exist_ok=True)
        _write_conf(renewal, "good", "good", root)
        _make_material(root, "good")
        evil = renewal.joinpath("evil.conf")
        evil.write_text(
            f"archive_dir = {root.joinpath('archive', '..').as_posix()}\n" f"cert = {root.joinpath('live', '..', 'cert.pem').as_posix()}\n",
            encoding="utf-8",
        )
        purge_lineage(root, evil, quarantine_root=None, logger=None)
        assert root.is_dir(), "purge_lineage wiped data_path via '..'"
        assert renewal.joinpath("good.conf").exists(), "purge_lineage destroyed a healthy conf via '..'"
        assert root.joinpath("live", "good", "fullchain.pem").exists()
        assert not evil.exists(), "the malicious conf itself should still be removed"

    print("letsencrypt_consistency self-check passed")
