from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from flask import Blueprint, render_template
from flask_login import login_required

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for about module")

about = Blueprint("about", __name__)


# Render the about page template for displaying BunkerWeb information.
# Provides system information, version details, and documentation 
# links to authenticated users.
@about.route("/about")
@login_required
def about_page():
    if DEBUG_MODE:
        logger.debug("about_page() called - rendering about page")
    
    if DEBUG_MODE:
        logger.debug("Successfully rendered about.html template")
    
    return render_template("about.html")