import os
from shutil import rmtree, copytree, chown
from logging import getLogger, INFO, ERROR, StreamHandler, Formatter
from traceback import format_exc
from typing import Optional
from jinja2 import Template
from threading import Thread
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
from json import JSONDecodeError, load as json_load
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dateutil.parser import parse as dateutil_parse
from requests import get
from requests.utils import default_headers
from sys import path as sys_path, exit as sys_exit, modules as sys_modules
from copy import deepcopy
from re import match as re_match
from docker import DockerClient
from docker.errors import (
    NotFound as docker_NotFound,
    APIError as docker_APIError,
    DockerException,
)
from uuid import uuid4
from time import sleep, time
import tarfile
import zipfile

sys_path.append("/opt/bunkerweb/ui/src")

from ConfigFiles import ConfigFiles
from Config import Config
from ReverseProxied import ReverseProxied
from User import User
from utils import (
    check_settings,
    env_to_summary_class,
    form_plugin_gen,
    form_service_gen,
    form_service_gen_multiple,
    form_service_gen_multiple_values,
    gen_folders_tree_html,
    get_variables,
    path_to_dict,
)

sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/api")

from src.Instances import Instances
from API import API
from ApiCaller import ApiCaller

# Set up logger
logger = getLogger("flask_app")
logger.setLevel(INFO)
# create console handler with a higher log level
ch = StreamHandler()
ch.setLevel(ERROR)
# create formatter and add it to the handlers
formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)

# Flask app
app = Flask(
    __name__,
    static_url_path="/",
    static_folder="static",
    template_folder="templates",
)
app.wsgi_app = ReverseProxied(app.wsgi_app)

# Set variables and instantiate objects
vars = get_variables()

if not vars["FLASK_ENV"] == "development" and vars["ADMIN_PASSWORD"] == "changeme":
    logger.error("Please change the default admin password.")
    sys_exit(1)

if not vars["FLASK_ENV"] == "development" and (
    vars["ABSOLUTE_URI"].endswith("/changeme/")
    or vars["ABSOLUTE_URI"].endswith("/changeme")
):
    logger.error("Please change the default URL.")
    sys_exit(1)

with open("/opt/bunkerweb/tmp/ui.pid", "w") as f:
    f.write(str(os.getpid()))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
user = User(vars["ADMIN_USERNAME"], vars["ADMIN_PASSWORD"])
api_caller = ApiCaller()
PLUGIN_KEYS = [
    "id",
    "order",
    "name",
    "description",
    "version",
    "settings",
]

try:
    docker_client: DockerClient = DockerClient(base_url=vars["DOCKER_HOST"])
except (docker_APIError, DockerException):
    docker_client = None


if docker_client:
    apis: list[API] = []
    for container in docker_client.containers.list(filters={"label": "bunkerweb.UI"}):
        env_variables = {
            x[0]: x[1]
            for x in [env.split("=") for env in container.attrs["Config"]["Env"]]
        }

        apis.append(
            API(
                f"http://{container.name}:{env_variables.get('API_HTTP_PORT', '5000')}",
                env_variables.get("API_SERVER_NAME", "bwapi"),
            )
        )

    api_caller._set_apis(apis)

try:
    app.config.update(
        DEBUG=True,
        SECRET_KEY=vars["FLASK_SECRET"],
        ABSOLUTE_URI=vars["ABSOLUTE_URI"],
        INSTANCES=Instances(docker_client),
        CONFIG=Config(),
        CONFIGFILES=ConfigFiles(),
        SESSION_COOKIE_DOMAIN=vars["ABSOLUTE_URI"]
        .replace("http://", "")
        .replace("https://", "")
        .split("/")[0],
        WTF_CSRF_SSL_STRICT=False,
        USER=user,
        SEND_FILE_MAX_AGE_DEFAULT=86400,
        PLUGIN_ARGS=None,
        RELOADING=False,
        TO_FLASH=[],
    )
except FileNotFoundError as e:
    logger.error(repr(e), e.filename)
    sys_exit(1)

# Declare functions for jinja2
app.jinja_env.globals.update(env_to_summary_class=env_to_summary_class)
app.jinja_env.globals.update(form_plugin_gen=form_plugin_gen)
app.jinja_env.globals.update(form_service_gen=form_service_gen)
app.jinja_env.globals.update(form_service_gen_multiple=form_service_gen_multiple)
app.jinja_env.globals.update(
    form_service_gen_multiple_values=form_service_gen_multiple_values
)
app.jinja_env.globals.update(gen_folders_tree_html=gen_folders_tree_html)
app.jinja_env.globals.update(check_settings=check_settings)


def manage_bunkerweb(method: str, operation: str = "reloads", *args):
    # Do the operation
    if method == "services":
        if operation == "new":
            operation, error = app.config["CONFIG"].new_service(args[0])
        elif operation == "edit":
            operation, error = app.config["CONFIG"].edit_service(args[1], args[0])
        elif operation == "delete":
            operation, error = app.config["CONFIG"].delete_service(args[2])

        if error:
            app.config["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            app.config["TO_FLASH"].append({"content": operation, "type": "success"})
    if method == "global_config":
        operation = app.config["CONFIG"].edit_global_conf(args[0])
        app.config["TO_FLASH"].append({"content": operation, "type": "success"})
    elif method == "plugins":
        app.config["CONFIG"].reload_config()

    if operation == "reload":
        operation = app.config["INSTANCES"].reload_instance(args[0])
    elif operation == "start":
        operation = app.config["INSTANCES"].start_instance(args[0])
    elif operation == "stop":
        operation = app.config["INSTANCES"].stop_instance(args[0])
    elif operation == "restart":
        operation = app.config["INSTANCES"].restart_instance(args[0])
    else:
        operation = app.config["INSTANCES"].reload_instances()

    if isinstance(operation, list):
        for op in operation:
            app.config["TO_FLASH"].append(
                {"content": f"Reload failed for the instance {op}", "type": "error"}
            )
    elif operation.startswith("Can't"):
        app.config["TO_FLASH"].append({"content": operation, "type": "error"})
    else:
        app.config["TO_FLASH"].append({"content": operation, "type": "success"})

    app.config["RELOADING"] = False


@login_manager.user_loader
def load_user(user_id):
    return User(user_id, vars["ADMIN_PASSWORD"])


# CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)


@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    """
    It takes a CSRFError exception as an argument, and returns a Flask response

    :param e: The exception object
    :return: A template with the error message and a 401 status code.
    """
    logout_user()
    flash("Wrong CSRF token !", "error")
    return render_template("login.html"), 403


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/loading")
@login_required
def loading():
    next_url: str = request.values.get("next", None) or url_for("home")
    message: Optional[str] = request.values.get("message", None)
    return render_template(
        "loading.html",
        message=message if message is not None else "Loading",
        next=next_url,
    )


@app.route("/home")
@login_required
def home():
    """
    It returns the home page
    :return: The home.html template is being rendered with the following variables:
        check_version: a boolean indicating whether the local version is the same as the remote version
        remote_version: the remote version
        version: the local version
        instances_number: the number of instances
        services_number: the number of services
        posts: a list of posts
    """

    r = get(
        "https://raw.githubusercontent.com/bunkerity/bunkerweb/master/VERSION",
    )
    remote_version = None

    if r.status_code == 200:
        remote_version = r.text.strip()

    with open("/opt/bunkerweb/VERSION", "r") as f:
        version = f.read().strip()

    headers = default_headers()
    headers.update({"User-Agent": "bunkerweb-ui", "Host": "www.bunkerweb.io"})

    formatted_posts = None
    try:
        r = get(
            f"https://www.bunkerweb.io/api/posts/0/2",
            headers=headers,
        )

        if r.status_code == 200:
            posts = r.json()
            formatted_posts = []

            for post in posts["data"]:
                formatted_posts.append(
                    {
                        "link": f"https://www.bunkerweb.io/blog/post/{post['slug']}",
                        "title": post["title"],
                        "description": f"{post['content'][:256]}..."
                        if len(post["content"]) > 256
                        else post["content"],
                        "date": datetime.strptime(post["date"], "%Y-%m-%d")
                        .astimezone(timezone.utc)
                        .strftime("%B %d, %Y"),
                        "image_url": post["photo"]["url"].replace("\n", ""),
                    }
                )
        elif r.status_code == 403:
            flash("You are not allowed to access the bunkerweb.io API", "error")
    except Exception as e:
        flash(f"Error while fetching posts: {e}", "error")

    instances_number = len(app.config["INSTANCES"].get_instances())
    services_number = len(app.config["CONFIG"].get_services())

    return render_template(
        "home.html",
        check_version=not remote_version or version == remote_version,
        remote_version=remote_version,
        version=version,
        instances_number=instances_number,
        services_number=services_number,
        posts=formatted_posts,
    )


@app.route("/instances", methods=["GET", "POST"])
@login_required
def instances():
    # Manage instances
    if request.method == "POST":
        # Check operation
        if not "operation" in request.form or not request.form["operation"] in [
            "reload",
            "start",
            "stop",
            "restart",
        ]:
            flash("Missing operation parameter on /instances.", "error")
            return redirect(url_for("loading", next=url_for("instances")))

        # Check that all fields are present
        if not "INSTANCE_ID" in request.form:
            flash("Missing INSTANCE_ID parameter.", "error")
            return redirect(url_for("loading", next=url_for("instances")))

        app.config["RELOADING"] = True
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("instances", request.form["operation"], request.form["INSTANCE_ID"]),
        ).start()

        return redirect(
            url_for(
                "loading",
                next=url_for("instances"),
                message=(
                    f"{request.form['operation'].title()}ing"
                    if request.form["operation"] != "stop"
                    else "Stopping"
                )
                + " instance",
            )
        )

    # Display instances
    instances = app.config["INSTANCES"].get_instances()
    return render_template("instances.html", title="Instances", instances=instances)


@app.route("/services", methods=["GET", "POST"])
@login_required
def services():
    if request.method == "POST":

        # Check operation
        if not "operation" in request.form or not request.form["operation"] in [
            "new",
            "edit",
            "delete",
        ]:
            flash("Missing operation parameter on /services.", "error")
            return redirect(url_for("loading", next=url_for("services")))

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        if (
            not "OLD_SERVER_NAME" in request.form
            and request.form["operation"] == "edit"
        ):
            flash("Missing OLD_SERVER_NAME parameter.", "error")
            return redirect(url_for("loading", next=url_for("services")))

        if request.form["operation"] in ("new", "edit"):
            del variables["operation"]

            if request.form["operation"] == "edit":
                del variables["OLD_SERVER_NAME"]

            # Edit check fields and remove already existing ones
            config = app.config["CONFIG"].get_config()
            for variable in deepcopy(variables):
                if variables[variable] == "on":
                    variables[variable] = "yes"
                elif variables[variable] == "off":
                    variables[variable] = "no"

                if (
                    request.form["operation"] == "edit"
                    and variable != "SERVER_NAME"
                    and variables[variable] == config.get(variable, None)
                    or not variables[variable].strip()
                ):
                    del variables[variable]

            if not variables:
                flash(
                    f"{variables['SERVER_NAME'].split(' ')[0]} was not edited because no values were changed."
                )
                return redirect(url_for("loading", next=url_for("services")))

            error = app.config["CONFIG"].check_variables(variables)

            if error:
                return redirect(url_for("loading", next=url_for("services")))

        # Delete
        elif request.form["operation"] == "delete":
            if not "SERVER_NAME" in request.form:
                flash("Missing SERVER_NAME parameter.", "error")
                return redirect(url_for("loading", next=url_for("services")))

            error = app.config["CONFIG"].check_variables(
                {"SERVER_NAME": request.form["SERVER_NAME"]}
            )

            if error:
                return redirect(url_for("loading", next=url_for("services")))

        error = 0

        # Reload instances
        app.config["RELOADING"] = True
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=(
                "services",
                request.form["operation"],
                variables,
                request.form.get("OLD_SERVER_NAME", "").split(" ")[0],
                variables.get("SERVER_NAME", "").split(" ")[0],
            ),
        ).start()

        message = ""

        if request.form["operation"] == "new":
            message = f"Creating service {variables['SERVER_NAME'].split(' ')[0]}"
        elif request.form["operation"] == "edit":
            message = f"Saving configuration for service {request.form['OLD_SERVER_NAME'].split(' ')[0]}"
        elif request.form["operation"] == "delete":
            message = f"Deleting service {request.form['SERVER_NAME'].split(' ')[0]}"

        return redirect(url_for("loading", next=url_for("services"), message=message))

    # Display services
    services = app.config["CONFIG"].get_services()
    return render_template("services.html", services=services)


@app.route("/global_config", methods=["GET", "POST"])
@login_required
def global_config():
    if request.method == "POST":

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        # Edit check fields and remove already existing ones
        config = app.config["CONFIG"].get_config()
        for variable in deepcopy(variables):
            if variables[variable] == "on":
                variables[variable] = "yes"
            elif variables[variable] == "off":
                variables[variable] = "no"

            if (
                variables[variable] == config.get(variable, None)
                or not variables[variable].strip()
            ):
                del variables[variable]

        if not variables:
            flash(
                f"The global configuration was not edited because no values were changed."
            )
            return redirect(url_for("loading", next=url_for("global_config")))

        error = app.config["CONFIG"].check_variables(variables, True)

        if error:
            return redirect(url_for("loading", next=url_for("global_config")))

        # Reload instances
        app.config["RELOADING"] = True
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=(
                "global_config",
                "reloads",
                variables,
            ),
        ).start()

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config"),
                message="Saving global configuration",
            )
        )

    # Display services
    services = app.config["CONFIG"].get_services()
    return render_template("global_config.html", services=services)


@app.route("/configs", methods=["GET", "POST"])
@login_required
def configs():
    if request.method == "POST":
        operation = ""

        # Check operation
        if not "operation" in request.form or not request.form["operation"] in [
            "new",
            "edit",
            "delete",
        ]:
            flash("Missing operation parameter on /configs.", "error")
            return redirect(url_for("loading", next=url_for("configs")))

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        operation = app.config["CONFIGFILES"].check_path(variables["path"])

        if operation:
            flash(operation, "error")
            return redirect(url_for("loading", next=url_for("configs"))), 500

        if request.form["operation"] in ("new", "edit"):
            if not app.config["CONFIGFILES"].check_name(variables["name"]):
                flash(
                    f"Invalid {variables['type']} name. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 32))",
                    "error",
                )
                return redirect(url_for("loading", next=url_for("configs")))

            if variables["type"] == "file":
                variables["name"] = f"{variables['name']}.conf"
                variables["content"] = BeautifulSoup(
                    variables["content"], "html.parser"
                ).get_text()

            if request.form["operation"] == "new":
                if variables["type"] == "folder":
                    operation, error = app.config["CONFIGFILES"].create_folder(
                        variables["path"], variables["name"]
                    )
                elif variables["type"] == "file":
                    operation, error = app.config["CONFIGFILES"].create_file(
                        variables["path"], variables["name"], variables["content"]
                    )
            elif request.form["operation"] == "edit":
                if variables["type"] == "folder":
                    operation, error = app.config["CONFIGFILES"].edit_folder(
                        variables["path"], variables["name"]
                    )
                elif variables["type"] == "file":
                    operation, error = app.config["CONFIGFILES"].edit_file(
                        variables["path"], variables["name"], variables["content"]
                    )

            if error:
                flash(operation, "error")
                return redirect(url_for("loading", next=url_for("configs")))
        else:
            operation, error = app.config["CONFIGFILES"].delete_path(variables["path"])

            if error:
                flash(operation, "error")
                return redirect(url_for("loading", next=url_for("configs")))

        flash(operation)

        # Reload instances
        app.config["RELOADING"] = True
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("configs",),
        ).start()

        return redirect(url_for("loading", next=url_for("configs")))

    return render_template(
        "configs.html", folders=[path_to_dict("/opt/bunkerweb/configs")]
    )


@app.route("/plugins", methods=["GET", "POST"])
@login_required
def plugins():
    if request.method == "POST":
        operation = ""
        error = 0

        if "operation" in request.form and request.form["operation"] == "delete":
            # Check variables
            variables = deepcopy(request.form.to_dict())
            del variables["csrf_token"]

            operation = app.config["CONFIGFILES"].check_path(
                variables["path"], "/opt/bunkerweb/plugins/"
            )

            if operation:
                flash(operation, "error")
                return redirect(url_for("loading", next=url_for("plugins"))), 500

            operation, error = app.config["CONFIGFILES"].delete_path(variables["path"])

            if error:
                flash(operation, "error")
                return redirect(url_for("loading", next=url_for("plugins")))
        else:
            if not os.path.exists("/opt/bunkerweb/tmp/ui") or not os.listdir(
                "/opt/bunkerweb/tmp/ui"
            ):
                flash("Please upload new plugins to reload plugins", "error")
                return redirect(url_for("loading", next=url_for("plugins")))

            for file in os.listdir("/opt/bunkerweb/tmp/ui"):
                if not os.path.isfile(f"/opt/bunkerweb/tmp/ui/{file}"):
                    continue

                folder_name = ""
                temp_folder_name = file.split(".")[0]

                try:
                    if file.endswith(".zip"):
                        try:
                            with zipfile.ZipFile(
                                f"/opt/bunkerweb/tmp/ui/{file}"
                            ) as zip_file:
                                try:
                                    zip_file.getinfo("plugin.json")
                                    zip_file.extractall(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}"
                                    )
                                    with open(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/plugin.json",
                                        "r",
                                    ) as f:
                                        plugin_file = json_load(f)

                                    if not all(
                                        key in plugin_file.keys() for key in PLUGIN_KEYS
                                    ):
                                        raise ValueError

                                    folder_name = plugin_file["id"]

                                    if not app.config["CONFIGFILES"].check_name(
                                        folder_name
                                    ):
                                        error = 1
                                        flash(
                                            f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 32))",
                                            "error",
                                        )
                                        raise Exception

                                    if os.path.exists(
                                        f"/opt/bunkerweb/plugins/{folder_name}"
                                    ):
                                        raise FileExistsError

                                    copytree(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}",
                                        f"/opt/bunkerweb/plugins/{folder_name}",
                                    )
                                except KeyError:
                                    zip_file.extractall(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}"
                                    )
                                    dirs = [
                                        d
                                        for d in os.listdir(
                                            f"/opt/bunkerweb/tmp/ui/{temp_folder_name}"
                                        )
                                        if os.path.isdir(
                                            f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{d}"
                                        )
                                    ]

                                    if (
                                        not dirs
                                        or len(dirs) > 1
                                        or not os.path.exists(
                                            f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{dirs[0]}/plugin.json"
                                        )
                                    ):
                                        raise KeyError

                                    with open(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{dirs[0]}/plugin.json",
                                        "r",
                                    ) as f:
                                        plugin_file = json_load(f)

                                    if not all(
                                        key in plugin_file.keys() for key in PLUGIN_KEYS
                                    ):
                                        raise ValueError

                                    folder_name = plugin_file["id"]

                                    if not app.config["CONFIGFILES"].check_name(
                                        folder_name
                                    ):
                                        error = 1
                                        flash(
                                            f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 32))",
                                            "error",
                                        )
                                        raise Exception

                                    if os.path.exists(
                                        f"/opt/bunkerweb/plugins/{folder_name}"
                                    ):
                                        raise FileExistsError

                                    copytree(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{dirs[0]}",
                                        f"/opt/bunkerweb/plugins/{folder_name}",
                                    )
                        except zipfile.BadZipFile:
                            error = 1
                            flash(
                                f"{file} is not a valid zip file. ({folder_name if folder_name else temp_folder_name})",
                                "error",
                            )
                    else:
                        try:
                            with tarfile.open(
                                f"/opt/bunkerweb/tmp/ui/{file}",
                                errorlevel=2,
                            ) as tar_file:
                                try:
                                    tar_file.getmember("plugin.json")
                                    tar_file.extractall(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}"
                                    )
                                    with open(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/plugin.json",
                                        "r",
                                    ) as f:
                                        plugin_file = json_load(f)

                                    if not all(
                                        key in plugin_file.keys() for key in PLUGIN_KEYS
                                    ):
                                        raise ValueError

                                    folder_name = plugin_file["id"]

                                    if not app.config["CONFIGFILES"].check_name(
                                        folder_name
                                    ):
                                        error = 1
                                        flash(
                                            f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 32))",
                                            "error",
                                        )
                                        raise Exception

                                    if os.path.exists(
                                        f"/opt/bunkerweb/plugins/{folder_name}"
                                    ):
                                        raise FileExistsError

                                    copytree(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}",
                                        f"/opt/bunkerweb/plugins/{folder_name}",
                                    )
                                except KeyError:
                                    tar_file.extractall(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}",
                                    )
                                    dirs = [
                                        d
                                        for d in os.listdir(
                                            f"/opt/bunkerweb/tmp/ui/{temp_folder_name}"
                                        )
                                        if os.path.isdir(
                                            f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{d}"
                                        )
                                    ]

                                    if (
                                        not dirs
                                        or len(dirs) > 1
                                        or not os.path.exists(
                                            f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{dirs[0]}/plugin.json"
                                        )
                                    ):
                                        raise KeyError

                                    with open(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{dirs[0]}/plugin.json",
                                        "r",
                                    ) as f:
                                        plugin_file = json_load(f)

                                    if not all(
                                        key in plugin_file.keys() for key in PLUGIN_KEYS
                                    ):
                                        raise ValueError

                                    folder_name = plugin_file["id"]

                                    if not app.config["CONFIGFILES"].check_name(
                                        folder_name
                                    ):
                                        error = 1
                                        flash(
                                            f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 32))",
                                            "error",
                                        )
                                        raise Exception

                                    if os.path.exists(
                                        f"/opt/bunkerweb/plugins/{folder_name}"
                                    ):
                                        raise FileExistsError

                                    copytree(
                                        f"/opt/bunkerweb/tmp/ui/{temp_folder_name}/{dirs[0]}",
                                        f"/opt/bunkerweb/plugins/{folder_name}",
                                    )
                        except tarfile.ReadError:
                            error = 1
                            flash(
                                f"Couldn't read file {file} ({folder_name if folder_name else temp_folder_name})",
                                "error",
                            )
                        except tarfile.CompressionError:
                            error = 1
                            flash(
                                f"{file} is not a valid tar file ({folder_name if folder_name else temp_folder_name})",
                                "error",
                            )
                        except tarfile.HeaderError:
                            error = 1
                            flash(
                                f"The file plugin.json in {file} is not valid ({folder_name if folder_name else temp_folder_name})",
                                "error",
                            )
                except KeyError:
                    error = 1
                    flash(
                        f"{file} is not a valid plugin (plugin.json file is missing) ({folder_name if folder_name else temp_folder_name})",
                        "error",
                    )
                except JSONDecodeError as e:
                    error = 1
                    flash(
                        f"The file plugin.json in {file} is not valid ({e.msg}: line {e.lineno} column {e.colno} (char {e.pos})) ({folder_name if folder_name else temp_folder_name})",
                        "error",
                    )
                except ValueError:
                    error = 1
                    flash(
                        f"The file plugin.json is missing one or more of the following keys: <i>{', '.join(PLUGIN_KEYS)}</i> ({folder_name if folder_name else temp_folder_name})",
                        "error",
                    )
                except FileExistsError:
                    error = 1
                    flash(
                        f"A plugin named {folder_name} already exists",
                        "error",
                    )
                except (tarfile.TarError, OSError) as e:
                    error = 1
                    flash(f"{e}", "error")
                except Exception:
                    pass
                finally:
                    if error != 1:
                        flash(
                            f"Successfully created plugin: <b><i>{folder_name}</i></b>"
                        )

                    error = 0

            # Fix permissions for plugins folders
            for root, dirs, files in os.walk("/opt/bunkerweb/plugins", topdown=False):
                for name in files + dirs:
                    chown(os.path.join(root, name), "nginx", "nginx")
                    os.chmod(os.path.join(root, name), 0o770)

        if operation:
            flash(operation)

        # Reload instances
        app.config["RELOADING"] = True
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("plugins",),
        ).start()

        # Remove tmp folder
        if os.path.exists("/opt/bunkerweb/tmp/ui"):
            try:
                rmtree("/opt/bunkerweb/tmp/ui")
            except OSError:
                pass

        app.config["CONFIG"].reload_plugins()
        return redirect(
            url_for("loading", next=url_for("plugins"), message="Reloading plugins")
        )

    # Initialize plugins tree
    plugins = [
        {
            "name": "plugins",
            "type": "folder",
            "path": "/opt/bunkerweb/plugins",
            "can_create_files": False,
            "can_create_folders": False,
            "can_edit": False,
            "can_delete": False,
            "children": [
                {
                    "name": _dir,
                    "type": "folder",
                    "path": f"/opt/bunkerweb/plugins/{_dir}",
                    "can_create_files": False,
                    "can_create_folders": False,
                    "can_edit": False,
                    "can_delete": True,
                }
                for _dir in os.listdir("/opt/bunkerweb/plugins")
            ],
        }
    ]
    # Populate plugins tree
    plugins_pages = app.config["CONFIG"].get_plugins_pages()

    pages = []
    active = True
    for page in plugins_pages:
        with open(
            f"/opt/bunkerweb/"
            + (
                "plugins"
                if os.path.exists(
                    f"/opt/bunkerweb/plugins/{page.lower()}/ui/template.html"
                )
                else "core"
            )
            + f"/{page.lower()}/ui/template.html",
            "r",
        ) as f:
            # Convert the file content to a jinja2 template
            template = Template(f.read())

        pages.append(
            {
                "id": page.lower().replace(" ", "-"),
                "name": page,
                # Render the template with the plugin's data if it corresponds to the last submitted form else with the default data
                "content": template.render(csrf_token=generate_csrf, url_for=url_for)
                if app.config["PLUGIN_ARGS"] is None
                or app.config["PLUGIN_ARGS"]["plugin"] != page.lower()
                else template.render(
                    csrf_token=generate_csrf,
                    url_for=url_for,
                    **app.config["PLUGIN_ARGS"]["args"],
                ),
                # Only the first plugin page is active
                "active": active,
            }
        )
        active = False

    app.config["PLUGIN_ARGS"] = None

    return render_template("plugins.html", folders=plugins, pages=pages)


@app.route("/plugins/upload", methods=["POST"])
@login_required
def upload_plugin():
    if not request.files:
        return {"status": "ko"}, 400

    if not os.path.exists("/opt/bunkerweb/tmp/ui"):
        os.mkdir("/opt/bunkerweb/tmp/ui")

    for file in request.files.values():
        if not file.filename.endswith((".zip", ".tar.gz", ".tar.xz")):
            return {"status": "ko"}, 422

        with open(
            f"/opt/bunkerweb/tmp/ui/{uuid4()}{file.filename[file.filename.index('.'):]}",
            "wb",
        ) as f:
            f.write(file.read())

    return {"status": "ok"}, 201


@app.route("/plugins/<plugin>", methods=["GET", "POST"])
@login_required
def custom_plugin(plugin):
    if not re_match(r"^[a-zA-Z0-9_-]{1,64}$", plugin):
        flash(
            f"Invalid plugin id, <b>{plugin}</b> (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)",
            "error",
        )
        return redirect(url_for("loading", next=url_for("plugins")))

    if not os.path.exists(
        f"/opt/bunkerweb/plugins/{plugin}/ui/actions.py"
    ) and not os.path.exists(f"/opt/bunkerweb/core/{plugin}/ui/actions.py"):
        flash(
            f"The <i>actions.py</i> file for the plugin <b>{plugin}</b> does not exist",
            "error",
        )
        return redirect(url_for("loading", next=url_for("plugins")))

    # Add the custom plugin to sys.path
    sys_path.append(
        f"/opt/bunkerweb/"
        + (
            "plugins"
            if os.path.exists(f"/opt/bunkerweb/plugins/{plugin}/ui/actions.py")
            else "core"
        )
        + f"/{plugin}/ui/"
    )
    try:
        # Try to import the custom plugin
        import actions
    except:
        flash(
            f"An error occurred while importing the plugin <b>{plugin}</b>:<br/>{format_exc()}",
            "error",
        )
        return redirect(url_for("loading", next=url_for("plugins")))

    error = False
    res = None

    try:
        # Try to get the custom plugin custom function and call it
        method = getattr(actions, plugin)
        res = method()
    except AttributeError:
        flash(
            f"The plugin <b>{plugin}</b> does not have a <i>{plugin}</i> method",
            "error",
        )
        error = True
        return redirect(url_for("loading", next=url_for("plugins")))
    except:
        flash(
            f"An error occurred while executing the plugin <b>{plugin}</b>:<br/>{format_exc()}",
            "error",
        )
        error = True
    finally:
        # Remove the custom plugin from the shared library
        sys_path.pop()
        del sys_modules["actions"]
        del actions

        if (
            request.method != "POST"
            or error is True
            or res is None
            or isinstance(res, dict) is False
        ):
            return redirect(url_for("loading", next=url_for("plugins")))

    app.config["PLUGIN_ARGS"] = {"plugin": plugin, "args": res}

    flash(f"Your action <b>{plugin}</b> has been executed")
    return redirect(url_for("loading", next=url_for("plugins")))


@app.route("/cache", methods=["GET"])
@login_required
def cache():
    return render_template(
        "cache.html", folders=[path_to_dict("/opt/bunkerweb/cache", is_cache=True)]
    )


@app.route("/cache/download", methods=["GET"])
@login_required
def cache_download():
    path = request.args.get("path")

    if not path:
        return redirect(url_for("loading", next=url_for("cache"))), 400

    operation = app.config["CONFIGFILES"].check_path(path, "/opt/bunkerweb/cache/")

    if operation:
        flash(operation, "error")
        return redirect(url_for("loading", next=url_for("plugins"))), 500

    return send_file(path, as_attachment=True)


@app.route("/logs", methods=["GET"])
@login_required
def logs():
    instances = app.config["INSTANCES"].get_instances()
    first_instance = instances[0] if instances else None

    return render_template(
        "logs.html", first_instance=first_instance, instances=instances
    )


@app.route("/logs/local", methods=["GET"])
@login_required
def logs_linux():
    if not os.path.exists("/usr/sbin/nginx"):
        return (
            jsonify(
                {
                    "status": "ko",
                    "message": "There are no linux instances running",
                }
            ),
            404,
        )

    last_update = request.args.get("last_update")
    raw_logs_access = []
    raw_logs_error = []

    if last_update:
        if os.path.exists("/var/log/nginx/error.log"):
            with open("/var/log/nginx/error.log", "r") as f:
                raw_logs_error = f.read().splitlines()[int(last_update.split(".")[0]) :]

        if os.path.exists("/var/log/nginx/access.log"):
            with open("/var/log/nginx/access.log", "r") as f:
                raw_logs_access = f.read().splitlines()[
                    int(last_update.split(".")[1]) :
                ]

    else:
        if os.path.exists("/var/log/nginx/error.log"):
            with open("/var/log/nginx/error.log", "r") as f:
                raw_logs_error = f.read().splitlines()

        if os.path.exists("/var/log/nginx/access.log"):
            with open("/var/log/nginx/access.log", "r") as f:
                raw_logs_access = f.read().splitlines()

    logs_error = []
    temp_multiple_lines = []
    NGINX_LOG_LEVELS = [
        "debug",
        "notice",
        "info",
        "warn",
        "error",
        "crit",
        "alert",
        "emerg",
    ]
    for line in raw_logs_error:
        line_lower = line.lower()

        if "[info]" in line.lower() and line.endswith(":") or "[error]" in line.lower():
            if temp_multiple_lines:
                logs_error.append("\n".join(temp_multiple_lines))

            temp_multiple_lines = [
                f"{datetime.strptime(' '.join(line.strip().split(' ')[0:2]), '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()} {line}"
            ]
        elif (
            all(f"[{log_level}]" not in line_lower for log_level in NGINX_LOG_LEVELS)
            and temp_multiple_lines
        ):
            temp_multiple_lines.append(line)
        else:
            logs_error.append(
                f"{datetime.strptime(' '.join(line.strip().split(' ')[0:2]), '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()} {line}"
            )

    if temp_multiple_lines:
        logs_error.append("\n".join(temp_multiple_lines))

    logs_access = [
        f"{datetime.strptime(line[line.find('[') + 1: line.find(']')], '%d/%b/%Y:%H:%M:%S %z').timestamp()} {line}"
        for line in raw_logs_access
    ]
    raw_logs = logs_error + logs_access
    raw_logs.sort(
        key=lambda x: float(x.split(" ")[0]) if x.split(" ")[0].isdigit() else 0
    )

    logs = []
    for log in raw_logs:
        log_lower = log.lower()
        error_type = (
            "error"
            if "[error]" in log_lower
            or "[crit]" in log_lower
            or "[alert]" in log_lower
            or "❌" in log_lower
            else (
                "warn"
                if "[warn]" in log_lower
                else ("info" if "[info]" in log_lower else "message")
            )
        )

        if "\n" in log:
            splitted_one_line = log.split("\n")
            logs.append(
                {
                    "content": " ".join(
                        splitted_one_line.pop(0).strip().split(" ")[1:]
                    ),
                    "type": error_type,
                    "separator": True,
                }
            )

            for splitted_log in splitted_one_line:
                logs.append(
                    {
                        "content": splitted_log,
                        "type": error_type,
                    }
                )
        else:
            logs.append(
                {
                    "content": " ".join(log.strip().split(" ")[1:]),
                    "type": error_type,
                }
            )

    count_error_logs = 0
    for log in logs_error:
        if "\n" in log:
            for _ in log.split("\n"):
                count_error_logs += 1
        else:
            count_error_logs += 1

    return jsonify(
        {
            "logs": logs,
            "last_update": f"{count_error_logs + int(last_update.split('.')[0])}.{len(logs_access) + int(last_update.split('.')[1])}"
            if last_update
            else f"{count_error_logs}.{len(logs_access)}",
        }
    )


@app.route("/logs/<container_id>", methods=["GET"])
@login_required
def logs_container(container_id):
    last_update = request.args.get("last_update")
    logs = []
    if docker_client:
        try:
            if last_update:
                if not last_update.isdigit():
                    return (
                        jsonify(
                            {
                                "status": "ko",
                                "message": "last_update must be an integer",
                            }
                        ),
                        422,
                    )

                docker_logs = docker_client.containers.get(container_id).logs(
                    stdout=True,
                    stderr=True,
                    since=datetime.fromtimestamp(int(last_update)),
                )
            else:
                docker_logs = docker_client.containers.get(container_id).logs(
                    stdout=True,
                    stderr=True,
                )

            for log in docker_logs.decode("utf-8", errors="replace").split("\n")[0:-1]:
                log_lower = log.lower()
                logs.append(
                    {
                        "content": log,
                        "type": "error"
                        if "[error]" in log_lower
                        or "[crit]" in log_lower
                        or "[alert]" in log_lower
                        or "❌" in log_lower
                        else (
                            "warn"
                            if "[warn]" in log_lower
                            else ("info" if "[info]" in log_lower else "message")
                        ),
                    }
                )
        except docker_NotFound:
            return (
                jsonify(
                    {
                        "status": "ko",
                        "message": f"Container with ID {container_id} not found!",
                    }
                ),
                404,
            )

    return jsonify({"logs": logs, "last_update": int(time())})


@app.route("/login", methods=["GET", "POST"])
def login():
    fail = False
    if (
        request.method == "POST"
        and "username" in request.form
        and "password" in request.form
    ):
        if app.config["USER"].get_id() == request.form["username"] and app.config[
            "USER"
        ].check_password(request.form["password"]):
            # log the user in
            next_url = request.form.get("next")
            login_user(app.config["USER"])

            # redirect him to the page he originally wanted or to the home page
            return redirect(url_for("loading", next=next_url or url_for("home")))
        else:
            fail = True

    if fail:
        return (
            render_template("login.html", error="Invalid username or password"),
            401,
        )
    return render_template("login.html")


@app.route("/check_reloading")
@login_required
def check_reloading():
    if app.config["RELOADING"] is False:
        for f in app.config["TO_FLASH"]:
            if f["type"] == "error":
                flash(f["content"], "error")
            else:
                flash(f["content"])

        app.config["TO_FLASH"].clear()

    return jsonify({"reloading": app.config["RELOADING"]})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))
