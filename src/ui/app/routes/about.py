from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-about",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-about")

from flask import Blueprint, render_template
from flask_login import login_required


about = Blueprint("about", __name__)


# Display the about page with BunkerWeb project information.
# Provides project details, version info, and acknowledgments.
@about.route("/about")
@login_required
def about_page():
    logger.debug("about_page() called")
    return render_template("about.html")