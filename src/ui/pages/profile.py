from base64 import b64encode
from json import dumps
from threading import Thread
from time import time
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, session
from flask_login import current_user, login_required, logout_user

from builder.profile import profile_builder  # type: ignore

from utils import USER_PASSWORD_RX, gen_password_hash

from pages.utils import handle_error, manage_bunkerweb, verify_data_in_form, wait_applying


profile = Blueprint("profile", __name__)


@profile.route("/profile", methods=["GET", "POST"])
@login_required
def profile_page():
    totp_recovery_codes = None
    if request.method == "POST":
        if current_app.db.readonly:
            return handle_error("Database is in read-only mode", "profile")

        verify_data_in_form(
            data={"operation": ("username", "password", "totp", "activate-key")}, err_message="Invalid operation parameter.", redirect_url="profile"
        )

        if request.form["operation"] not in ("username", "password", "totp", "activate-key"):
            return handle_error("Invalid operation parameter.", "profile")

        if request.form["operation"] == "activate-key":
            verify_data_in_form(data={"license": None}, err_message="Missing license for operation activate key on /account.", redirect_url="profile")

            if len(request.form["license"]) == 0:
                return handle_error("The license key is empty", "profile")

            variables = {"PRO_LICENSE_KEY": request.form["license"]}

            variables = current_app.bw_config.check_variables(variables, {"PRO_LICENSE_KEY": request.form["license"]})

            if not variables:
                return handle_error("The license key variable checks returned error", "profile", True)

            # Force job to contact PRO API
            # by setting the last check to None
            metadata = current_app.db.get_metadata()
            metadata["last_pro_check"] = None
            current_app.db.set_pro_metadata(metadata)

            curr_changes = current_app.db.check_changes()

            # Reload instances
            def update_global_config(threaded: bool = False):
                wait_applying()

                if not manage_bunkerweb("global_config", variables, threaded=threaded):
                    message = "Checking license key to upgrade."
                    if threaded:
                        current_app.data["TO_FLASH"].append({"content": message, "type": "success"})
                    else:
                        flash(message)

            current_app.data["PRO_LOADING"] = True
            current_app.data["CONFIG_CHANGED"] = True

            if any(curr_changes.values()):
                current_app.data["RELOADING"] = True
                current_app.data["LAST_RELOAD"] = time()
                Thread(target=update_global_config, args=(True,)).start()
            else:
                update_global_config()

            return redirect(url_for("profile.profile_page"))

        verify_data_in_form(data={"curr_password": None}, err_message="Missing current password parameter on /account.", redirect_url="profile")

        if not current_user.check_password(request.form["curr_password"]):
            return handle_error(f"The current password is incorrect. ({request.form['operation']})", "profile")

        username = current_user.get_id()
        password = request.form["curr_password"]
        totp_secret = current_user.totp_secret
        totp_recovery_codes = current_user.list_recovery_codes

        if request.form["operation"] == "username":
            verify_data_in_form(data={"admin_username": None}, err_message="Missing admin username parameter on /account.", redirect_url="profile")

            if len(request.form["admin_username"]) > 256:
                return handle_error("The admin username is too long. It must be less than 256 characters. (username)", "profile")

            username = request.form["admin_username"]

            session.clear()
            logout_user()

        if request.form["operation"] == "password":
            verify_data_in_form(
                data={"admin_password": None, "admin_password_check": None},
                err_message="Missing admin password or confirm password parameter on /account.",
                redirect_url="profile",
            )

            if request.form["admin_password"] != request.form["admin_password_check"]:
                return handle_error("The passwords do not match. (password)", "profile")

            if not USER_PASSWORD_RX.match(request.form["admin_password"]):
                return handle_error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-). (password)",
                    "profile",
                )

            password = request.form["admin_password"]

            session.clear()
            logout_user()

        if request.form["operation"] == "totp":
            verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /account.", redirect_url="profile")

            if not current_app.totp.verify_totp(
                request.form["totp_token"], totp_secret=session.get("tmp_totp_secret", ""), user=current_user
            ) and not current_app.totp.verify_recovery_code(request.form["totp_token"], user=current_user):
                return handle_error("The totp token is invalid. (totp)", "profile")

            session["totp_validated"] = not bool(current_user.totp_secret)
            totp_secret = None if bool(current_user.totp_secret) else session.pop("tmp_totp_secret", "")

            if totp_secret and totp_secret != current_user.totp_secret:
                totp_recovery_codes = current_app.totp.generate_recovery_codes()
                flash(
                    "The recovery codes have been refreshed.\nPlease save them in a safe place. They will not be displayed again."
                    + "\n".join(totp_recovery_codes),
                    "info",
                )  # TODO: Remove this when we have a way to display the recovery codes

            current_app.logger.debug(f"totp recovery codes: {totp_recovery_codes or current_user.list_recovery_codes}")

        ret = current_app.db.update_ui_user(
            username,
            gen_password_hash(password),
            totp_secret,
            totp_recovery_codes=totp_recovery_codes or current_user.list_recovery_codes,
            method=current_user.method if request.form["operation"] == "totp" else "ui",
        )
        if ret:
            return handle_error(f"Couldn't update the admin user in the database: {ret}", "profile", False, "error")

        flash(
            (
                f"The {request.form['operation']} has been successfully updated."
                if request.form["operation"] != "totp"
                else f"The two-factor authentication was successfully {'disabled' if bool(current_user.totp_secret) else 'enabled'}."
            ),
        )

        return redirect(url_for("profile.profile_page" if request.form["operation"] == "totp" else "login"))

    totp_qr_image = ""
    if not bool(current_user.totp_secret):
        session["tmp_totp_secret"] = current_app.totp.generate_totp_secret()
        totp_qr_image = current_app.totp.generate_qrcode(current_user.get_id(), session["tmp_totp_secret"])

    builder = profile_builder(
        current_user if current_user.is_authenticated else None,
        {
            "is_totp": bool(current_user.totp_secret),
            "totp_image": totp_qr_image,
            "totp_recovery_codes": totp_recovery_codes or current_user.list_recovery_codes,
            "is_recovery_refreshed": bool(totp_recovery_codes),
            "totp_secret": current_app.totp.get_totp_pretty_key(session.get("tmp_totp_secret", "")),
        },
    )

    # TODO: Show user backup codes after TOTP refresh + add refresh feature
    return render_template("profile.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
