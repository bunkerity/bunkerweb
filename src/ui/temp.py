from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from secrets import token_urlsafe
from signal import SIGINT, SIGTERM, signal
from subprocess import PIPE, Popen, call
from sys import path as sys_path


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from flask import Flask, render_template, request

from logger import getLogger  # type: ignore

from app.models.reverse_proxied import ReverseProxied

LOGGER = getLogger("TMP-UI")

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
ERROR_FILE = TMP_DIR.joinpath("ui.error")


def stop(status):
    pid_file = Path(sep, "var", "run", "bunkerweb", "tmp-ui.pid")
    if pid_file.is_file():
        pid = pid_file.read_bytes()
    else:
        p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
        pid, _ = p.communicate()
    call(["kill", "-SIGTERM", pid.strip().decode().split("\n")[0]])
    _exit(status)


def handle_stop(signum, frame):
    LOGGER.info("Caught stop operation")
    LOGGER.info("Stopping web ui ...")
    stop(0, False)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)

app = Flask(__name__, static_url_path="/", static_folder="app/static", template_folder="app/templates")
app.url_map.strict_slashes = False

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)

    app.config["ENV"] = {}
    app.config["SCRIPT_NONCE"] = ""


@app.before_request
def before_request():
    app.config["SCRIPT_NONCE"] = token_urlsafe(32)


@app.context_processor
def inject_variables():
    return dict(
        current_endpoint=request.path.split("/")[-1],
        script_nonce=app.config["SCRIPT_NONCE"],
    )


@app.after_request
def set_security_headers(response):
    """Set the security headers."""
    # * Content-Security-Policy header to prevent XSS attacks
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

    # * X-Frames-Options header to prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # * X-Content-Type-Options header to prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # * Referrer-Policy header to prevent leaking of sensitive data
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


@app.errorhandler(404)
def not_found_handler(error):
    message = "BunkerWeb UI is starting..."
    error = ""
    if ERROR_FILE.is_file():
        message = "BunkerWeb UI encountered an error while starting."
        error = ERROR_FILE.read_text()
    return render_template("starting.html", message=message, error=error)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    message = "BunkerWeb UI is starting..."
    error = ""
    if ERROR_FILE.is_file():
        message = "BunkerWeb UI encountered an error while starting."
        error = ERROR_FILE.read_text()
    return render_template("starting.html", message=message, error=error)
