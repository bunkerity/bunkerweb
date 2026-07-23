from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from html import escape
from os import getenv
from subprocess import DEVNULL, PIPE, STDOUT, run
from os.path import dirname, join, sep
from pathlib import Path
from shutil import rmtree
from io import BytesIO
from json import loads
from tarfile import open as tar_open
from tempfile import TemporaryDirectory
from traceback import format_exc
from typing import Dict, List, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_required

from common_utils import safe_tar_extractall  # type: ignore
from letsencrypt_consistency import (  # type: ignore
    detect_broken_lineages as _detect_broken_lineages,
    detect_orphan_renewals as _detect_orphan_renewals,
    is_safe_cert_name as _is_safe_cert_name,
    le_cache_write_lock as _le_cache_write_lock,
    letsencrypt_cache_consistent as _le_cache_consistent,
    path_is_inside as _path_is_inside,
    purge_lineage as _purge_lineage,
)
from app.dependencies import DB  # type: ignore
from app.utils import LOGGER  # type: ignore
from app.routes.utils import cors_required  # type: ignore

blueprint_path = dirname(__file__)

letsencrypt = Blueprint(
    "letsencrypt",
    __name__,
    static_folder=f"{blueprint_path}/static",
    template_folder=f"{blueprint_path}/templates",
)

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
LE_CACHE_DIR = join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc")
# Per-request scratch dirs land under this root. Previously a single fixed DATA_PATH
# was used, which produced:
#   - DATA_PATH race: parallel workers rmtree'd each other's mid-flight tars,
#     silently losing heals.
#   - Account-key persistence: private_key.json sat on disk between requests.
# Per-request TemporaryDirectory closes both. Each handler creates its own subtree
# under this root via `_ui_scratch_dir()`.
SCRATCH_ROOT = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt")
WORK_DIR_ROOT = join(SCRATCH_ROOT, "work")
LOGS_DIR = join(sep, "var", "tmp", "bunkerweb", "letsencrypt", "log")

DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

DATATABLE_COLUMNS = (
    None,
    None,
    "domain",
    "common_name",
    "issuer",
    "valid_from",
    "valid_to",
    "preferred_profile",
    "challenge",
    "key_type",
    "serial_number",
    "fingerprint",
    "version",
)

SEARCHABLE_FIELDS = (
    "domain",
    "common_name",
    "issuer",
    "issuer_server",
    "serial_number",
    "fingerprint",
    "version",
    "preferred_profile",
    "challenge",
    "authenticator",
    "key_type",
    "valid_from",
    "valid_to",
)


def _ui_scratch_dir() -> TemporaryDirectory:
    """Allocate a fresh per-request scratch tree under SCRATCH_ROOT.

    Lifetime is tied to the `with` block in each handler. Teardown removes the
    extracted accounts/, live/ keys, archive/, renewal/ — eliminating the
    long-lived ACME account JWK on disk between requests AND the DATA_PATH
    race where two workers' rmtree/extract sequences interleaved.
    """
    Path(SCRATCH_ROOT).mkdir(parents=True, exist_ok=True)
    return TemporaryDirectory(prefix="le-ui-", dir=SCRATCH_ROOT)


def _user_readonly() -> bool:
    """True when the current user lacks write permission (mirrors src/ui templates.py write-gate).

    Cert lifecycle (delete/heal) is writer-level, not admin-only: a read-only user must never be
    able to run certbot delete / purge_lineage and re-persist the DB cache blob.
    """
    return "write" not in getattr(current_user, "list_permissions", [])


def download_certificates(target: Path) -> None:
    """Restore the full Let's Encrypt config tree from the DB cache into `target`.

    Always extract every member (accounts/, renewal-hooks/, etc.) — selective
    extraction is unsafe when the caller may re-cache from `target` and silently
    drop subtrees the filter excluded.
    """
    target.mkdir(parents=True, exist_ok=True)
    for cache_file in DB.get_jobs_cache_files(job_name="certbot-renew"):
        if cache_file["file_name"].endswith(".tgz") and cache_file["file_name"].startswith("folder:"):
            with tar_open(fileobj=BytesIO(cache_file["data"]), mode="r:gz") as tar:
                safe_tar_extractall(tar, target.as_posix(), tar_filter="auto")


def _persist_le_cache_dir(source: Path, bypass_gate: bool = False) -> Optional[str]:
    """Re-tar `source` and upsert it into the DB cache row keyed by LE_CACHE_DIR.

    Returns None on success, or an error string describing why persistence
    was skipped or failed.

    `bypass_gate=True` skips the consistency gate — used by the explicit Heal
    flow where the operator intentionally removes an orphan; the resulting
    cache state may still carry other orphans but cannot be worse than before
    (we strictly remove a referenced-but-missing pair). The scheduler's own
    gate still protects against runtime poisoning, so this bypass is local
    to operator-initiated UI mutations.
    """
    if not bypass_gate:
        ok, reason = _le_cache_consistent(source)
        if not ok:
            LOGGER.error(f"Refusing to persist Let's Encrypt cache: {reason}. DB row left untouched.")
            return f"cache state inconsistent ({reason})"

    file_name = f"folder:{Path(LE_CACHE_DIR).as_posix()}.tgz"
    content = BytesIO()
    with tar_open(file_name, mode="w:gz", fileobj=content, compresslevel=9) as tgz:
        tgz.add(source.as_posix(), arcname=".")
    content.seek(0, 0)
    err = DB.upsert_job_cache("", file_name, content.getvalue(), job_name="certbot-renew")
    if err:
        return f"upsert_job_cache failed: {err}"
    err = DB.checked_changes(["plugins"], ["letsencrypt"], True)
    if err:
        return f"checked_changes failed: {err}"
    return None


def retrieve_certificates(source: Path):
    """Parse cert + renewal-conf metadata from an already-extracted scratch tree."""
    certificates = {
        "domain": [],
        "common_name": [],
        "issuer": [],
        "issuer_server": [],
        "valid_from": [],
        "valid_to": [],
        "serial_number": [],
        "fingerprint": [],
        "version": [],
        "preferred_profile": [],
        "challenge": [],
        "authenticator": [],
        "key_type": [],
    }

    renewal_file: Optional[Path] = None
    for cert_file in source.joinpath("live").glob("*/fullchain.pem"):
        domain = cert_file.parent.name
        certificates["domain"].append(domain)
        cert_info = {
            "common_name": domain,
            "issuer": "Unknown",
            "issuer_server": "Unknown",
            "valid_from": None,
            "valid_to": None,
            "serial_number": "Unknown",
            "fingerprint": "Unknown",
            "version": "Unknown",
            "preferred_profile": "classic",
            "challenge": "Unknown",
            "authenticator": "Unknown",
            "key_type": "Unknown",
        }
        try:
            certs = x509.load_pem_x509_certificates(cert_file.read_bytes())
            if not certs:
                raise ValueError(f"No certificates found in {cert_file}")
            cert = certs[0]
            subject = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if subject:
                cert_info["common_name"] = subject[0].value
            issuer = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if issuer:
                cert_info["issuer"] = issuer[0].value
            cert_info["valid_from"] = cert.not_valid_before.astimezone().isoformat()
            cert_info["valid_to"] = cert.not_valid_after.astimezone().isoformat()
            cert_info["serial_number"] = str(cert.serial_number)
            cert_info["fingerprint"] = cert.fingerprint(hashes.SHA256()).hex()
            cert_info["version"] = cert.version.name
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while parsing certificate {cert_file}: {e}")

        try:
            renewal_file = source.joinpath("renewal", f"{domain}.conf")
            if renewal_file.exists():
                with renewal_file.open("r") as f:
                    for line in f:
                        if line.startswith("preferred_profile = "):
                            cert_info["preferred_profile"] = line.split(" = ")[1].strip()
                        elif line.startswith("pref_challs = "):
                            cert_info["challenge"] = line.split(" = ")[1].strip().split(",")[0]
                        elif line.startswith("authenticator = "):
                            cert_info["authenticator"] = line.split(" = ")[1].strip()
                        elif line.startswith("server = "):
                            cert_info["issuer_server"] = line.split(" = ")[1].strip()
                        elif line.startswith("key_type = "):
                            cert_info["key_type"] = line.split(" = ")[1].strip()
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while parsing renewal configuration {renewal_file}: {e}")

        for key in cert_info:
            certificates[key].append(cert_info[key])

    return certificates


@letsencrypt.route("/letsencrypt", methods=["GET"])
@login_required
def letsencrypt_page():
    return render_template("letsencrypt.html")


@letsencrypt.route("/letsencrypt/fetch", methods=["POST"])
@login_required
@cors_required
def letsencrypt_fetch():
    cert_list = []

    def _normalize(value):
        if value is None:
            return ""
        return str(value)

    def _pane_value(value):
        normalized = _normalize(value)
        return normalized or "N/A"

    try:
        draw = int(request.form.get("draw", 1))
    except (TypeError, ValueError):
        draw = 1

    try:
        with _ui_scratch_dir() as tmp:
            scratch = Path(tmp)
            download_certificates(scratch)
            certs = retrieve_certificates(scratch)
            LOGGER.debug(f"Certificates: {certs}")
            # Tag each row with whether its renewal conf references a missing ACME account OR has a
            # broken lineage (stem/body name mismatch). The front-end uses this to render a per-row
            # "Heal" quick-action button. Rows are keyed off the live-dir basename, which for a
            # broken lineage is the BODY name (e.g. domain.se.conf), not the conf stem — so tag
            # every lineage_names alias (stem AND body names), not just the stem cert_name.
            orphan_names = {o["cert_name"] for o in _detect_orphan_renewals(scratch)}
            for b in _detect_broken_lineages(scratch):
                orphan_names.update(b["lineage_names"])
        for i, domain in enumerate(certs.get("domain", [])):
            cert_list.append(
                {
                    "domain": domain,
                    "common_name": certs.get("common_name", [""])[i],
                    "issuer": certs.get("issuer", [""])[i],
                    "issuer_server": certs.get("issuer_server", [""])[i],
                    "valid_from": certs.get("valid_from", [""])[i],
                    "valid_to": certs.get("valid_to", [""])[i],
                    "serial_number": certs.get("serial_number", [""])[i],
                    "fingerprint": certs.get("fingerprint", [""])[i],
                    "version": certs.get("version", [""])[i],
                    "preferred_profile": certs.get("preferred_profile", [""])[i],
                    "challenge": certs.get("challenge", [""])[i],
                    "authenticator": certs.get("authenticator", [""])[i],
                    "key_type": certs.get("key_type", [""])[i],
                    "is_orphan": domain in orphan_names,
                }
            )
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while fetching certificates: {e}")

    total_records = len(cert_list)

    search_value = (request.form.get("search[value]", "") or "").strip().lower()

    search_panes = defaultdict(list)
    for key, value in request.form.items():
        if key.startswith("searchPanes["):
            field = key.split("[")[1].split("]")[0]
            if value:
                search_panes[field].append(value)

    filtered_cert_list = list(cert_list)
    if search_value:
        filtered_cert_list = [
            cert for cert in filtered_cert_list if any(search_value in _normalize(cert.get(field, "")).lower() for field in SEARCHABLE_FIELDS)
        ]

    # Column-specific search (e.g. search panes)
    for idx, column_key in enumerate(DATATABLE_COLUMNS):
        if not column_key:
            continue
        raw_value = (request.form.get(f"columns[{idx}][search][value]", "") or "").strip()
        if not raw_value:
            continue

        search_terms = [term.strip().lower() for term in raw_value.split("|") if term.strip()]
        if not search_terms:
            continue

        filtered_cert_list = [cert for cert in filtered_cert_list if any(term in _normalize(cert.get(column_key, "")).lower() for term in search_terms)]

    # SearchPanes filtering
    if search_panes:
        for field, selected_values in search_panes.items():
            normalized_values = {_pane_value(value).lower() for value in selected_values if value is not None}
            if not normalized_values:
                continue
            filtered_cert_list = [cert for cert in filtered_cert_list if _pane_value(cert.get(field, "")).lower() in normalized_values]

    records_filtered = len(filtered_cert_list)

    # Prepare SearchPanes counts/options before pagination
    pane_fields = ("issuer", "preferred_profile", "challenge", "key_type")
    pane_counts = defaultdict(lambda: defaultdict(lambda: {"total": 0, "count": 0}))

    for cert in cert_list:
        for field in pane_fields:
            value = _pane_value(cert.get(field, ""))
            pane_counts[field][value]["total"] += 1

    for cert in filtered_cert_list:
        for field in pane_fields:
            value = _pane_value(cert.get(field, ""))
            pane_counts[field][value]["count"] += 1

    # Ordering
    try:
        order_idx = int(request.form.get("order[0][column]", -1))
    except (TypeError, ValueError):
        order_idx = -1

    if 0 <= order_idx < len(DATATABLE_COLUMNS):
        order_key = DATATABLE_COLUMNS[order_idx]
        if order_key:
            order_dir = request.form.get("order[0][dir]", "asc")
            reverse = order_dir == "desc"

            def sort_value(cert):
                value = cert.get(order_key)
                if order_key in {"valid_from", "valid_to"}:
                    try:
                        return datetime.fromisoformat(_normalize(value))
                    except (TypeError, ValueError):
                        return _normalize(value)
                return _normalize(value)

            filtered_cert_list.sort(key=sort_value, reverse=reverse)

    # Pagination
    try:
        start = int(request.form.get("start", 0))
    except (TypeError, ValueError):
        start = 0
    try:
        length = int(request.form.get("length", -1))
    except (TypeError, ValueError):
        length = -1

    if start < 0:
        start = 0
    if length == -1:
        paginated_cert_list = filtered_cert_list
    else:
        paginated_cert_list = filtered_cert_list[start : start + max(length, 0)]  # noqa: E203

    # Build SearchPanes options
    search_panes_options = {}
    for field, values in pane_counts.items():
        if not values:
            continue
        options = []
        for value, counts in sorted(values.items(), key=lambda item: item[0].lower()):
            label = escape(value)
            options.append(
                {
                    "label": label,
                    "value": value,
                    "total": counts["total"],
                    "count": counts["count"],
                }
            )
        if options:
            search_panes_options[field] = options

    return jsonify(
        {
            "data": paginated_cert_list,
            "recordsTotal": total_records,
            "recordsFiltered": records_filtered,
            "draw": draw,
            "searchPanes": {"options": search_panes_options},
        }
    )


@letsencrypt.route("/letsencrypt/delete", methods=["POST"])
@login_required
@cors_required
def letsencrypt_delete():
    if _user_readonly():
        return jsonify({"status": "ko", "message": "User is read-only"}), 403
    cert_name = request.json.get("cert_name") if request.is_json else None
    if not cert_name:
        return jsonify({"status": "ko", "message": "Missing cert_name"}), 400
    # Block path-traversal: regex permits the character class but `.` / `..` would
    # resolve out of the scratch dir at rmtree time (see _is_safe_cert_name).
    if not _is_safe_cert_name(cert_name):
        return jsonify({"status": "ko", "message": "Invalid cert_name"}), 400

    cmd_env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    cmd_env["PYTHONPATH"] = cmd_env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in cmd_env["PYTHONPATH"] else "")

    try:
        max_log_backups = max(0, int(getenv("LETS_ENCRYPT_MAX_LOG_BACKUPS", "50").strip()))
    except ValueError:
        max_log_backups = 50

    with _le_cache_write_lock(), _ui_scratch_dir() as tmp:
        scratch = Path(tmp)
        download_certificates(scratch)

        # Alias-aware broken-lineage delete (mirrors /letsencrypt/heal). A #3733-shaped lineage
        # keys its UI row off the live-dir basename (the body name, e.g. domain.se.conf), not the
        # conf stem, so `certbot delete --cert-name` + the stem-derived renewal_file below would
        # both miss and 500. Route it through the shared purge_lineage, which resolves the conf
        # stem AND body names, then persist and skip the certbot subprocess for this case.
        target_broken = next(
            (b for b in _detect_broken_lineages(scratch) if cert_name == b["cert_name"] or cert_name in b["lineage_names"]),
            None,
        )
        if target_broken is not None:
            LOGGER.info(f"Deleting broken certificate lineage {cert_name} ({target_broken['reason']})")
            removed = _purge_lineage(scratch, Path(target_broken["renewal_conf"]), quarantine_root=None, logger=LOGGER)
            try:
                err = _persist_le_cache_dir(scratch, bypass_gate=True)
                if err:
                    return jsonify({"status": "ko", "message": f"Successfully deleted certificate {cert_name}, but cache update failed: {err}"}), 500
            except Exception as e:
                return jsonify({"status": "ko", "message": f"Successfully deleted certificate {cert_name}, but cache update failed: {e}"}), 500
            return jsonify({"status": "ok", "message": f"Successfully deleted certificate {cert_name}", "removed": removed})

        work_dir = scratch.joinpath("_work")
        work_dir.mkdir(parents=True, exist_ok=True)

        # Defense-in-depth: every path the certbot subprocess + cleanup touches must
        # resolve UNDER `scratch`. Blocks any cert_name that slips past the regex.
        cert_dir = scratch.joinpath("live", cert_name)
        archive_dir = scratch.joinpath("archive", cert_name)
        renewal_file = scratch.joinpath("renewal", f"{cert_name}.conf")
        for path in (cert_dir, archive_dir, renewal_file):
            if not _path_is_inside(path, scratch):
                LOGGER.error(f"Refusing delete: cert_name {cert_name!r} escapes scratch {scratch}")
                return jsonify({"status": "ko", "message": "Invalid cert_name"}), 400

        delete_proc = run(
            [
                CERTBOT_BIN,
                "delete",
                "--config-dir",
                scratch.as_posix(),
                "--work-dir",
                work_dir.as_posix(),
                "--logs-dir",
                LOGS_DIR,
                "--max-log-backups",
                str(max_log_backups),
                "--cert-name",
                cert_name,
                "-n",
            ],
            stdin=DEVNULL,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            env=cmd_env,
            check=False,
        )

        if delete_proc.returncode != 0:
            LOGGER.error(f"Failed to delete certificate {cert_name}: {delete_proc.stdout}")
            return jsonify({"status": "ko", "message": f"Failed to delete certificate {cert_name}"}), 500

        LOGGER.info(f"Successfully deleted certificate {cert_name}")
        for path in (cert_dir, archive_dir):
            if path.exists():
                try:
                    rmtree(path, ignore_errors=False)
                    LOGGER.info(f"Removed directory {path}")
                except Exception as e:
                    LOGGER.error(f"Failed to remove directory {path}: {e}")

        if renewal_file.exists():
            try:
                renewal_file.unlink()
                LOGGER.info(f"Removed renewal file {renewal_file}")
            except Exception as e:
                LOGGER.error(f"Failed to remove renewal file {renewal_file}: {e}")

        try:
            # Bypass the consistency gate (like Heal): removing one cert cannot add an orphan
            # ref, so the result is no worse than before. Without this, an UNRELATED orphan in
            # the cache would block a legit delete (500) and the cert would reappear next sync.
            err = _persist_le_cache_dir(scratch, bypass_gate=True)
            if err:
                return jsonify({"status": "ko", "message": f"Successfully deleted certificate {cert_name}, but cache update failed: {err}"}), 500
        except Exception as e:
            return jsonify({"status": "ko", "message": f"Successfully deleted certificate {cert_name}, but cache update failed: {e}"}), 500

        return jsonify({"status": "ok", "message": f"Successfully deleted certificate {cert_name}"})


@letsencrypt.route("/letsencrypt/orphans", methods=["GET"])
@login_required
@cors_required
def letsencrypt_orphans():
    """Tier 1 observability: list renewal confs whose ACME account is missing on disk.

    These orphans block cache writeback (the integrity gate refuses to persist
    them) and will produce AccountNotFound errors on the next certbot renew.
    """
    with _ui_scratch_dir() as tmp:
        scratch = Path(tmp)
        download_certificates(scratch)
        orphans = _detect_orphan_renewals(scratch)
        broken = _detect_broken_lineages(scratch)
    return jsonify({"status": "ok", "count": len(orphans), "orphans": orphans, "broken": broken})


@letsencrypt.route("/letsencrypt/heal", methods=["POST"])
@login_required
@cors_required
def letsencrypt_heal():
    """Tier 2 interactive remediation: remove an orphan or broken renewal conf + its cert files.

    Body: { "cert_name": "<service>" }

    Refuses to act unless the cert is actually orphaned (missing ACME account) or broken
    (lineage name mismatch / no cert material). On success, the next scheduler certbot-new
    tick will re-issue.

    Cross-writer window: the scheduler's sanitize step mutates the live tree outside
    le_cache_write_lock while this heal works from its own scratch snapshot, so the last DB
    writer wins — broken lineages self-correct on the next tick, but a healed account-orphan
    can be resurrected by a concurrent scheduler write (per-host lock caveat, see
    letsencrypt_consistency.py LE_CACHE_LOCK_PATH).
    """
    if _user_readonly():
        return jsonify({"status": "ko", "message": "User is read-only"}), 403
    cert_name = request.json.get("cert_name") if request.is_json else None
    if not cert_name:
        return jsonify({"status": "ko", "message": "Missing cert_name"}), 400
    if not _is_safe_cert_name(cert_name):
        return jsonify({"status": "ko", "message": "Invalid cert_name"}), 400

    with _le_cache_write_lock(), _ui_scratch_dir() as tmp:
        scratch = Path(tmp)
        download_certificates(scratch)
        orphans = {o["cert_name"]: o for o in _detect_orphan_renewals(scratch)}
        # Match a broken entry by conf stem OR by a body-derived lineage name: the UI row is keyed
        # off the live-dir basename, which for a #3733 lineage is the body name (domain.se.conf),
        # not the conf stem (domain.se) that detect_broken_lineages reports as cert_name.
        target_broken = next(
            (b for b in _detect_broken_lineages(scratch) if cert_name == b["cert_name"] or cert_name in b["lineage_names"]),
            None,
        )
        if cert_name in orphans:
            target_info = orphans[cert_name]
            LOGGER.info(f"Healing orphan certificate {cert_name} (missing account {target_info['account']} on {target_info['server']})")
            renewal_file = scratch.joinpath("renewal", f"{cert_name}.conf")
        elif target_broken is not None:
            target_info = target_broken
            LOGGER.info(f"Healing broken certificate lineage {cert_name} ({target_info['reason']})")
            # Heal the broken entry via its own renewal_conf path (already under scratch) so a
            # submitted body-name alias resolves to the real conf stem's lineage.
            renewal_file = Path(target_info["renewal_conf"])
        else:
            return jsonify({"status": "ko", "message": f"Certificate {cert_name} is neither orphaned nor broken — refusing to heal"}), 400

        # Defense-in-depth: refuse anything that would resolve outside the scratch.
        if not _path_is_inside(renewal_file, scratch):
            LOGGER.error(f"Refusing heal: cert_name {cert_name!r} escapes scratch {scratch}")
            return jsonify({"status": "ko", "message": "Invalid cert_name"}), 400

        # purge_lineage removes the renewal conf + live/<name> + archive/<name> for the conf stem
        # AND any body-referenced lineage names — broken confs point live/archive at a name that
        # differs from the stem, which the old hard-coded triple would have missed. Each path is
        # containment-checked against scratch inside purge_lineage.
        removed = _purge_lineage(scratch, renewal_file, quarantine_root=None, logger=LOGGER)

        try:
            # Bypass the consistency gate here — operator explicitly asked to remove this cert; the
            # resulting tar is strictly better than the prior state. Scheduler-side gate still
            # protects against runtime poisoning.
            err = _persist_le_cache_dir(scratch, bypass_gate=True)
            if err:
                # Persistence failed → return 500 so automation knows to retry.
                # On-disk removals were in the scratch dir, which is torn down anyway.
                return jsonify({"status": "ko", "message": f"Healed {cert_name} on disk, but cache update failed: {err}", "removed": removed}), 500
        except Exception as e:
            return jsonify({"status": "ko", "message": f"Healed {cert_name} on disk, but cache update failed: {e}", "removed": removed}), 500

    return jsonify(
        {
            "status": "ok",
            "message": f"Healed {cert_name}; next certbot-new tick will reissue.",
            "removed": removed,
            "target": target_info,
        }
    )


@letsencrypt.route("/letsencrypt/accounts", methods=["GET"])
@login_required
@cors_required
def letsencrypt_accounts():
    """List every ACME account currently registered on disk.

    Each entry includes the path under accounts/, the account UUID, and the
    email pulled from meta.json when available.
    """
    out: List[Dict[str, str]] = []
    with _ui_scratch_dir() as tmp:
        scratch = Path(tmp)
        download_certificates(scratch)
        accounts_root = scratch.joinpath("accounts")
        if accounts_root.is_dir():
            with suppress(OSError):
                for regr in accounts_root.rglob("regr.json"):
                    account_dir = regr.parent
                    if not account_dir.is_dir():
                        continue
                    email = ""
                    meta_path = account_dir.joinpath("meta.json")
                    if meta_path.is_file():
                        try:
                            meta = loads(meta_path.read_text(encoding="utf-8"))
                            if isinstance(meta, dict):
                                email = str(meta.get("email") or "")
                        except (OSError, ValueError, KeyError):
                            email = ""
                    try:
                        rel = account_dir.relative_to(accounts_root).as_posix()
                    except ValueError:
                        rel = account_dir.as_posix()
                    segments = rel.split("/")
                    server_host = segments[0] if segments else ""
                    server_url = f"https://{rel.rsplit('/', 1)[0]}" if "/" in rel else f"https://{server_host}"
                    out.append({"account_id": account_dir.name, "path": rel, "server_url": server_url, "email": email})
    return jsonify({"status": "ok", "count": len(out), "accounts": out})


@letsencrypt.route("/letsencrypt/cache-status", methods=["GET"])
@login_required
@cors_required
def letsencrypt_cache_status():
    """Report the cache integrity gate's verdict against the current cache row."""
    with _ui_scratch_dir() as tmp:
        scratch = Path(tmp)
        download_certificates(scratch)
        ok, reason = _le_cache_consistent(scratch)
        orphans = _detect_orphan_renewals(scratch)
    return jsonify(
        {
            "status": "ok",
            "consistent": ok,
            "reason": reason,
            "orphan_count": len(orphans),
            "orphans": orphans,
        }
    )


@letsencrypt.route("/letsencrypt/<path:filename>")
@login_required
def letsencrypt_static(filename):
    """
    Generalized handler for static files in the letsencrypt blueprint.
    """
    return letsencrypt.send_static_file(filename)
