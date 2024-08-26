from flask import Blueprint, render_template
from flask_login import login_required


from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS  # , DB

home = Blueprint("home", __name__)


@home.route("/home")
@login_required
def home_page():
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
    # try:
    #     r = get("https://github.com/bunkerity/bunkerweb/releases/latest", allow_redirects=True, timeout=5)
    #     r.raise_for_status()
    # except BaseException:
    #     r = None
    # remote_version = None

    # if r and r.status_code == 200:
    #     remote_version = basename(r.url).strip().replace("v", "")

    config = BW_CONFIG.get_config(with_drafts=True, filtered_settings=("SERVER_NAME",))
    instances = BW_INSTANCES_UTILS.get_instances()

    instance_health_count = 0

    for instance in instances:
        if instance.status == "up":
            instance_health_count += 1

    services = 0
    services_scheduler_count = 0
    services_ui_count = 0
    services_autoconf_count = 0

    for service in config["SERVER_NAME"]["value"].split(" "):
        service_method = config.get(f"{service}_SERVER_NAME", {"method": "scheduler"})["method"]

        if service_method == "scheduler":
            services_scheduler_count += 1
        elif service_method == "ui":
            services_ui_count += 1
        elif service_method == "autoconf":
            services_autoconf_count += 1
        services += 1

    # metadata = DB.get_metadata()

    # data = {
    #     "check_version": not remote_version or get_version() == remote_version,
    #     "remote_version": remote_version,
    #     "version": metadata["version"],
    #     "instances_number": len(instances),
    #     "services_number": services,
    #     "instance_health_count": instance_health_count,
    #     "services_scheduler_count": services_scheduler_count,
    #     "services_ui_count": services_ui_count,
    #     "services_autoconf_count": services_autoconf_count,
    #     "is_pro_version": metadata["is_pro"],
    #     "pro_status": metadata["pro_status"],
    #     "pro_services": metadata["pro_services"],
    #     "pro_overlapped": metadata["pro_overlapped"],
    #     "plugins_number": len(BW_CONFIG.get_plugins()),
    #     "plugins_errors": DB.get_plugins_errors(),
    # }

    # builder = home_builder(data)
    # return render_template("home.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
    return render_template("home.html")  # TODO
