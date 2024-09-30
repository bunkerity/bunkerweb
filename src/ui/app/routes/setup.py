from os import getenv
from secrets import choice
from string import ascii_letters, digits
from threading import Thread
from time import time

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.models.totp import totp as TOTP

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import USER_PASSWORD_RX, gen_password_hash

from app.routes.utils import REVERSE_PROXY_PATH, handle_error, manage_bunkerweb

setup = Blueprint("setup", __name__)


@setup.route("/setup", methods=["GET", "POST"])
def setup_page():
    if current_user.is_authenticated:
        return redirect(url_for("home.home_page"))
    db_config = BW_CONFIG.get_config(
        methods=False,
        filtered_settings=("SERVER_NAME", "MULTISITE", "USE_UI", "UI_HOST", "AUTO_LETS_ENCRYPT", "USE_LETS_ENCRYPT_STAGING", "EMAIL_LETS_ENCRYPT"),
    )

    admin_user = DB.get_ui_user()

    ui_reverse_proxy = False
    for server_name in db_config["SERVER_NAME"].split(" "):
        if server_name and db_config.get(f"{server_name}_USE_UI", db_config.get("USE_UI", "no")) == "yes":
            if admin_user:
                return redirect(url_for("login.login_page"), 301)
            ui_reverse_proxy = True
            break

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "setup")

        required_keys = []
        if not ui_reverse_proxy:
            required_keys.extend(["server_name", "ui_host", "ui_url", "auto_lets_encrypt", "lets_encrypt_staging", "email_lets_encrypt"])
        if not admin_user:
            required_keys.extend(["admin_username", "admin_email", "admin_password", "admin_password_check", "2fa_code"])

        if not any(key in request.form for key in required_keys):
            return handle_error(f"Missing either one of the following parameters: {', '.join(required_keys)}.", "setup")

        if not admin_user:
            if len(request.form["admin_username"]) > 256:
                return handle_error("The admin username is too long. It must be less than 256 characters.", "setup")
            elif len(request.form["admin_email"]) > 256:
                return handle_error("The admin email is too long. It must be less than 256 characters.", "setup")
            elif request.form["admin_password"] != request.form["admin_password_check"]:
                return handle_error("The passwords do not match.", "setup")
            elif not USER_PASSWORD_RX.match(request.form["admin_password"]):
                return handle_error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).",
                    "setup",
                )

            totp_secret = None
            totp_recovery_codes = None

            if request.form["2fa_code"]:
                totp_secret = session.pop("tmp_totp_secret", "")
                if not TOTP.verify_totp(request.form["2fa_code"], totp_secret=totp_secret, user=current_user):
                    return handle_error("The totp token is invalid.", "setup")

                totp_recovery_codes = TOTP.generate_recovery_codes()

            ret = DB.create_ui_user(
                request.form["admin_username"],
                gen_password_hash(request.form["admin_password"]),
                ["admin"],
                request.form["admin_email"] or None,
                totp_secret=totp_secret,
                totp_recovery_codes=totp_recovery_codes,
                method="ui",
                admin=True,
            )
            if ret:
                return handle_error(f"Couldn't create the admin user in the database: {ret}", "setup", False, "error")

            flash("The admin user was created successfully", "success")

        if not ui_reverse_proxy:
            server_names = db_config["SERVER_NAME"].split(" ")
            if request.form["server_name"] in server_names:
                return handle_error(f"The hostname {request.form['server_name']} is already in use.", "setup")
            else:
                for server_name in server_names:
                    if request.form["server_name"] in db_config.get(f"{server_name}_SERVER_NAME", "").split(" "):
                        return handle_error(f"The hostname {request.form['server_name']} is already in use.", "setup")

            if not REVERSE_PROXY_PATH.match(request.form["ui_host"]):
                return handle_error("The hostname is not valid.", "setup")

            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()

            config = {
                "SERVER_NAME": request.form["server_name"],
                "USE_TEMPLATE": "ui",
                "USE_REVERSE_PROXY": "yes",
                "REVERSE_PROXY_HOST": request.form["ui_host"],
                "REVERSE_PROXY_URL": request.form["ui_url"] or "/",
                "USE_LETS_ENCRYPT_STAGING": request.form["lets_encrypt_staging"],
                "EMAIL_LETS_ENCRYPT": request.form["email_lets_encrypt"],
            }

            if request.form.get("auto_lets_encrypt", "no") == "yes":
                config["AUTO_LETS_ENCRYPT"] = "yes"
            else:
                config.update(
                    {
                        "USE_CUSTOM_SSL": "yes",
                        "CUSTOM_SSL_CERT": "/var/cache/bunkerweb/misc/default-server-cert.pem",
                        "CUSTOM_SSL_KEY": "/var/cache/bunkerweb/misc/default-server-cert.key",
                    }
                )

            if not config.get("MULTISITE", "no") == "yes":
                BW_CONFIG.edit_global_conf({"MULTISITE": "yes"}, check_changes=False)

            # deepcode ignore MissingAPI: We don't need to check to wait for the thread to finish
            Thread(
                target=manage_bunkerweb,
                name="Reloading instances",
                args=("services", config, request.form["server_name"], request.form["server_name"]),
                kwargs={"operation": "new", "threaded": True},
            ).start()

        return Response(status=200)

    session["tmp_totp_secret"] = TOTP.generate_totp_secret()
    totp_qr_image = TOTP.generate_qrcode(current_user.get_id(), session["tmp_totp_secret"])

    return render_template(
        "setup.html",
        ui_user=admin_user,
        ui_reverse_proxy=ui_reverse_proxy,
        username=getenv("ADMIN_USERNAME", ""),
        password=getenv("ADMIN_PASSWORD", ""),
        ui_host=db_config.get("UI_HOST", getenv("UI_HOST", "")),
        auto_lets_encrypt=db_config.get("AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")),
        lets_encrypt_staging=db_config.get("USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")),
        email_lets_encrypt=db_config.get("EMAIL_LETS_ENCRYPT", getenv("EMAIL_LETS_ENCRYPT", "")),
        random_url=f"/{''.join(choice(ascii_letters + digits) for _ in range(10))}",
        totp_qr_image=totp_qr_image,
        totp_secret=TOTP.get_totp_pretty_key(session.get("tmp_totp_secret", "")),
    )


@setup.route("/setup/loading", methods=["GET"])
def setup_loading():
    if current_user.is_authenticated:
        return redirect(url_for("home.home_page"))

    if DB.get_ui_user():
        db_config = BW_CONFIG.get_config(methods=False, filtered_settings=("SERVER_NAME", "USE_UI", "REVERSE_PROXY_URL"))
        for server_name in db_config["SERVER_NAME"].split(" "):
            if server_name and db_config.get(f"{server_name}_USE_UI", db_config.get("USE_UI", "no")) == "yes":
                return redirect(url_for("login.login_page"), 301)

    target_endpoint = request.args.get("target_endpoint", "")
    return render_template(
        "loading.html",
        message="Setting up Web UI...",
        target_endpoint=target_endpoint,
        next=target_endpoint.replace("/check", "/login") if target_endpoint else url_for("login.login_page"),
    )
