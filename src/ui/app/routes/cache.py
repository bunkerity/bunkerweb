from io import BytesIO
from json import JSONDecodeError, loads
from typing import Optional

from flask import Blueprint, Response, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.utils import secure_filename

from common_utils import is_sensitive_job_cache_file  # type: ignore
from model import Jobs, Jobs_cache  # type: ignore
from app.dependencies import BW_CONFIG, DB
from app.utils import LOGGER, flash, get_printable_content

cache = Blueprint("cache", __name__)

RESTRICTED = object()

SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


def _delete_cache_rows(file_name: str, *, job_name: str, service_id: Optional[str], plugin_id: str, admin: bool):
    """Delete the cache rows a request names. None: no row. RESTRICTED: a stored row is sensitive and the caller is not a super
    administrator. "": deleted. Other strings: errors.

    The lookup follows the database collation (MariaDB/MySQL: case-insensitive, trailing spaces ignored), so it can match rows the
    request did not spell. The rows are resolved, authorized and deleted by id and stored identity in one transaction: exactly the rows that were checked.
    """
    if DB.readonly:
        return "The database is read-only, the changes will not be saved"

    with DB._db_session() as session:
        if not session.query(Jobs).filter_by(name=job_name, plugin_id=plugin_id).first():
            return None

        rows = (
            session.query(Jobs_cache.id, Jobs_cache.file_name, Jobs_cache.job_name, Jobs_cache.service_id)
            .filter_by(file_name=file_name, service_id=service_id or None, job_name=job_name)
            .all()
        )
        if not rows:
            return None

        stored_plugins = {}
        for row in rows:
            stored_plugins[row.id] = session.query(Jobs.plugin_id).filter_by(name=row.job_name).scalar() or ""
            if not admin and is_sensitive_job_cache_file(row.file_name, stored_plugins[row.id], row.job_name):
                return RESTRICTED

        try:
            # The read above holds no lock: another writer can replace a row and reuse its id before this DELETE. Every column the
            # check read stays in the WHERE, so a replaced row matches nothing and is never deleted.
            for row in rows:
                deleted = (
                    session.query(Jobs_cache)
                    .filter(
                        Jobs_cache.id == row.id,
                        Jobs_cache.file_name == row.file_name,
                        Jobs_cache.job_name == row.job_name,
                        Jobs_cache.service_id.is_(None) if row.service_id is None else Jobs_cache.service_id == row.service_id,
                        Jobs_cache.job_name.in_(select(Jobs.name).where(Jobs.plugin_id == stored_plugins[row.id])),
                    )
                    .delete(synchronize_session=False)
                )
                if deleted != 1:
                    session.rollback()
                    return None
            DB._blob_sweep(session)
            session.commit()
        except BaseException as e:
            return str(e)

    return ""


@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():
    service = request.args.get("service", "")
    cache_plugin = request.args.get("plugin", "")
    cache_job_name = request.args.get("job_name", "")
    return render_template(
        "cache.html",
        caches=DB.get_jobs_cache_files(with_data=False),
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"],
        cache_service=service,
        cache_plugin=cache_plugin,
        cache_job_name=cache_job_name,
    )


@cache.route("/cache/<string:service>/<string:plugin_id>/<string:job_name>/<string:file_name>", methods=["GET"])
@login_required
def cache_view(service: str, plugin_id: str, job_name: str, file_name: str):
    if file_name.startswith("folder:"):
        file_name = file_name.replace("_", "/")
    else:
        file_name = secure_filename(file_name)

    # Super administrators only (`admin`, not an assigned admin role); checked on the normalised name, before the DB read.
    if is_sensitive_job_cache_file(file_name, plugin_id, job_name) and not current_user.admin:
        return Response("Forbidden", status=403)

    cached = DB.get_job_cache_file(
        job_name,
        file_name,
        service_id=service if service != "global" else None,
        plugin_id=plugin_id,
        with_info=True,
    )
    # The lookup follows the database collation, so the row found may carry other spellings than the request (case, trailing
    # spaces): decide again on the stored names, before any byte leaves.
    if cached and not current_user.admin and is_sensitive_job_cache_file(cached["file_name"], cached["plugin_id"], cached["job_name"]):
        return Response("Forbidden", status=403)
    cache_file = cached["data"] if cached else None

    download = request.args.get("download", False)
    if download:
        if not cache_file:
            return Response("Cache file not found", status=404)
        return send_file(BytesIO(cache_file), as_attachment=True, download_name=file_name)

    if not cache_file:
        flash(
            f"Cache file {file_name} from job {job_name}, plugin {plugin_id}{', service ' + service if service != 'global' else ''} not found",
            "error",
            save=False,
        )
        return redirect(url_for("cache.cache_page"))

    return render_template("cache_view.html", cache_file=get_printable_content(cache_file))


@cache.route("/cache/delete", methods=["POST"])
@login_required
def cache_delete_bulk():
    if DB.readonly:
        return Response("Database is in read-only mode", status=403)

    try:
        cache_files = loads(request.form.get("cache_files", "[]"))
    except JSONDecodeError:
        return Response("Invalid cache files parameter", status=400)

    if not cache_files:
        return Response("No cache files selected", status=400)

    errors = []
    changed_plugins = set()
    deleted_count = 0

    for cache_file in cache_files:
        file_name = cache_file.get("fileName", "")
        job_name = cache_file.get("jobName", "")
        service = cache_file.get("service", "")
        plugin = cache_file.get("plugin", "")

        if file_name.startswith("folder:"):
            file_name = file_name.replace("_", "/")
        else:
            file_name = secure_filename(file_name)

        # Same rule as cache_view: super administrators only. The names the request sent are checked first, then the stored rows.
        if not current_user.admin and is_sensitive_job_cache_file(file_name, plugin, job_name):
            errors.append(f"Cache file {file_name} is restricted to administrators")
            continue

        result = _delete_cache_rows(
            file_name,
            job_name=job_name,
            service_id=service if service != "global" else None,
            plugin_id=plugin,
            admin=current_user.admin,
        )

        if result is RESTRICTED:
            errors.append(f"Cache file {file_name} is restricted to administrators")
            continue

        if result is None:
            errors.append(f"Cache file {file_name} not found")
        elif result:
            errors.append(f"Error deleting {file_name}: {result}")
        else:
            changed_plugins.add(plugin)
            deleted_count += 1

    if changed_plugins:
        ret = DB.checked_changes(changes=["config"], plugins_changes=list(changed_plugins), value=True)
        if ret:
            LOGGER.warning("Cache deletion changes were not committed to the database")
            errors.append("Changes were not committed to the database")

    if errors:
        flash(f"Deleted {deleted_count} files with {len(errors)} errors: {'; '.join(errors)}", "warning", save=False)
    else:
        flash(f"Successfully deleted {deleted_count} cache file{'s' if deleted_count != 1 else ''}", "success", save=False)

    return redirect(url_for("cache.cache_page"))
