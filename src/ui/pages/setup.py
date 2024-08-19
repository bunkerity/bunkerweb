from os import getenv
from secrets import choice
from string import ascii_letters, digits
from threading import Thread
from time import time

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for

from utils import USER_PASSWORD_RX, gen_password_hash

from pages.utils import REVERSE_PROXY_PATH, handle_error, manage_bunkerweb

setup = Blueprint("setup", __name__)


@setup.route("/setup", methods=["GET", "POST"])
def setup_page():
    db_config = current_app.bw_config.get_config(methods=False, filtered_settings=("SERVER_NAME", "MULTISITE", "USE_UI", "UI_HOST", "AUTO_LETS_ENCRYPT"))

    admin_user = current_app.db.get_ui_user()

    ui_reverse_proxy = False
    for server_name in db_config["SERVER_NAME"].split(" "):
        if server_name and db_config.get(f"{server_name}_USE_UI", db_config.get("USE_UI", "no")) == "yes":
            if admin_user:
                return redirect(url_for("login.login_page"), 301)
            ui_reverse_proxy = True
            break

    if request.method == "POST":
        if current_app.db.readonly:
            return handle_error("Database is in read-only mode", "setup")

        required_keys = []
        if not ui_reverse_proxy:
            required_keys.extend(["server_name", "ui_host", "ui_url"])
        if not admin_user:
            required_keys.extend(["admin_username", "admin_password", "admin_password_check"])

        if not any(key in request.form for key in required_keys):
            return handle_error(f"Missing either one of the following parameters: {', '.join(required_keys)}.", "setup")

        if not admin_user:
            if len(request.form["admin_username"]) > 256:
                return handle_error("The admin username is too long. It must be less than 256 characters.", "setup")

            if request.form["admin_password"] != request.form["admin_password_check"]:
                return handle_error("The passwords do not match.", "setup")

            if not USER_PASSWORD_RX.match(request.form["admin_password"]):
                return handle_error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).",
                    "setup",
                )

            ret = current_app.db.create_ui_user(
                request.form["admin_username"], gen_password_hash(request.form["admin_password"]), ["admin"], method="ui", admin=True
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

            current_app.data["RELOADING"] = True
            current_app.data["LAST_RELOAD"] = time()

            config = {
                "SERVER_NAME": request.form["server_name"],
                "USE_UI": "yes",
                "USE_REVERSE_PROXY": "yes",
                "REVERSE_PROXY_HOST": request.form["ui_host"],
                "REVERSE_PROXY_URL": request.form["ui_url"] or "/",
                "INTERCEPTED_ERROR_CODES": "400 404 405 413 429 500 501 502 503 504",
                "ALLOWED_METHODS": "GET|POST|PUT|DELETE",
                "MAX_CLIENT_SIZE": "50m",
                "KEEP_UPSTREAM_HEADERS": "Content-Security-Policy Strict-Transport-Security X-Frame-Options X-Content-Type-Options Referrer-Policy",
            }

            if request.form.get("auto_lets_encrypt", "no") == "yes":
                config["AUTO_LETS_ENCRYPT"] = "yes"
            else:
                config["GENERATE_SELF_SIGNED_SSL"] = "yes"
                config["SELF_SIGNED_SSL_SUBJ"] = f"/CN={request.form['server_name']}/"

            if not config.get("MULTISITE", "no") == "yes":
                current_app.bw_config.edit_global_conf({"MULTISITE": "yes"}, check_changes=False)

            # deepcode ignore MissingAPI: We don't need to check to wait for the thread to finish
            Thread(
                target=manage_bunkerweb,
                name="Reloading instances",
                args=("services", config, request.form["server_name"], request.form["server_name"]),
                kwargs={"operation": "new", "threaded": True},
            ).start()

        return Response(status=200)

    return render_template(
        "setup.html",
        ui_user=admin_user,
        ui_reverse_proxy=ui_reverse_proxy,
        username=getenv("ADMIN_USERNAME", ""),
        password=getenv("ADMIN_PASSWORD", ""),
        ui_host=db_config.get("UI_HOST", getenv("UI_HOST", "")),
        auto_lets_encrypt=db_config.get("AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) == "yes",
        random_url=f"/{''.join(choice(ascii_letters + digits) for _ in range(10))}",
    )


@setup.route("/setup/loading", methods=["GET"])
def setup_loading():
    return render_template("setup_loading.html")
