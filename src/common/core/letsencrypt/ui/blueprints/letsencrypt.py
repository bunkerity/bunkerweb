from collections import defaultdict
from datetime import datetime
from html import escape
from os import getenv
from subprocess import DEVNULL, PIPE, STDOUT, run
from os.path import dirname, join, sep
from pathlib import Path
from shutil import rmtree
from io import BytesIO
from tarfile import open as tar_open
from traceback import format_exc

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

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
DATA_PATH = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt", "etc")
WORK_DIR = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt", "lib")
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


def download_certificates():
    rmtree(DATA_PATH, ignore_errors=True)
    Path(DATA_PATH).mkdir(parents=True, exist_ok=True)

    cache_files = DB.get_jobs_cache_files(job_name="certbot-renew")

    for cache_file in cache_files:
        if cache_file["file_name"].endswith(".tgz") and cache_file["file_name"].startswith("folder:"):
            with tar_open(fileobj=BytesIO(cache_file["data"]), mode="r:gz") as tar:
                try:
                    tar.extractall(DATA_PATH, filter="fully_trusted")
                except TypeError:
                    tar.extractall(DATA_PATH)


def retrieve_certificates():
    download_certificates()

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

    for cert_file in Path(DATA_PATH).joinpath("live").glob("*/fullchain.pem"):
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
            cert = x509.load_pem_x509_certificate(cert_file.read_bytes(), default_backend())
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
            renewal_file = Path(DATA_PATH).joinpath("renewal", f"{domain}.conf")
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
        certs = retrieve_certificates()
        LOGGER.debug(f"Certificates: {certs}")
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
    cert_name = request.json.get("cert_name")
    if not cert_name:
        return jsonify({"status": "ko", "message": "Missing cert_name"}), 400

    download_certificates()

    cmd_env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    cmd_env["PYTHONPATH"] = cmd_env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in cmd_env["PYTHONPATH"] else "")

    delete_proc = run(
        [
            CERTBOT_BIN,
            "delete",
            "--config-dir",
            DATA_PATH,
            "--work-dir",
            WORK_DIR,
            "--logs-dir",
            LOGS_DIR,
            "--cert-name",
            cert_name,
            "-n",  # non-interactive
        ],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=cmd_env,
        check=False,
    )

    if delete_proc.returncode == 0:
        LOGGER.info(f"Successfully deleted certificate {cert_name}")
        cert_dir = Path(DATA_PATH).joinpath("live", cert_name)
        archive_dir = Path(DATA_PATH).joinpath("archive", cert_name)
        renewal_file = Path(DATA_PATH).joinpath("renewal", f"{cert_name}.conf")

        for path in (cert_dir, archive_dir):
            if path.exists():
                try:
                    for file in path.glob("*"):
                        try:
                            file.unlink()
                        except Exception as e:
                            LOGGER.error(f"Failed to remove file {file}: {e}")
                    path.rmdir()
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
            dir_path = Path(LE_CACHE_DIR)
            file_name = f"folder:{dir_path.as_posix()}.tgz"
            content = BytesIO()
            with tar_open(file_name, mode="w:gz", fileobj=content, compresslevel=9) as tgz:
                tgz.add(DATA_PATH, arcname=".")
            content.seek(0, 0)

            err = DB.upsert_job_cache("", file_name, content.getvalue(), job_name="certbot-renew")
            if err:
                return jsonify({"status": "ko", "message": f"Failed to cache letsencrypt dir: {err}"})
            else:
                err = DB.checked_changes(["plugins"], ["letsencrypt"], True)
                if err:
                    return jsonify({"status": "ko", "message": f"Failed to cache letsencrypt dir: {err}"})
        except Exception as e:
            return jsonify({"status": "ok", "message": f"Successfully deleted certificate {cert_name}, but failed to cache letsencrypt dir: {e}"})
        return jsonify({"status": "ok", "message": f"Successfully deleted certificate {cert_name}"})
    else:
        LOGGER.error(f"Failed to delete certificate {cert_name}: {delete_proc.stdout}")
        return jsonify({"status": "ko", "message": f"Failed to delete certificate {cert_name}: {delete_proc.stdout}"})


@letsencrypt.route("/letsencrypt/<path:filename>")
@login_required
def letsencrypt_static(filename):
    """
    Generalized handler for static files in the letsencrypt blueprint.
    """
    return letsencrypt.send_static_file(filename)
