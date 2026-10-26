from platform import platform, python_implementation, python_version

from flask import Blueprint, render_template
from flask_login import login_required

from common_utils import get_integration  # type: ignore

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT, DATA
from app.models.changelog import load
from app.utils import human_readable_number

about = Blueprint("about", __name__)

# How many bundled releases the About page previews before pointing at /whats-new.
RELEASE_PREVIEW = 3


def _environment():
    """Allow-listed facts only (the same ones the owner support bundle carries): never an environment
    variable, a license key or a database URI. Split by where each fact was read, because the UI host,
    the control plane and the instances are three different machines."""
    try:
        metadata = API_CLIENT.get_metadata()
    except (ApiClientError, ApiUnavailableError):
        metadata = {}
    try:
        instances = API_CLIENT.get_instances()
    except (ApiClientError, ApiUnavailableError):
        instances = None
    return {
        "ui_host": {
            "integration": get_integration(),
            "python": f"{python_version()} ({python_implementation()})",
            "platform": platform(),
        },
        "control_plane": {
            "version": metadata.get("version"),
            "database": metadata.get("database_version"),
        },
        "instances": (
            None
            if instances is None
            else {
                "total": len(instances),
                "up": sum(1 for instance in instances if (instance.get("status") if isinstance(instance, dict) else getattr(instance, "status", None)) == "up"),
            }
        ),
    }


@about.route("/about")
@login_required
def about_page():
    # Refreshed hourly in the background (main.py `update_github_metadata`), never on this
    # request: the page must render at the same speed whether or not GitHub is reachable. The
    # sidebar footer reads the same value through the context processor in routes/home.py.
    stars = DATA.get("GITHUB_STARS")
    return render_template(
        "about.html",
        github_stars=human_readable_number(stars) if stars else None,
        releases=load()[:RELEASE_PREVIEW],
        environment=_environment(),
    )
