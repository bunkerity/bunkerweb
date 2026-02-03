from datetime import datetime, timedelta
from itertools import chain
from os import environ, getenv

# from secrets import choice
# from string import ascii_letters, digits
from re import escape, match
from time import sleep

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user

# from app.models.totp import totp as TOTP

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import LOGGER, USER_PASSWORD_RX, gen_password_hash, _sanitize_internal_next

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
            "REVERSE_PROXY_URL",
            "AUTO_LETS_ENCRYPT",
            "USE_LETS_ENCRYPT_STAGING",
            "EMAIL_LETS_ENCRYPT",
            "LETS_ENCRYPT_CHALLENGE",
            "LETS_ENCRYPT_PROFILE",
            "LETS_ENCRYPT_CUSTOM_PROFILE",
            "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES",
            "LETS_ENCRYPT_DNS_PROVIDER",
            "LETS_ENCRYPT_DNS_PROPAGATION",
            "USE_LETS_ENCRYPT_WILDCARD",
            "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM",
            "USE_CUSTOM_SSL",
            "CUSTOM_SSL_CERT_PRIORITY",
            "CUSTOM_SSL_CERT",
            "CUSTOM_SSL_KEY",
            "CUSTOM_SSL_CERT_DATA",
            "CUSTOM_SSL_KEY_DATA",
            "PRO_LICENSE_KEY",
            "USE_REAL_IP",
            "USE_PROXY_PROTOCOL",
            "REAL_IP_FROM",
            "REAL_IP_HEADER",
            "REAL_IP_RECURSIVE",
            "REAL_IP_FROM_URLS",
        ),
    )

    admin_user = DB.get_ui_user()
    pro_license_key = db_config.get("PRO_LICENSE_KEY", getenv("PRO_LICENSE_KEY", ""))

    ui_reverse_proxy = None
    ui_reverse_proxy_url = None
    for server_name in db_config["SERVER_NAME"].split():
        if server_name and db_config.get(f"{server_name}_USE_UI", db_config.get("USE_UI", "no")) == "yes":
            if admin_user:
                return redirect(url_for("login.login_page"), 303)
            ui_reverse_proxy = server_name
            ui_reverse_proxy_url = db_config.get(f"{server_name}_REVERSE_PROXY_URL", db_config.get("REVERSE_PROXY_URL", "/"))
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
                    "custom_ssl_cert_priority",
                    "custom_ssl_cert",
                    "custom_ssl_key",
                    "custom_ssl_cert_data",
                    "custom_ssl_key_data",
                ]
            )
        if not admin_user:
            required_keys.extend(
                ["admin_username", "admin_email", "admin_password", "admin_password_check"]
            )  # TODO: add "2fa_code" back when TOTP is implemented in setup wizard

        if not any(key in request.form for key in required_keys):
            return handle_error(f"Missing either one of the following parameters: {', '.join(required_keys)}.", "setup")

        if not pro_license_key and request.form.get("pro_license_key", ""):
            global_config = DB.get_config(global_only=True)
            BW_CONFIG.edit_global_conf(global_config | {"PRO_LICENSE_KEY": request.form["pro_license_key"]}, check_changes=False)

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
                theme=request.form.get("theme", "light"),
                language=request.form.get("language", "en"),
                totp_secret=totp_secret,
                totp_recovery_codes=totp_recovery_codes,
                method="wizard",
                admin=True,
            )
            if ret:
                return handle_error(f"Couldn't create the admin user in the database: {ret}", "setup", False, "error")

            flash("The admin user was created successfully")

        if not ui_reverse_proxy:
            server_names = db_config["SERVER_NAME"].split()
            if request.form["server_name"] in server_names:
                return handle_error(f"The hostname {request.form['server_name']} is already in use.", "setup")
            else:
                for server_name in server_names:
                    if request.form["server_name"] in db_config.get(f"{server_name}_SERVER_NAME", "").split():
                        return handle_error(f"The hostname {request.form['server_name']} is already in use.", "setup")

            if not REVERSE_PROXY_PATH.match(request.form["ui_host"]):
                return handle_error("The hostname is not valid.", "setup")

            base_config = {
                "SERVER_NAME": request.form["server_name"],
                "USE_UI": "yes",
                "USE_TEMPLATE": "ui",
            }

            config = {
                "USE_REVERSE_PROXY": "yes",
                "REVERSE_PROXY_HOST": request.form["ui_host"],
                "REVERSE_PROXY_URL": request.form["ui_url"] or "/",
                "AUTO_LETS_ENCRYPT": request.form.get("auto_lets_encrypt", "no"),
                "USE_LETS_ENCRYPT_STAGING": request.form["lets_encrypt_staging"],
                "USE_LETS_ENCRYPT_WILDCARD": request.form["lets_encrypt_wildcard"],
                "EMAIL_LETS_ENCRYPT": request.form["email_lets_encrypt"],
                "LETS_ENCRYPT_CHALLENGE": request.form["lets_encrypt_challenge"],
                "LETS_ENCRYPT_PROFILE": request.form["lets_encrypt_profile"],
                "LETS_ENCRYPT_CUSTOM_PROFILE": request.form["lets_encrypt_custom_profile"],
                "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES": request.form.get("lets_encrypt_disable_public_suffixes", "yes"),
                "LETS_ENCRYPT_DNS_PROVIDER": request.form["lets_encrypt_dns_provider"],
                "LETS_ENCRYPT_DNS_PROPAGATION": request.form["lets_encrypt_dns_propagation"],
                "USE_REAL_IP": request.form.get("use_real_ip", "no"),
                "USE_PROXY_PROTOCOL": request.form.get("use_proxy_protocol", "no"),
                "REAL_IP_FROM": request.form.get("real_ip_from", "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"),
                "REAL_IP_HEADER": request.form.get("real_ip_header", "X-Forwarded-For"),
                "REAL_IP_RECURSIVE": request.form.get("real_ip_recursive", "yes"),
                "REAL_IP_FROM_URLS": request.form.get("real_ip_from_urls", ""),
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
                    ) and not all(
                        [
                            bool(request.form.get("custom_ssl_cert_data", "")),
                            bool(request.form.get("custom_ssl_key_data", "")),
                        ]
                    ):
                        return handle_error("When using a custom SSL certificate, you must set both the certificate and the key.", "setup")

                    config.update(
                        {
                            "USE_CUSTOM_SSL": "yes",
                            "CUSTOM_SSL_CERT_PRIORITY": request.form.get("custom_ssl_cert_priority", "file"),
                            "CUSTOM_SSL_CERT": request.form.get("custom_ssl_cert", ""),
                            "CUSTOM_SSL_KEY": request.form.get("custom_ssl_key", ""),
                            "CUSTOM_SSL_CERT_DATA": request.form.get("custom_ssl_cert_data", ""),
                            "CUSTOM_SSL_KEY_DATA": request.form.get("custom_ssl_key_data", ""),
                        }
                    )

            if not config.get("MULTISITE", "no") == "yes":
                global_config = DB.get_config(global_only=True)
                BW_CONFIG.edit_global_conf(global_config | {"MULTISITE": "yes"}, check_changes=False)

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

    server_name = request.headers.get("Host", "").split(":")[0]
    if not server_name:
        server_name = "www.example.com"

    return render_template(
        "setup.html",
        plugins_settings=BW_CONFIG.get_plugins_settings(),
        server_name=server_name,
        ui_user=admin_user,
        ui_reverse_proxy=ui_reverse_proxy,
        ui_reverse_proxy_url=ui_reverse_proxy_url,
        username=getenv("ADMIN_USERNAME", ""),
        password=getenv("ADMIN_PASSWORD", ""),
        ui_host=db_config.get("UI_HOST", getenv("UI_HOST", "")),
        auto_lets_encrypt=db_config.get("AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")),
        lets_encrypt_staging=db_config.get("USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")),
        lets_encrypt_wildcard=db_config.get("USE_LETS_ENCRYPT_WILDCARD", getenv("USE_LETS_ENCRYPT_WILDCARD", "no")),
        email_lets_encrypt=db_config.get("EMAIL_LETS_ENCRYPT", getenv("EMAIL_LETS_ENCRYPT", "")),
        lets_encrypt_challenge=db_config.get("LETS_ENCRYPT_CHALLENGE", getenv("LETS_ENCRYPT_CHALLENGE", "http")),
        lets_encrypt_profile=db_config.get("LETS_ENCRYPT_PROFILE", getenv("LETS_ENCRYPT_PROFILE", "classic")),
        lets_encrypt_custom_profile=db_config.get("LETS_ENCRYPT_CUSTOM_PROFILE", getenv("LETS_ENCRYPT_CUSTOM_PROFILE", "")),
        lets_encrypt_disable_public_suffixes=db_config.get("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", getenv("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "yes")),
        lets_encrypt_dns_provider=db_config.get("LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", "")),
        lets_encrypt_dns_propagation=db_config.get("LETS_ENCRYPT_DNS_PROPAGATION", getenv("LETS_ENCRYPT_DNS_PROPAGATION", "default")),
        lets_encrypt_dns_credential_items=lets_encrypt_dns_credential_items,
        use_custom_ssl=db_config.get("USE_CUSTOM_SSL", getenv("USE_CUSTOM_SSL", "no")),
        custom_ssl_cert_priority=db_config.get("CUSTOM_SSL_CERT_PRIORITY", getenv("CUSTOM_SSL_CERT_PRIORITY", "file")),
        custom_ssl_cert=db_config.get("CUSTOM_SSL_CERT", getenv("CUSTOM_SSL_CERT", "")),
        custom_ssl_key=db_config.get("CUSTOM_SSL_KEY", getenv("CUSTOM_SSL_KEY", "")),
        custom_ssl_cert_data=db_config.get("CUSTOM_SSL_CERT_DATA", getenv("CUSTOM_SSL_CERT_DATA", "")),
        custom_ssl_key_data=db_config.get("CUSTOM_SSL_KEY_DATA", getenv("CUSTOM_SSL_KEY_DATA", "")),
        pro_license_key=db_config.get("PRO_LICENSE_KEY", getenv("PRO_LICENSE_KEY", "")),
        use_real_ip=db_config.get("USE_REAL_IP", getenv("USE_REAL_IP", "no")),
        use_proxy_protocol=db_config.get("USE_PROXY_PROTOCOL", getenv("USE_PROXY_PROTOCOL", "no")),
        real_ip_from=db_config.get("REAL_IP_FROM", getenv("REAL_IP_FROM", "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8")),
        real_ip_header=db_config.get("REAL_IP_HEADER", getenv("REAL_IP_HEADER", "X-Forwarded-For")),
        real_ip_recursive=db_config.get("REAL_IP_RECURSIVE", getenv("REAL_IP_RECURSIVE", "yes")),
        real_ip_from_urls=db_config.get("REAL_IP_FROM_URLS", getenv("REAL_IP_FROM_URLS", "")),
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
    ui_admin = DB.get_ui_user(as_dict=True)
    admin_old_enough = ui_admin and ui_admin["creation_date"] < datetime.now().astimezone() - timedelta(minutes=5)

    for server_name in db_config["SERVER_NAME"].split():
        if server_name and db_config.get(f"{server_name}_USE_UI", "no") == "yes":
            if admin_old_enough:
                return redirect(url_for("login.login_page"), 303)
            ui_service = {"server_name": server_name, "url": db_config.get(f"{server_name}_REVERSE_PROXY_URL", "/")}
            break

    if not ui_service:
        sleep(1)
        return redirect(url_for("setup.setup_loading"))

    ui_service["url"] = ui_service.get("url") or "/"
    if not ui_service["url"].startswith("/"):
        ui_service["url"] = f"/{ui_service['url']}"
    if not ui_service["url"].endswith("/"):
        ui_service["url"] = f"{ui_service['url']}/"

    target_endpoint = request.args.get("target_endpoint", "")
    if target_endpoint and not match(
        rf"^https://{escape(ui_service['server_name'])}{escape(ui_service['url'])}/check$".replace("//check", "/check"), target_endpoint
    ):
        return Response(status=400)

    # Support an optional next parameter but sanitize (falls back to login)
    default_next = f"{ui_service['url']}login"
    requested_next = request.args.get("next")
    try:
        safe_next = _sanitize_internal_next(requested_next, default_next)
    except Exception:
        safe_next = default_next

    return render_template(
        "loading.html",
        message="Setting up Web UI...",
        target_endpoint=target_endpoint,
        next=safe_next,
    )
