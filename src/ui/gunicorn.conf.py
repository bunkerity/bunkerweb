from contextlib import suppress
from hashlib import sha256
from json import JSONDecodeError, dumps, loads
from os import cpu_count, getenv, getpid, sep, urandom
from os.path import join
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from threading import Lock
from regex import compile as re_compile
from sys import path as sys_path
from time import sleep

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore

from src.User import User

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
RUN_DIR = Path(sep, "var", "run", "bunkerweb")

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("LOG_LEVEL", "info")

wsgi_app = "main:app"
proc_name = "bunkerweb-ui"
accesslog = "/var/log/bunkerweb/ui-access.log"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
errorlog = "/var/log/bunkerweb/ui.log"
reuse_port = True
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "ui")
secure_scheme_headers = {}
workers = MAX_WORKERS
worker_class = "gthread"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 30

DEBUG = getenv("DEBUG", False)

loglevel = "debug" if DEBUG else LOG_LEVEL.lower()

if DEBUG:
    reload = True
    reload_extra_files = [file.as_posix() for file in Path(sep, "usr", "share", "bunkerweb", "ui", "templates").iterdir()]

LOCK = Lock()


def on_starting(server):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if not getenv("FLASK_SECRET") and not TMP_DIR.joinpath(".flask_secret").is_file():
        TMP_DIR.joinpath(".flask_secret").write_text(sha256(urandom(32)).hexdigest(), encoding="utf-8")

    LOGGER = setup_logger("UI")

    db = Database(LOGGER, ui=True)

    ready = False
    while not ready:
        db_metadata = db.get_metadata()
        if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
            LOGGER.warning("Database is not initialized, retrying in 5s ...")
        else:
            ready = True
            continue
        sleep(5)

    USER_PASSWORD_RX = re_compile(r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,./:;<=>?@[\\\]^_`{|}~-]).{8,}$")

    USER = "Error"
    while USER == "Error":
        with suppress(Exception):
            USER = db.get_ui_user()

    if USER:
        USER = User(**USER)

        if getenv("ADMIN_USERNAME") or getenv("ADMIN_PASSWORD"):
            override_admin_creds = getenv("OVERRIDE_ADMIN_CREDS", "no").lower() == "yes"
            if USER.method == "manual" or override_admin_creds:
                updated = False
                if getenv("ADMIN_USERNAME", "") and USER.get_id() != getenv("ADMIN_USERNAME", ""):
                    USER.id = getenv("ADMIN_USERNAME", "")
                    updated = True
                if getenv("ADMIN_PASSWORD", "") and not USER.check_password(getenv("ADMIN_PASSWORD", "")):
                    if not USER_PASSWORD_RX.match(getenv("ADMIN_PASSWORD", "")):
                        LOGGER.warning(
                            "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-). It will not be updated."
                        )
                    else:
                        USER.update_password(getenv("ADMIN_PASSWORD", ""))
                        updated = True

                if updated:
                    if override_admin_creds:
                        LOGGER.warning("Overriding the admin user credentials, as the OVERRIDE_ADMIN_CREDS environment variable is set to 'yes'.")
                    err = db.update_ui_user(USER.get_id(), USER.password_hash, USER.is_two_factor_enabled, USER.secret_token, method="manual")
                    if err:
                        LOGGER.error(f"Couldn't update the admin user in the database: {err}")
                    else:
                        LOGGER.info("The admin user was updated successfully")
            else:
                LOGGER.warning("The admin user wasn't created manually. You can't change it from the environment variables.")
    elif getenv("ADMIN_USERNAME") and getenv("ADMIN_PASSWORD"):
        if not getenv("FLASK_DEBUG", False):
            if len(getenv("ADMIN_USERNAME", "admin")) > 256:
                LOGGER.error("The admin username is too long. It must be less than 256 characters.")
                exit(1)
            elif not USER_PASSWORD_RX.match(getenv("ADMIN_PASSWORD", "changeme")):
                LOGGER.error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
                )
                exit(1)

        user_name = getenv("ADMIN_USERNAME", "admin")
        USER = User(user_name, getenv("ADMIN_PASSWORD", "changeme"))
        ret = db.create_ui_user(user_name, USER.password_hash)

        if ret:
            LOGGER.error(f"Couldn't create the admin user in the database: {ret}")
            exit(1)

    LOGGER.info("UI is ready")


def handle_stop(signum=None, frame=None):
    if not TMP_DIR.joinpath(".ui.json").is_file():
        return

    ui_data = "Error"
    while ui_data == "Error":
        with suppress(JSONDecodeError):
            ui_data = loads(TMP_DIR.joinpath(".ui.json").read_text(encoding="utf-8"))

    ui_data["SERVER_STOPPING"] = True

    with LOCK:
        TMP_DIR.joinpath(".ui.json").write_text(dumps(ui_data), encoding="utf-8")


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


def on_reload(server):
    handle_stop()


def when_ready(server):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.joinpath("ui.pid").write_text(str(getpid()), encoding="utf-8")
    TMP_DIR.joinpath("ui.healthy").write_text("ok", encoding="utf-8")


def on_exit(server):
    RUN_DIR.joinpath("ui.pid").unlink(missing_ok=True)
    TMP_DIR.joinpath("ui.healthy").unlink(missing_ok=True)
    TMP_DIR.joinpath(".flask_secret").unlink(missing_ok=True)
    TMP_DIR.joinpath(".ui.json").unlink(missing_ok=True)
