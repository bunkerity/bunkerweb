from contextlib import suppress
from io import BytesIO
from tarfile import open as tar_open
from time import time
from typing import Dict, List

from flask import request, session
from markupsafe import escape

# Default column visibility settings for letsencrypt tables
COLUMNS_PREFERENCES_DEFAULTS = {
    "3": True,
    "4": True,
    "5": True,
    "6": True,
    "7": True,
    "8": True,
    "9": False,
    "10": False,
    "11": True,
}

# Throttle orphan detection to at most once per N seconds per user session.
# The check reads the LE cache tar from DB (gzipped) and walks it in memory —
# cheap enough at this cadence to run from a context_processor on every page.
_ORPHAN_CHECK_INTERVAL_SECONDS = 60
_ORPHAN_CHECK_LAST_KEY = "_le_orphan_check_at"
_ORPHAN_NOTIFIED_KEY = "_le_orphan_notified"
_LE_CACHE_TGZ_FILENAME = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"

# Process-level result cache keyed by the cache row's checksum. Skips the
# tar walk entirely when the LE cache hasn't changed since the last check —
# turns the steady-state cost into a single SELECT for the checksum + a dict
# lookup. Shared across all gunicorn workers within the same process.
_ORPHAN_RESULT_BY_CHECKSUM: Dict[str, List[Dict[str, str]]] = {}
_ORPHAN_RESULT_CACHE_MAX = 4  # bound the cache; LE cache row changes are rare


def _detect_orphans_from_db_cache() -> List[Dict[str, str]]:
    """Detect orphan renewal confs by reading the DB cache tar in memory.

    Two-step lookup:
      1. Fast path: fetch metadata only (checksum, no data column). If the
         checksum matches a result we already computed, return cached orphans.
      2. Slow path: fetch the tar blob, walk it in memory, cache the result
         keyed by checksum so the next check at the same content is free.

    Avoids touching the on-disk UI tmp dir — no rmtree, no extract — so this
    is safe to call from a per-request context_processor (throttled by caller).
    Returns one dict per orphan: { cert_name, account, server }.
    """
    try:
        from app.dependencies import DB  # type: ignore
    except Exception:
        return []

    # Step 1: metadata-only fetch to check if we can short-circuit via checksum.
    cached_checksum = ""
    try:
        meta_files = DB.get_jobs_cache_files(with_data=False, job_name="certbot-renew")
        for meta in meta_files:
            if meta.get("file_name") == _LE_CACHE_TGZ_FILENAME:
                cached_checksum = str(meta.get("checksum") or "")
                break
    except Exception:
        cached_checksum = ""

    if cached_checksum and cached_checksum in _ORPHAN_RESULT_BY_CHECKSUM:
        return _ORPHAN_RESULT_BY_CHECKSUM[cached_checksum]

    # Step 2: tar blob fetch + in-memory walk.
    try:
        cache_files = DB.get_jobs_cache_files(job_name="certbot-renew")
    except Exception:
        return []

    for cache_file in cache_files:
        if cache_file.get("file_name") != _LE_CACHE_TGZ_FILENAME:
            continue
        data = cache_file.get("data") or b""
        if not data:
            return []

        renewal_accounts: Dict[str, Dict[str, str]] = {}
        on_disk_account_ids: set = set()
        try:
            with tar_open(fileobj=BytesIO(data), mode="r:gz") as tar:
                for member in tar.getmembers():
                    name = member.name.lstrip("./")
                    if not name:
                        continue
                    if name.startswith("renewal/") and name.endswith(".conf") and member.isfile():
                        f = tar.extractfile(member)
                        if not f:
                            continue
                        content = f.read().decode(encoding="utf-8", errors="replace")
                        cert_name = name.removeprefix("renewal/").removesuffix(".conf")
                        account_id = ""
                        server = ""
                        for line in content.splitlines():
                            key, sep_char, value = line.partition("=")
                            if not sep_char:
                                continue
                            k = key.strip()
                            v = value.strip()
                            if k == "account" and v and v != "None":
                                account_id = v
                            elif k == "server" and v:
                                server = v
                        if account_id:
                            renewal_accounts[cert_name] = {"account": account_id, "server": server}
                    elif name.endswith("/regr.json") and member.isfile():
                        parent = name.rsplit("/", 1)[0]
                        account_id = parent.rsplit("/", 1)[-1] if "/" in parent else parent
                        on_disk_account_ids.add(account_id)
        except Exception:
            return []

        orphans = [
            {"cert_name": cert_name, "account": info["account"], "server": info["server"]}
            for cert_name, info in renewal_accounts.items()
            if info["account"] not in on_disk_account_ids
        ]

        # Cache by checksum so the next check on identical content is O(1).
        checksum = str(cache_file.get("checksum") or "") or cached_checksum
        if checksum:
            if len(_ORPHAN_RESULT_BY_CHECKSUM) >= _ORPHAN_RESULT_CACHE_MAX:
                _ORPHAN_RESULT_BY_CHECKSUM.pop(next(iter(_ORPHAN_RESULT_BY_CHECKSUM)))
            _ORPHAN_RESULT_BY_CHECKSUM[checksum] = orphans
        return orphans
    return []


def _flash_new_orphans(orphans: List[Dict[str, str]]) -> None:
    """Push a warning toast for any orphan not already flashed this session.

    Uses the global flash() helper so the message appears in the notifications
    sidebar across every UI page — operators don't need to be on /letsencrypt
    to see it. Healed orphans drop out of the notified set so re-occurrences
    re-flash naturally.
    """
    try:
        from app.utils import flash  # type: ignore
    except Exception:
        return

    notified = set(session.get(_ORPHAN_NOTIFIED_KEY, []))
    current = {o["cert_name"] for o in orphans}
    new_orphans = [o for o in orphans if o["cert_name"] not in notified]

    for orphan in new_orphans:
        # HTML-escape every value sourced from the DB cache row. cert_name comes
        # from a renewal/*.conf basename and account UUID from the conf body — both
        # are operator-mutable (and would carry attacker payload after a DB
        # compromise). Flash messages are rendered with Jinja's `|safe` so any raw
        # HTML here becomes stored XSS in the sidebar that appears on every page.
        safe_cert = escape(orphan["cert_name"])
        safe_account = escape(orphan["account"])
        message = (
            f"Let's Encrypt: orphan certificate <strong>{safe_cert}</strong> "
            f"references missing ACME account <code>{safe_account}</code>. "
            f"Renewals are blocked until healed. "
            f'<a href="/letsencrypt">Open Let\'s Encrypt page to heal</a>.'
        )
        try:
            flash(message, "warning", save=True)
        except Exception:
            continue

    if current != notified:
        session[_ORPHAN_NOTIFIED_KEY] = list(current)
        session.modified = True


def context_processor():
    """
    Flask context processor to inject variables into templates.

    This adds:
    - Column preference defaults for tables
    - Throttled detection of Let's Encrypt orphan renewal configs (renewal/<cert>.conf
      whose `account = X` UUID has no matching regr.json on disk). On new orphans,
      pushes a warning into the global notifications sidebar so operators don't have
      to be on the /letsencrypt page to see the alert.
    """
    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp", "/logout")):
        return None

    data = {"columns_preferences_defaults_letsencrypt": COLUMNS_PREFERENCES_DEFAULTS}

    # Throttled orphan check — runs at most once per _ORPHAN_CHECK_INTERVAL_SECONDS
    # per session. Broad-suppress so a failure never breaks rendering.
    with suppress(Exception):
        now = time()
        last_check = session.get(_ORPHAN_CHECK_LAST_KEY, 0)
        if now - last_check >= _ORPHAN_CHECK_INTERVAL_SECONDS:
            session[_ORPHAN_CHECK_LAST_KEY] = now
            session.modified = True
            orphans = _detect_orphans_from_db_cache()
            if orphans or session.get(_ORPHAN_NOTIFIED_KEY):
                # Only update the notified set when there's something to track —
                # avoids needlessly bumping session.modified on every check tick.
                _flash_new_orphans(orphans)

    return data
