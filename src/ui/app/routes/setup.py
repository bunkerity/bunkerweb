from datetime import datetime, timedelta
from itertools import chain
from os import environ, getenv

# from secrets import choice
# from string import ascii_letters, digits
from re import escape, match
from time import sleep, time

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user

# from app.models.totp import totp as TOTP

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import LOGGER, USER_PASSWORD_RX, gen_password_hash

from app.routes.utils import REVERSE_PROXY_PATH, handle_error

setup = Blueprint("setup", __name__)


@setup.route("/setup", methods=["GET", "POST"])
def setup_page():
    if current_user.is_authenticated:
        return redirect(url_for("home.home_page"))
    db_config = DB.get_config(
        filtered_settings=(
            "SERVER_NAME",
            "MULTISITE",
            "USE_UI",
            "UI_HOST",
            "AUTO_LETS_ENCRYPT",
            "USE_LETS_ENCRYPT_STAGING",
            "EMAIL_LETS_ENCRYPT",
            "LETS_ENCRYPT_CHALLENGE",
            "LETS_ENCRYPT_DNS_PROVIDER",
            "LETS_ENCRYPT_DNS_PROPAGATION",
            "USE_LETS_ENCRYPT_WILDCARD",
            "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM",
            "USE_CUSTOM_SSL",
            "CUSTOM_SSL_CERT",
            "CUSTOM_SSL_KEY",
        ),
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

        required_keys = ["theme"]
        if not ui_reverse_proxy:
            required_keys.extend(
                [
                    "server_name",
                    "ui_host",
                    "ui_url",
                    "auto_lets_encrypt",
                    "lets_encrypt_staging",
                    "lets_encrypt_wildcard",
                    "email_lets_encrypt",
                    "lets_encrypt_challenge",
                    "lets_encrypt_dns_provider",
                    "lets_encrypt_dns_propagation",
                    "lets_encrypt_dns_credential_items",
                    "use_custom_ssl",
                    "custom_ssl_cert",
                    "custom_ssl_key",
                ]
            )
        if not admin_user:
            required_keys.extend(
                ["admin_username", "admin_email", "admin_password", "admin_password_check"]
            )  # TODO: add "2fa_code" back when TOTP is implemented in setup wizard

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

            # if request.form["2fa_code"]: # TODO: uncomment when TOTP is implemented in setup wizard
            #     totp_secret = session.pop("tmp_totp_secret", "")
            #     if not TOTP.verify_totp(request.form["2fa_code"], totp_secret=totp_secret, user=current_user):
            #         return handle_error("The totp token is invalid.", "setup")

            #     totp_recovery_codes = TOTP.generate_recovery_codes()

            ret = DB.create_ui_user(
                request.form["admin_username"],
                gen_password_hash(request.form["admin_password"]),
                ["admin"],
                request.form["admin_email"] or None,
                theme=request.form["theme"],
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

            base_config = {
                "SERVER_NAME": request.form["server_name"],
                "USE_UI": "yes",
                "USE_TEMPLATE": "ui",
            }

            config = {
                "USE_REVERSE_PROXY": "yes",
                "REVERSE_PROXY_HOST": request.form["ui_host"],
                "REVERSE_PROXY_URL": request.form["ui_url"] or "/",
                "AUTO_LETS_ENCRYPT": "yes" if request.form.get("auto_lets_encrypt", "no") == "yes" else "no",
                "USE_LETS_ENCRYPT_STAGING": request.form["lets_encrypt_staging"],
                "USE_LETS_ENCRYPT_WILDCARD": request.form["lets_encrypt_wildcard"],
                "EMAIL_LETS_ENCRYPT": request.form["email_lets_encrypt"],
                "LETS_ENCRYPT_CHALLENGE": request.form["lets_encrypt_challenge"],
                "LETS_ENCRYPT_DNS_PROVIDER": request.form["lets_encrypt_dns_provider"],
                "LETS_ENCRYPT_DNS_PROPAGATION": request.form["lets_encrypt_dns_propagation"],
            }

            lets_encrypt_dns_credential_items = request.form.getlist("lets_encrypt_dns_credential_items")
            for x in range(len(lets_encrypt_dns_credential_items)):
                if lets_encrypt_dns_credential_items[x]:
                    config["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" + (f"_{x}" if x else "")] = lets_encrypt_dns_credential_items[x]

            if request.form.get("auto_lets_encrypt", "no") == "no":
                if request.form.get("use_custom_ssl", "no") == "yes":
                    if not all(
                        [
                            bool(request.form.get("custom_ssl_cert", "")),
                            bool(request.form.get("custom_ssl_key", "")),
                        ]
                    ):
                        return handle_error("When using a custom SSL certificate, you must set both the certificate and the key.", "setup")

                    config.update(
                        {
                            "USE_CUSTOM_SSL": "yes",
                            "CUSTOM_SSL_CERT": request.form.get("custom_ssl_cert", ""),
                            "CUSTOM_SSL_KEY": request.form.get("custom_ssl_key", ""),
                        }
                    )
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

            LOGGER.debug(f"Creating new service with base_config: {base_config} and config: {config}")

            operation, error = BW_CONFIG.new_service(base_config, override_method="wizard", check_changes=False)
            if error:
                return handle_error(f"Couldn't create the new service: {operation}", "setup", False, "error")

            operation, error = BW_CONFIG.edit_service(request.form["server_name"], config | base_config, check_changes=False)
            if error:
                return handle_error(f"Couldn't edit the new service: {operation}", "setup", False, "error")

            err = DB.checked_changes(["config", "custom_configs"], plugins_changes="all", value=True)
            if err:
                LOGGER.error(f"Error while applying changes to the database: {err}, you may need to reload the application")

        return Response(status=200)

    # session["tmp_totp_secret"] = TOTP.generate_totp_secret() # TODO: uncomment when TOTP is implemented in setup wizard
    # totp_qr_image = TOTP.generate_qrcode(current_user.get_id(), session["tmp_totp_secret"])

    lets_encrypt_dns_credential_items = [
        value for key, value in chain(db_config.items(), environ.items()) if key.startswith("LETS_ENCRYPT_DNS_CREDENTIAL_ITEM")
    ]

    return render_template(
        "setup.html",
        ui_user=admin_user,
        ui_reverse_proxy=ui_reverse_proxy,
        username=getenv("ADMIN_USERNAME", ""),
        password=getenv("ADMIN_PASSWORD", ""),
        ui_host=db_config.get("UI_HOST", getenv("UI_HOST", "")),
        auto_lets_encrypt=db_config.get("AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")),
        lets_encrypt_staging=db_config.get("USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")),
        lets_encrypt_wildcard=db_config.get("USE_LETS_ENCRYPT_WILDCARD", getenv("USE_LETS_ENCRYPT_WILDCARD", "no")),
        email_lets_encrypt=db_config.get("EMAIL_LETS_ENCRYPT", getenv("EMAIL_LETS_ENCRYPT", "")),
        lets_encrypt_challenge=db_config.get("LETS_ENCRYPT_CHALLENGE", getenv("LETS_ENCRYPT_CHALLENGE", "http")),
        lets_encrypt_dns_provider=db_config.get("LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", "")),
        lets_encrypt_dns_propagation=db_config.get("LETS_ENCRYPT_DNS_PROPAGATION", getenv("LETS_ENCRYPT_DNS_PROPAGATION", "default")),
        lets_encrypt_dns_credential_items=lets_encrypt_dns_credential_items,
        use_custom_ssl=db_config.get("USE_CUSTOM_SSL", getenv("USE_CUSTOM_SSL", "no")),
        custom_ssl_cert=db_config.get("CUSTOM_SSL_CERT", getenv("CUSTOM_SSL_CERT", "")),
        custom_ssl_key=db_config.get("CUSTOM_SSL_KEY", getenv("CUSTOM_SSL_KEY", "")),
        # totp_qr_image=totp_qr_image,
        # totp_secret=TOTP.get_totp_pretty_key(session.get("tmp_totp_secret", "")),
    )


@setup.route("/setup/loading", methods=["GET"])
def setup_loading():
    if current_user.is_authenticated:
        return redirect(url_for("home.home_page"))

    DATA.load_from_file()

    db_config = DB.get_config(filtered_settings=("SERVER_NAME", "USE_UI", "REVERSE_PROXY_URL"))
    ui_service = {}
    ui_admin = DB.get_ui_user()
    admin_old_enough = ui_admin and ui_admin.creation_date < datetime.now() - timedelta(minutes=5)

    for server_name in db_config["SERVER_NAME"].split(" "):
        if server_name and db_config.get(f"{server_name}_USE_UI", "no") == "yes":
            if admin_old_enough:
                return redirect(url_for("login.login_page"), 301)
            ui_service = {"server_name": server_name, "url": db_config.get(f"{server_name}_REVERSE_PROXY_URL", "/")}
            break

    if not ui_service:
        sleep(1)
        return redirect(url_for("setup.setup_loading"))

    target_endpoint = request.args.get("target_endpoint", "")
    if target_endpoint and not match(
        rf"^https://{escape(ui_service['server_name'])}{escape(ui_service['url'])}/check$".replace("//check", "/check"), target_endpoint
    ):
        return Response(status=400)

    return render_template(
        "loading.html",
        message="Setting up Web UI...",
        target_endpoint=target_endpoint,
        next=target_endpoint.replace("/check", "/login") if target_endpoint else url_for("login.login_page"),
    )
