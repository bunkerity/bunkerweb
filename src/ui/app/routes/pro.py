from datetime import datetime, timezone
from time import time
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT, BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA
from app.api_client import ApiClientError, ApiUnavailableError
from app.routes.utils import get_remain, handle_error, verify_data_in_form, wait_applying
from app.utils import flash

pro = Blueprint("pro", __name__)


@pro.route("/pro", methods=["GET"])
@login_required
def pro_page():
    online_services = 0
    draft_services = 0
    for service in API_CLIENT.get_services(with_drafts=True):
        if service["is_draft"]:
            draft_services += 1
            continue
        online_services += 1

    metadata = API_CLIENT.get_metadata()
    # Convert current date to UTC and normalize to midnight for daily comparison
    current_day_utc = datetime.now().astimezone().astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    pro_expires_in = "Unknown"
    if metadata["pro_expire"]:
        # Ensure pro_expire is timezone-aware UTC
        pro_expire = metadata["pro_expire"]
        if isinstance(pro_expire, str):
            pro_expire = datetime.fromisoformat(pro_expire)
        if pro_expire.tzinfo is None:
            pro_expire = pro_expire.replace(tzinfo=timezone.utc)
        else:
            pro_expire = pro_expire.astimezone(timezone.utc)

        exp = (pro_expire - current_day_utc).total_seconds()
        remain = ("Unknown", "Unknown") if exp <= 0 else get_remain(exp)
        pro_expires_in = remain[0]

    return render_template(
        "pro.html",
        online_services=online_services,
        draft_services=draft_services,
        pro_expires_in=pro_expires_in,
        pro_license_key=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("PRO_LICENSE_KEY",)).get(
            "PRO_LICENSE_KEY", ""
        ),
    )


@pro.route("/pro/key", methods=["POST"])
@login_required
def pro_key():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "pro")

    verify_data_in_form(
        data={"PRO_LICENSE_KEY": None},
        err_message="Missing license key parameter on /pro/key.",
        redirect_url="pro",
        next=True,
    )
    license_key = request.form["PRO_LICENSE_KEY"]
    if not license_key:
        return handle_error("Invalid license key", "pro")

    global_config = BW_CONFIG.get_config(global_only=True, methods=False)
    global_config_methods = BW_CONFIG.get_config(global_only=True, methods=True)
    variables = BW_CONFIG.check_variables(
        global_config | {"PRO_LICENSE_KEY": license_key},
        global_config_methods,
        {"PRO_LICENSE_KEY": license_key},
        global_config=True,
    )

    if not variables:
        flash("The license key is the same as the current one.", "warning")
        return redirect(url_for("pro.pro_page"))

    DATA.load_from_file()

    def update_license_key(variables: dict):
        wait_applying()

        operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True)

        if not error:
            operation = "The PRO license key was updated successfully."

        if operation:
            if operation.startswith(("Can't", "The database is read-only")):
                DATA["TO_FLASH"].append({"content": operation, "type": "error"})
            else:
                DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                DATA["TO_FLASH"].append(
                    {"content": "The Scheduler will be in charge of applying the changes and downloading the PRO plugins.", "type": "success", "save": False}
                )

        DATA["RELOADING"] = False

    DATA.update(
        {
            "RELOADING": True,
            "LAST_RELOAD": time(),
            "CONFIG_CHANGED": True,
            "PRO_LOADING": True,
        }
    )
    flash("Checking license key.")
    CONFIG_TASKS_EXECUTOR.submit(update_license_key, variables)
    return redirect(
        url_for(
            "loading",
            next=url_for("pro.pro_page"),
            message="Updating license key",
        )
    )


@pro.route("/pro/force-check", methods=["POST"])
@login_required
def force_check():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "pro")

    try:
        API_CLIENT.update_metadata({"last_pro_check": None})
        API_CLIENT.checked_changes(["config"], plugins_changes=["pro"], value=True)
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(e.message, "pro")

    flash("A new check for PRO plugins has been scheduled.", "success")
    DATA["PRO_LOADING"] = True
    return redirect(url_for("pro.pro_page"))


@pro.route("/pro/force-update", methods=["POST"])
@login_required
def force_update():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "pro")

    try:
        API_CLIENT.update_metadata({"force_pro_update": True})
        API_CLIENT.update_metadata({"last_pro_check": None})
        API_CLIENT.checked_changes(["config"], plugins_changes=["pro"], value=True)
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(e.message, "pro")

    flash("A forced update of PRO plugins has been scheduled.", "success")
    DATA["PRO_LOADING"] = True
    return redirect(url_for("pro.pro_page"))


@pro.route("/pro/refresh-ui", methods=["POST"])
@login_required
def refresh_ui():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "pro")

    # safe_reload_plugins() latches on IS_RELOADING_PLUGINS and only ever clears it on
    # worker import, so a UI that already reloaded once since boot would consume the flag
    # without re-extracting anything. Clear the latch so this stays an explicit escape hatch.
    DATA.load_from_file()
    DATA["IS_RELOADING_PLUGINS"] = False

    try:
        API_CLIENT.checked_changes(["ui_plugins"], value=True)
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(e.message, "pro")

    flash("The web UI will reload its PRO plugins shortly.", "success")
    return redirect(url_for("pro.pro_page"))
