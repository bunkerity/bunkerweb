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
from os.path import sep
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

# Shared sentinel: Let's Encrypt cache writers/readers flock this path so the last writer
# of the LE DB cache row doesn't silently win. Must stay OUTSIDE /var/cache/bunkerweb/letsencrypt:
# that dir is a Job.job_path whose restore_cache cleanup deletes stray files in it.
LE_CACHE_LOCK_PATH = Path(sep, "var", "cache", "bunkerweb", ".letsencrypt-cache-write.lock")


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
