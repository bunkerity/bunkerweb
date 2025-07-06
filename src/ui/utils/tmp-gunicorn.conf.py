from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import handle_docker_secrets  # type: ignore

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title=__name__,
    log_file_path="/var/log/bunkerweb/scheduler.log"
)

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
TMP_UI_DIR = TMP_DIR.joinpath("ui")
RUN_DIR = Path(sep, "var", "run", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

HEALTH_FILE = TMP_DIR.joinpath("tmp-ui.healthy")
PID_FILE = RUN_DIR.joinpath("tmp-ui.pid")

LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "info"))
LISTEN_ADDR = getenv("LISTEN_ADDR", "0.0.0.0")
LISTEN_PORT = getenv("LISTEN_PORT", "7000")
FORWARDED_ALLOW_IPS = getenv("FORWARDED_ALLOW_IPS", "*")
CAPTURE_OUTPUT = getenv("CAPTURE_OUTPUT", "no").lower() == "yes"

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"
DEBUG = getenv("DEBUG", False)

if DEBUG_MODE:
    logger.debug("Debug mode enabled for tmp-gunicorn.conf.py")
    logger.debug(f"Configuration loaded - LISTEN_ADDR: {LISTEN_ADDR}, "
                 f"LISTEN_PORT: {LISTEN_PORT}")

wsgi_app = "temp:app"
proc_name = "bunkerweb-tmp-ui"
accesslog = (join(sep, "var", "log", "bunkerweb", "tmp-ui-access.log") 
             if CAPTURE_OUTPUT else "-")
access_log_format = ('%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" '
                    '%(s)s %(b)s "%(f)s" "%(a)s"')
errorlog = (join(sep, "var", "log", "bunkerweb", "tmp-ui.log") 
            if CAPTURE_OUTPUT else "-")
capture_output = CAPTURE_OUTPUT
limit_request_line = 0
limit_request_fields = 32768
limit_request_field_size = 0
reuse_port = True
daemon = True
chdir = join(sep, "usr", "share", "bunkerweb", "ui")
umask = 0x027
pidfile = PID_FILE.as_posix()
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = TMP_UI_DIR.as_posix()
secure_scheme_headers = {}
forwarded_allow_ips = FORWARDED_ALLOW_IPS
pythonpath = (join(sep, "usr", "share", "bunkerweb", "deps", "python") + 
              "," + join(sep, "usr", "share", "bunkerweb", "ui"))
proxy_allow_ips = "*"
casefold_http_method = True
workers = 1
bind = f"{LISTEN_ADDR}:{LISTEN_PORT}"
worker_class = "sync"
threads = 2
max_requests_jitter = 0
graceful_timeout = 0

loglevel = "debug" if DEBUG else LOG_LEVEL.lower()

if DEBUG:
    reload = True
    reload_extra_files = [
        file.as_posix()
        for file in Path(sep, "usr", "share", "bunkerweb", "ui", 
                        "app").rglob("*")
        if "__pycache__" not in file.parts and "static" not in file.parts
    ]


# Initialize gunicorn server and prepare required directories.
# Handles Docker secrets loading and sets up logging for the temporary UI
# server startup process.
def on_starting(server):
    if DEBUG_MODE:
        logger.debug("on_starting() called")
    
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    TMP_UI_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    if DEBUG_MODE:
        logger.debug(f"Created directories: {TMP_DIR}, {TMP_UI_DIR}, "
                     f"{RUN_DIR}, {LIB_DIR}")

    # Handle Docker secrets first
    docker_secrets = handle_docker_secrets()
    if docker_secrets:
        environ.update(docker_secrets)
        if DEBUG_MODE:
            logger.debug(f"Updated environment with "
                        f"{len(docker_secrets)} Docker secrets")

    if DEBUG_MODE:
        logger.debug(f"Server configuration: workers={workers}, "
                     f"bind={bind}, worker_class={worker_class}")

    if docker_secrets:
        logger.info(f"Loaded {len(docker_secrets)} Docker secrets")

    logger.info("TMP-UI is ready")

    if DEBUG_MODE:
        logger.debug("on_starting() completed successfully")


# Signal that the server is ready to accept connections.
# Creates the health check file that external monitoring systems
# can use to verify the server is operational.
def when_ready(server):
    if DEBUG_MODE:
        logger.debug("when_ready() called")
    
    HEALTH_FILE.write_text("ok", encoding="utf-8")
    
    if DEBUG_MODE:
        logger.debug(f"Created health file: {HEALTH_FILE}")


# Clean up resources when the server is shutting down.
# Removes the health check file to indicate the server is no longer
# available for handling requests.
def on_exit(server):
    if DEBUG_MODE:
        logger.debug("on_exit() called")
    
    HEALTH_FILE.unlink(missing_ok=True)
    
    if DEBUG_MODE:
        logger.debug(f"Removed health file: {HEALTH_FILE}")