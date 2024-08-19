from json import JSONDecodeError, dumps, loads
from os import cpu_count, getenv, getpid, sep
from os.path import join
from pathlib import Path
from random import randint
from secrets import token_urlsafe
from sys import exit, path as sys_path
from time import sleep


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from passlib import totp

from common_utils import get_version  # type: ignore
from logger import setup_logger  # type: ignore

from ui_database import UIDatabase
from utils import USER_PASSWORD_RX, check_password, gen_password_hash

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
RUN_DIR = Path(sep, "var", "run", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "info"))

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
    reload_extra_files = [file.as_posix() for file in Path(sep, "usr", "share", "bunkerweb", "ui", "pages").glob("*.py")]


def on_starting(server):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    LOGGER = setup_logger("UI", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

    FLASK_SECRET = getenv("FLASK_SECRET")
    if not FLASK_SECRET and not TMP_DIR.joinpath(".flask_secret").is_file():
        LOGGER.warning("The FLASK_SECRET environment variable is missing, generating a random one ...")
        TMP_DIR.joinpath(".flask_secret").write_text(token_urlsafe(32), encoding="utf-8")

    TOTP_SECRETS = getenv("TOTP_SECRETS", "")
    if TOTP_SECRETS:
        try:
            TOTP_SECRETS = loads(TOTP_SECRETS)
        except JSONDecodeError:
            x = 1
            tmp_secrets = {}
            for secret in TOTP_SECRETS.strip().split(" "):
                if secret:
                    tmp_secrets[x] = secret
                    x += 1
            TOTP_SECRETS = tmp_secrets.copy()
            del tmp_secrets

    if not TOTP_SECRETS:
        LOGGER.warning("The TOTP_SECRETS environment variable is missing, generating a random one ...")
        LIB_DIR.joinpath(".totp_secrets.json").write_text(dumps({k: totp.generate_secret() for k in range(randint(1, 5))}), encoding="utf-8")

    DB = UIDatabase(LOGGER)

    ready = False
    while not ready:
        db_metadata = DB.get_metadata()
        if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
            LOGGER.warning("Database is not initialized, retrying in 5s ...")
        else:
            ready = True
            continue
        sleep(5)

    BW_VERSION = get_version()

    ret, err = DB.init_ui_tables(BW_VERSION)

    if not ret and err:
        LOGGER.error(f"Exception while checking database tables : {err}")
        exit(1)
    elif not ret:
        LOGGER.info("Database ui tables didn't change, skipping update ...")
    else:
        LOGGER.info("Database ui tables successfully updated")

    if not DB.get_ui_roles(as_dict=True):
        ret = DB.create_ui_role("admin", "Admin can create account, manager software and read data.", ["manage", "write", "read"])
        if ret:
            LOGGER.error(f"Couldn't create the admin role in the database: {ret}")
            exit(1)

        ret = DB.create_ui_role("writer", "Write can manage software and read data but can't create account.", ["write", "read"])
        if ret:
            LOGGER.error(f"Couldn't create the admin role in the database: {ret}")
            exit(1)

        ret = DB.create_ui_role("reader", "Reader can read data but can't proceed to any actions.", ["read"])
        if ret:
            LOGGER.error(f"Couldn't create the admin role in the database: {ret}")
            exit(1)

    ADMIN_USER = "Error"
    while ADMIN_USER == "Error":
        try:
            ADMIN_USER = DB.get_ui_user(as_dict=True)
        except BaseException as e:
            LOGGER.debug(f"Couldn't get the admin user: {e}")
            sleep(1)

    env_admin_username = getenv("ADMIN_USERNAME", "")
    env_admin_password = getenv("ADMIN_PASSWORD", "")

    if ADMIN_USER:
        LOGGER.debug(f"Admin user: {ADMIN_USER}")
        if env_admin_username or env_admin_password:
            override_admin_creds = getenv("OVERRIDE_ADMIN_CREDS", "no").lower() == "yes"
            if ADMIN_USER["method"] == "manual" or override_admin_creds:
                updated = False
                if env_admin_username and ADMIN_USER["username"] != env_admin_username:
                    ADMIN_USER["username"] = env_admin_username
                    updated = True

                if env_admin_password and not check_password(env_admin_password, ADMIN_USER["password"]):
                    if not USER_PASSWORD_RX.match(env_admin_password):
                        LOGGER.warning(
                            "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-). It will not be updated."
                        )
                    else:
                        ADMIN_USER["password"] = gen_password_hash(env_admin_password)
                        updated = True

                if updated:
                    if override_admin_creds:
                        LOGGER.warning("Overriding the admin user credentials, as the OVERRIDE_ADMIN_CREDS environment variable is set to 'yes'.")
                    err = DB.update_ui_user(ADMIN_USER["username"], ADMIN_USER["password"], ADMIN_USER["totp_secret"], method="manual")
                    if err:
                        LOGGER.error(f"Couldn't update the admin user in the database: {err}")
                    else:
                        LOGGER.info("The admin user was updated successfully")
            else:
                LOGGER.warning("The admin user wasn't created manually. You can't change it from the environment variables.")
    elif env_admin_username and env_admin_password:
        user_name = env_admin_username or "admin"

        if not DEBUG:
            if len(user_name) > 256:
                LOGGER.error("The admin username is too long. It must be less than 256 characters.")
                exit(1)
            elif not USER_PASSWORD_RX.match(env_admin_password):
                LOGGER.error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
                )
                exit(1)

        ret = DB.create_ui_user(user_name, gen_password_hash(env_admin_password), ["admin"], admin=True)
        if ret:
            LOGGER.error(f"Couldn't create the admin user in the database: {ret}")
            exit(1)

    LOGGER.info("UI is ready")


def when_ready(server):
    RUN_DIR.joinpath("ui.pid").write_text(str(getpid()), encoding="utf-8")
    TMP_DIR.joinpath("ui.healthy").write_text("ok", encoding="utf-8")


def on_exit(server):
    RUN_DIR.joinpath("ui.pid").unlink(missing_ok=True)
    TMP_DIR.joinpath("ui.healthy").unlink(missing_ok=True)
    TMP_DIR.joinpath(".flask_secret").unlink(missing_ok=True)
