from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from secrets import token_urlsafe
from signal import SIGINT, SIGTERM, signal
from subprocess import PIPE, Popen, call
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), 
                               ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from flask import Flask, render_template, request

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from app.models.reverse_proxied import ReverseProxied

# Initialize bw_logger module
logger = bwlog(
    title="UI-TMP: ",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for TMP-UI")
    logger.debug(f"Added dependency paths: {[join(sep, 'usr', 'share', 'bunkerweb', *paths) for paths in (('deps', 'python'), ('utils',), ('api',), ('db',))]}")

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
ERROR_FILE = TMP_DIR.joinpath("ui.error")

if DEBUG_MODE:
    logger.debug(f"TMP_DIR set to: {TMP_DIR}")
    logger.debug(f"ERROR_FILE set to: {ERROR_FILE}")


# Stop the temporary UI process gracefully by finding and terminating
# the gunicorn process
def stop(status):
    if DEBUG_MODE:
        logger.debug(f"stop() called with status: {status}")
    
    pid_file = Path(sep, "var", "run", "bunkerweb", "tmp-ui.pid")
    
    if DEBUG_MODE:
        logger.debug(f"Looking for PID file: {pid_file}")
    
    if pid_file.is_file():
        pid = pid_file.read_bytes()
        if DEBUG_MODE:
            logger.debug(f"Found PID in file: {pid}")
    else:
        if DEBUG_MODE:
            logger.debug("PID file not found, using pgrep to find gunicorn")
        p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
        pid, _ = p.communicate()
        if DEBUG_MODE:
            logger.debug(f"Found PID via pgrep: {pid}")
    
    target_pid = pid.strip().decode().split("\n")[0]
    if DEBUG_MODE:
        logger.debug(f"Sending SIGTERM to PID: {target_pid}")
    
    call(["kill", "-SIGTERM", target_pid])
    _exit(status)


# Handle stop signals (SIGINT, SIGTERM) and perform graceful shutdown
def handle_stop(signum, frame):
    if DEBUG_MODE:
        logger.debug(f"handle_stop() called with signal: {signum}")
    
    logger.info("Caught stop operation")
    logger.info("Stopping web ui ...")
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)

app = Flask(__name__, static_url_path="/", static_folder="app/static", 
            template_folder="app/templates")
app.url_map.strict_slashes = False

if DEBUG_MODE:
    logger.debug("Flask app created with static and template folders")

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    
    if DEBUG_MODE:
        logger.debug(f"PROXY_NUMBERS set to: {PROXY_NUMBERS}")
    
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, 
                                  x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, 
                                  x_prefix=PROXY_NUMBERS)

    app.config["ENV"] = {}
    app.config["SCRIPT_NONCE"] = ""
    
    if DEBUG_MODE:
        logger.debug("App configuration initialized")


# Generate a new script nonce for each request to enhance security
@app.before_request
def before_request():
    if DEBUG_MODE:
        logger.debug("before_request() - generating new script nonce")
    
    app.config["SCRIPT_NONCE"] = token_urlsafe(32)
    
    if DEBUG_MODE:
        logger.debug(f"Generated script nonce: {app.config['SCRIPT_NONCE']}")


# Inject common variables into all template contexts
@app.context_processor
def inject_variables():
    if DEBUG_MODE:
        logger.debug("inject_variables() - adding context variables")
        logger.debug(f"Current endpoint: {request.path.split('/')[-1]}")
        logger.debug(f"Script nonce: {app.config['SCRIPT_NONCE']}")
    
    return dict(
        current_endpoint=request.path.split("/")[-1],
        script_nonce=app.config["SCRIPT_NONCE"],
    )


# Set security headers on all responses to protect against common attacks
@app.after_request
def set_security_headers(response):
    if DEBUG_MODE:
        logger.debug("set_security_headers() - applying security headers")
    
    # Content-Security-Policy header to prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src 'self'"
        + f" script-src https: http: 'self' 'nonce-{app.config['SCRIPT_NONCE']}' 'strict-dynamic' 'unsafe-inline';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: blob: https://assets.bunkerity.com;"
        + " base-uri 'self';"
        + " block-all-mixed-content;"
    )

    # X-Frames-Options header to prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # X-Content-Type-Options header to prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Referrer-Policy header to prevent leaking of sensitive data
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if DEBUG_MODE:
        logger.debug("Security headers applied to response")

    return response


# Handle 404 errors by showing a starting page with optional error info
@app.errorhandler(404)
def not_found_handler(error):
    if DEBUG_MODE:
        logger.debug(f"not_found_handler() called with error: {error}")
    
    message = "BunkerWeb UI is starting..."
    error_content = ""
    
    if ERROR_FILE.is_file():
        message = "BunkerWeb UI encountered an error while starting."
        error_content = ERROR_FILE.read_text()
        
        if DEBUG_MODE:
            logger.debug(f"Error file found, content: {error_content}")
    elif DEBUG_MODE:
        logger.debug("No error file found, showing starting message")
    
    return render_template("starting.html", message=message, 
                          error=error_content)


# Catch all routes and show starting page with optional error information
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    if DEBUG_MODE:
        logger.debug(f"catch_all() called with path: {path}")
    
    message = "BunkerWeb UI is starting..."
    error_content = ""
    
    if ERROR_FILE.is_file():
        message = "BunkerWeb UI encountered an error while starting."
        error_content = ERROR_FILE.read_text()
        
        if DEBUG_MODE:
            logger.debug(f"Error file found, content: {error_content}")
    elif DEBUG_MODE:
        logger.debug("No error file found, showing starting message")
    
    return render_template("starting.html", message=message, 
                          error=error_content)
