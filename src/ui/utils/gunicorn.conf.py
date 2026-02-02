from datetime import datetime
from hashlib import sha256
from json import JSONDecodeError, dump, dumps, loads
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from secrets import token_hex
from stat import S_IRUSR, S_IWUSR
from subprocess import call
from sys import exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from biscuit_auth import KeyPair, PublicKey, PrivateKey
from passlib.totp import generate_secret

from common_utils import effective_cpu_count, handle_docker_secrets  # type: ignore
from logger import getLogger, log_types  # type: ignore

from app.models.ui_database import UIDatabase
from app.dependencies import reload_plugins
from app.utils import BISCUIT_PRIVATE_KEY_FILE, BISCUIT_PUBLIC_KEY_FILE, USER_PASSWORD_RX, check_password, gen_password_hash, get_latest_stable_release

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
TMP_UI_DIR = TMP_DIR.joinpath("ui")
RUN_DIR = Path(sep, "var", "run", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

UI_DATA_FILE = TMP_DIR.joinpath("ui_data.json")
HEALTH_FILE = TMP_DIR.joinpath("ui.healthy")
ERROR_FILE = TMP_DIR.joinpath("ui.error")

TMP_PID_FILE = RUN_DIR.joinpath("tmp-ui.pid")
PID_FILE = RUN_DIR.joinpath("ui.pid")

UI_SESSIONS_CACHE = LIB_DIR.joinpath("ui_sessions_cache")

FLASK_SECRET_FILE = LIB_DIR.joinpath(".flask_secret")
FLASK_SECRET_HASH_FILE = FLASK_SECRET_FILE.with_suffix(".hash")  # File to store hash of Flask secret
TOTP_ENCRYPTION_KEYS_FILE = LIB_DIR.joinpath(".totp_encryption_keys.json")
TOTP_ENCRYPTION_HASH_FILE = TOTP_ENCRYPTION_KEYS_FILE.with_suffix(".hash")  # File to store hash of TOTP encryption key(s)
TOTP_SECRETS_FILE = LIB_DIR.joinpath(".totp_secrets.json")
TOTP_HASH_FILE = TOTP_SECRETS_FILE.with_suffix(".hash")  # File to store hash of TOTP secrets
BISCUIT_PUBLIC_KEY_HASH_FILE = BISCUIT_PUBLIC_KEY_FILE.with_suffix(".hash")  # File to store hash of Biscuit public key
BISCUIT_PRIVATE_KEY_HASH_FILE = BISCUIT_PRIVATE_KEY_FILE.with_suffix(".hash")  # File to store hash of Biscuit private key

MAX_WORKERS = int(getenv("MAX_WORKERS", max(effective_cpu_count() - 1, 1)))
LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "info"))
LISTEN_ADDR = getenv("UI_LISTEN_ADDR", getenv("LISTEN_ADDR", "0.0.0.0"))
LISTEN_PORT = getenv("UI_LISTEN_PORT", getenv("LISTEN_PORT", "7000"))
FORWARDED_ALLOW_IPS = getenv(
    "UI_FORWARDED_ALLOW_IPS",
    getenv("FORWARDED_ALLOW_IPS", "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"),
)
PROXY_ALLOW_IPS = getenv("UI_PROXY_ALLOW_IPS", getenv("PROXY_ALLOW_IPS", FORWARDED_ALLOW_IPS))
"""
TLS/SSL support

Enable TLS by setting UI_SSL_ENABLED to yes/true/1 and providing
UI_SSL_CERTFILE and UI_SSL_KEYFILE. Optional: UI_SSL_CA_CERTS,
"""
UI_SSL_ENABLED = getenv("UI_SSL_ENABLED", getenv("SSL_ENABLED", "no")).lower() in ("1", "true", "yes", "on")
UI_SSL_CERTFILE = getenv("UI_SSL_CERTFILE", getenv("SSL_CERTFILE", ""))
UI_SSL_KEYFILE = getenv("UI_SSL_KEYFILE", getenv("SSL_KEYFILE", ""))
UI_SSL_CA_CERTS = getenv("UI_SSL_CA_CERTS", getenv("SSL_CA_CERTS", ""))
CAPTURE_OUTPUT = getenv("CAPTURE_OUTPUT", "no").lower() == "yes"

if CAPTURE_OUTPUT or "file" in log_types:
    errorlog = getenv("LOG_FILE_PATH", join(sep, "var", "log", "bunkerweb", "ui.log"))
    accesslog = f"{errorlog.rsplit('.', 1)[0]}-access.log"
else:
    errorlog = "-"
    accesslog = "-"

if "syslog" in log_types:
    syslog = True
    syslog_addr = getenv("LOG_SYSLOG_ADDRESS", "").strip()
    if not syslog_addr.startswith(("/", "udp://", "tcp://")):
        syslog_addr = f"udp://{syslog_addr}"
    syslog_prefix = getenv("LOG_SYSLOG_TAG", "bw-ui")

wsgi_app = "main:app"
proc_name = "bunkerweb-ui"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
capture_output = CAPTURE_OUTPUT
limit_request_line = 0
limit_request_fields = 32768
limit_request_field_size = 0
reuse_port = True
daemon = False
chdir = join(sep, "usr", "share", "bunkerweb", "ui")
umask = 0x027
pidfile = PID_FILE.as_posix()
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = TMP_UI_DIR.as_posix()
secure_scheme_headers = {
    "X-FORWARDED-PROTOCOL": "https",
    "X-FORWARDED-PROTO": "https",
    "X-FORWARDED-SSL": "on",
}
forwarded_allow_ips = FORWARDED_ALLOW_IPS
pythonpath = join(sep, "usr", "share", "bunkerweb", "deps", "python") + "," + join(sep, "usr", "share", "bunkerweb", "ui")
proxy_allow_ips = PROXY_ALLOW_IPS
casefold_http_method = True
workers = MAX_WORKERS
bind = f"{LISTEN_ADDR}:{LISTEN_PORT}"
worker_class = "gthread"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 30
http_protocols = "h1"  # TODO: add h2 when fixed and h3 when supported

DEBUG = getenv("DEBUG", False)

loglevel = "debug" if DEBUG else LOG_LEVEL.lower()

if DEBUG:
    reload = True
    reload_extra_files = [
        file.as_posix()
        for file in Path(sep, "usr", "share", "bunkerweb", "ui", "app").rglob("*")
        if "__pycache__" not in file.parts and "static" not in file.parts
    ]

# Configure TLS when enabled and files provided
if UI_SSL_ENABLED and UI_SSL_CERTFILE and UI_SSL_KEYFILE:
    certfile = UI_SSL_CERTFILE
    keyfile = UI_SSL_KEYFILE
    if UI_SSL_CA_CERTS:
        ca_certs = UI_SSL_CA_CERTS


def on_starting(server):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    TMP_UI_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    ERROR_FILE.unlink(missing_ok=True)

    # Handle Docker secrets first
    docker_secrets = handle_docker_secrets()
    if docker_secrets:
        environ.update(docker_secrets)

    LOGGER = getLogger("UI")

    if docker_secrets:
        LOGGER.info(f"Loaded {len(docker_secrets)} Docker secrets")

    def set_secure_permissions(file_path: Path):
        """Set file permissions to 600 (owner read/write only)."""
        file_path.chmod(S_IRUSR | S_IWUSR)

    # * Handle Flask secret
    try:
        flask_secret = None

        # * Step 1: Load Flask secret from file
        if FLASK_SECRET_FILE.is_file():
            try:
                flask_secret = FLASK_SECRET_FILE.read_text(encoding="utf-8").strip()
                if not flask_secret:
                    raise ValueError("Secret file is empty.")
                LOGGER.info("Flask secret successfully loaded from the file.")
            except (ValueError, Exception) as e:
                LOGGER.error(f"Failed to load Flask secret from file: {e}. Falling back to environment variable or generating a new secret.")

        # * Step 2: Check environment variable if no valid file
        if not flask_secret:
            flask_secret_env = getenv("FLASK_SECRET", "").strip()
            if flask_secret_env:
                flask_secret = flask_secret_env
                LOGGER.info("Flask secret successfully loaded from the environment variable.")

        # * Step 3: Generate new secret if none found
        if not flask_secret:
            LOGGER.warning("No valid Flask secret found. Generating a new random secret...")
            flask_secret = token_hex(64)
            LOGGER.info("Generated a new Flask secret.")

        # * Step 4: Hash for change detection
        current_env_hash = sha256(flask_secret.encode("utf-8")).hexdigest()
        previous_env_hash = FLASK_SECRET_HASH_FILE.read_text(encoding="utf-8").strip() if FLASK_SECRET_HASH_FILE.is_file() else None

        # * Step 5: Compare hashes and update if necessary
        if previous_env_hash and current_env_hash == previous_env_hash:
            LOGGER.info("The FLASK_SECRET environment variable has not changed since the last restart.")
        else:
            LOGGER.warning("The FLASK_SECRET environment variable has changed or is being set for the first time.")
            with FLASK_SECRET_FILE.open("w", encoding="utf-8") as file:
                file.write(flask_secret)
            set_secure_permissions(FLASK_SECRET_FILE)

            with FLASK_SECRET_HASH_FILE.open("w", encoding="utf-8") as file:
                file.write(current_env_hash)
            set_secure_permissions(FLASK_SECRET_HASH_FILE)

        LOGGER.info("Flask secret securely stored.")
        LOGGER.info("Flask secret hash securely stored for change detection.")
    except Exception as e:
        message = f"An error occurred while handling the Flask secret: {e}"
        LOGGER.debug(format_exc())
        LOGGER.critical(message)
        ERROR_FILE.write_text(message, encoding="utf-8")
        exit(1)

    # * Handle TOTP encryption key(s)
    VALID_TOTP_ENCRYPTION_KEY_LENGTH = 43  # (generated by generate_secret())
    invalid_totp_encryption_keys = False
    try:
        totp_encryption_keys = {}

        # * Step 1: Load TOTP encryption key(s) from file
        if TOTP_ENCRYPTION_KEYS_FILE.is_file():
            try:
                totp_encryption_keys = loads(TOTP_ENCRYPTION_KEYS_FILE.read_text(encoding="utf-8"))
                if not isinstance(totp_encryption_keys, dict):
                    raise ValueError("TOTP encryption key(s) file must contain a JSON object.")
                LOGGER.info("TOTP encryption key(s) successfully loaded from the file.")
            except (JSONDecodeError, ValueError) as e:
                LOGGER.error(f"Failed to load TOTP encryption key(s) from file: {e}. Falling back to environment variable or generating new keys.")
        elif TOTP_SECRETS_FILE.is_file():
            try:
                totp_encryption_keys = loads(TOTP_SECRETS_FILE.read_text(encoding="utf-8"))
                LOGGER.info("TOTP encryption key(s) successfully loaded from the file.")
            except JSONDecodeError:
                LOGGER.error("Failed to load TOTP encryption key(s) from file. Falling back to environment or generating new secrets.")

        # * Step 2: Check environment variable if no valid file
        totp_encryption_keys_env = None
        if not totp_encryption_keys:
            totp_encryption_keys_env = getenv("TOTP_ENCRYPTION_KEYS", "").strip() or getenv("TOTP_SECRETS", "").strip()
            if totp_encryption_keys_env:
                try:
                    parsed_secrets = loads(totp_encryption_keys_env)
                    if isinstance(parsed_secrets, dict):
                        totp_encryption_keys = parsed_secrets
                    elif isinstance(parsed_secrets, list):
                        totp_encryption_keys = {f"key-{i+1}": secret for i, secret in enumerate(parsed_secrets)}
                except JSONDecodeError:
                    LOGGER.info("TOTP_ENCRYPTION_KEYS (or TOTP_SECRETS) is not valid JSON. Treating as space-separated secrets.")
                    totp_encryption_keys = {f"key-{i+1}": secret for i, secret in enumerate(totp_encryption_keys_env.split())}

        # * Step 3: Validate and clean secrets
        for key, secret in list(totp_encryption_keys.items()):
            if not isinstance(secret, str) or len(secret) != VALID_TOTP_ENCRYPTION_KEY_LENGTH:
                LOGGER.warning(f"Invalid TOTP secret for key: {key}. Secret will be excluded.")
                totp_encryption_keys.pop(key)

        # * Step 4: Generate new secrets if none are valid
        if not totp_encryption_keys:
            LOGGER.warning("No valid TOTP encryption key(s) found. Generating new secure secrets...")
            totp_encryption_keys = {f"key-{i}": generate_secret() for i in range(1, 6)}
            LOGGER.info(f"Generated {len(totp_encryption_keys)} secure TOTP encryption key(s).")

        # * Step 5: Hash for change detection
        current_env_hash = sha256(dumps(totp_encryption_keys, sort_keys=True).encode("utf-8")).hexdigest()
        previous_env_hash = (
            TOTP_ENCRYPTION_HASH_FILE.read_text(encoding="utf-8").strip()
            if TOTP_ENCRYPTION_HASH_FILE.is_file()
            else TOTP_HASH_FILE.read_text(encoding="utf-8").strip() if TOTP_HASH_FILE.is_file() else None
        )

        # * Step 6: Compare hashes and update if necessary
        if previous_env_hash and current_env_hash == previous_env_hash:
            LOGGER.info("The TOTP_ENCRYPTION_KEYS (or TOTP_SECRETS) environment variable has not changed since the last restart.")
        else:
            if not totp_encryption_keys_env:
                LOGGER.warning("The TOTP_ENCRYPTION_KEYS (or TOTP_SECRETS) environment variable has changed or is being set for the first time.")
                invalid_totp_encryption_keys = True
            else:
                LOGGER.info("We won't reset the TOTP encryption key(s), as the TOTP_ENCRYPTION_KEYS (or TOTP_SECRETS) environment variable is set.")

            if TOTP_SECRETS_FILE.is_file():
                TOTP_SECRETS_FILE.unlink(missing_ok=True)
            if TOTP_HASH_FILE.is_file():
                TOTP_HASH_FILE.unlink(missing_ok=True)

            with TOTP_ENCRYPTION_KEYS_FILE.open("w", encoding="utf-8") as file:
                dump(totp_encryption_keys, file, indent=2)
            set_secure_permissions(TOTP_ENCRYPTION_KEYS_FILE)

            with TOTP_ENCRYPTION_HASH_FILE.open("w", encoding="utf-8") as file:
                file.write(current_env_hash)
            set_secure_permissions(TOTP_ENCRYPTION_HASH_FILE)

        LOGGER.info("TOTP encryption key(s) securely stored.")
        LOGGER.info("TOTP environment hash securely stored for change detection.")
    except Exception as e:
        message = f"An error occurred while handling TOTP encryption key(s): {e}"
        LOGGER.debug(format_exc())
        LOGGER.critical(message)
        ERROR_FILE.write_text(message, encoding="utf-8")
        exit(1)

    # * Handle Biscuit keys
    try:
        biscuit_public_key_hex = None
        biscuit_private_key_hex = None
        keys_loaded = False
        keys_generated = False

        # * Step 1: Load Biscuit keys from files and validate
        if BISCUIT_PUBLIC_KEY_FILE.is_file() and BISCUIT_PRIVATE_KEY_FILE.is_file():
            try:
                pub_hex = BISCUIT_PUBLIC_KEY_FILE.read_text().strip()
                priv_hex = BISCUIT_PRIVATE_KEY_FILE.read_text().strip()
                if not pub_hex or not priv_hex:
                    raise ValueError("One or both Biscuit key files are empty.")

                # Validate by attempting to load
                PublicKey(pub_hex)
                PrivateKey(priv_hex)
                biscuit_public_key_hex = pub_hex
                biscuit_private_key_hex = priv_hex
                keys_loaded = True
                LOGGER.info("Valid Biscuit keys successfully loaded from files.")
            except Exception as e:
                LOGGER.error(f"Failed to load or validate Biscuit keys from files: {e}. Falling back.")
                biscuit_public_key_hex = None  # Ensure reset if loading failed
                biscuit_private_key_hex = None

        # * Step 2: Check environment variables if no valid files loaded
        if not keys_loaded:
            pub_hex_env = getenv("BISCUIT_PUBLIC_KEY", "").strip()
            priv_hex_env = getenv("BISCUIT_PRIVATE_KEY", "").strip()
            if pub_hex_env and priv_hex_env:
                try:
                    # Validate by attempting to load
                    PublicKey(pub_hex_env)
                    PrivateKey(priv_hex_env)
                    biscuit_public_key_hex = pub_hex_env
                    biscuit_private_key_hex = priv_hex_env
                    keys_loaded = True
                    LOGGER.info("Valid Biscuit keys successfully loaded from environment variables.")
                except Exception as e:
                    LOGGER.error(f"Failed to validate Biscuit keys from environment variables: {e}. Falling back.")
                    biscuit_public_key_hex = None  # Ensure reset if env validation failed
                    biscuit_private_key_hex = None

        # * Step 3: Generate new keys if none found or loaded/validated successfully
        if not keys_loaded:
            LOGGER.warning("No valid Biscuit keys found from files or environment. Generating new random keys...")
            # Generate new keys using the biscuit library
            keypair = KeyPair()
            biscuit_private_key_obj = keypair.private_key
            biscuit_public_key_obj = keypair.public_key
            biscuit_private_key_hex = repr(biscuit_private_key_obj)
            biscuit_public_key_hex = repr(biscuit_public_key_obj)
            keys_generated = True
            LOGGER.info("Generated new Biscuit key pair.")

        # Ensure we have keys before proceeding
        if not biscuit_public_key_hex or not biscuit_private_key_hex:
            raise RuntimeError("Failed to load or generate required Biscuit keys.")

        # * Step 4: Hash for change detection
        current_public_key_hash = sha256(biscuit_public_key_hex.encode("utf-8")).hexdigest()
        current_private_key_hash = sha256(biscuit_private_key_hex.encode("utf-8")).hexdigest()
        previous_public_key_hash = BISCUIT_PUBLIC_KEY_HASH_FILE.read_text(encoding="utf-8").strip() if BISCUIT_PUBLIC_KEY_HASH_FILE.is_file() else None
        previous_private_key_hash = BISCUIT_PRIVATE_KEY_HASH_FILE.read_text(encoding="utf-8").strip() if BISCUIT_PRIVATE_KEY_HASH_FILE.is_file() else None

        # * Step 5: Compare hashes and update if necessary
        public_key_changed = previous_public_key_hash is None or current_public_key_hash != previous_public_key_hash
        private_key_changed = previous_private_key_hash is None or current_private_key_hash != previous_private_key_hash

        if public_key_changed or private_key_changed or keys_generated:
            if keys_generated:
                LOGGER.warning("Saving newly generated Biscuit keys.")
            else:
                LOGGER.warning("The Biscuit keys have changed or are being set for the first time.")

            # Update public key file and hash
            with BISCUIT_PUBLIC_KEY_FILE.open("w", encoding="utf-8") as file:
                file.write(biscuit_public_key_hex)
            set_secure_permissions(BISCUIT_PUBLIC_KEY_FILE)

            with BISCUIT_PUBLIC_KEY_HASH_FILE.open("w", encoding="utf-8") as file:
                file.write(current_public_key_hash)
            set_secure_permissions(BISCUIT_PUBLIC_KEY_HASH_FILE)

            # Update private key file and hash
            with BISCUIT_PRIVATE_KEY_FILE.open("w", encoding="utf-8") as file:
                file.write(biscuit_private_key_hex)
            set_secure_permissions(BISCUIT_PRIVATE_KEY_FILE)

            with BISCUIT_PRIVATE_KEY_HASH_FILE.open("w", encoding="utf-8") as file:
                file.write(current_private_key_hash)
            set_secure_permissions(BISCUIT_PRIVATE_KEY_HASH_FILE)
        else:
            LOGGER.info("The Biscuit keys have not changed since the last restart.")

        LOGGER.info("Biscuit keys securely stored.")
        LOGGER.info("Biscuit key hashes securely stored for change detection.")
    except Exception as e:
        message = f"An error occurred while handling Biscuit keys: {e}"
        LOGGER.debug(format_exc())
        LOGGER.critical(message)
        ERROR_FILE.write_text(message, encoding="utf-8")
        exit(1)

    DB = UIDatabase(LOGGER)
    current_time = datetime.now().astimezone()

    ready = False
    while not ready:
        if (datetime.now().astimezone() - current_time).total_seconds() > 60:
            message = "Timed out while waiting for the database to be initialized."
            LOGGER.error(message)
            ERROR_FILE.write_text(message, encoding="utf-8")
            exit(1)

        db_metadata = DB.get_metadata()
        ui_roles = DB.get_ui_roles(as_dict=True)
        if isinstance(db_metadata, str) or not db_metadata["is_initialized"] or (isinstance(ui_roles, str) and "doesn't exist" in ui_roles):
            LOGGER.warning("Database is not initialized, retrying in 5s ...")
        else:
            ready = True
            continue
        sleep(5)

    if not ui_roles:
        ret = DB.create_ui_role("admin", "Admins can create new users, edit and read the data.", ["manage", "write", "read"])
        if ret:
            message = f"Couldn't create the admin role in the database: {ret}"
            LOGGER.error(message)
            ERROR_FILE.write_text(message, encoding="utf-8")
            exit(1)

        ret = DB.create_ui_role("writer", "Writers can edit and read the data but can't create new users.", ["write", "read"])
        if ret:
            message = f"Couldn't create the writer role in the database: {ret}"
            LOGGER.error(message)
            ERROR_FILE.write_text(message, encoding="utf-8")
            exit(1)

        ret = DB.create_ui_role("reader", "Readers can only read the data.", ["read"])
        if ret:
            message = f"Couldn't create the reader role in the database: {ret}"
            LOGGER.error(message)
            ERROR_FILE.write_text(message, encoding="utf-8")
            exit(1)

    current_time = datetime.now().astimezone()

    ADMIN_USER = "Error"
    while ADMIN_USER == "Error":
        if (datetime.now().astimezone() - current_time).total_seconds() > 60:
            message = "Timed out while waiting for the admin user."
            LOGGER.error(message)
            ERROR_FILE.write_text(message, encoding="utf-8")
            exit(1)

        try:
            ADMIN_USER = DB.get_ui_user(as_dict=True)
        except BaseException as e:
            LOGGER.debug(f"Couldn't get the admin user: {e}")
            sleep(1)

    env_admin_username = getenv("ADMIN_USERNAME", "")
    env_admin_password = getenv("ADMIN_PASSWORD", "")

    if ADMIN_USER:
        if invalid_totp_encryption_keys:
            LOGGER.warning("The TOTP encryption key(s) have changed, removing admin TOTP secrets ...")
            err = DB.update_ui_user(
                ADMIN_USER["username"], ADMIN_USER["password"], None, theme=ADMIN_USER["theme"], method=ADMIN_USER["method"], language=ADMIN_USER["language"]
            )
            if err:
                LOGGER.error(f"Couldn't update the admin user in the database: {err}")

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
                            "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character. It will not be updated."
                        )
                    else:
                        ADMIN_USER["password"] = gen_password_hash(env_admin_password)
                        updated = True

                if updated:
                    if override_admin_creds:
                        LOGGER.warning("Overriding the admin user credentials, as the OVERRIDE_ADMIN_CREDS environment variable is set to 'yes'.")
                    err = DB.update_ui_user(
                        ADMIN_USER["username"],
                        ADMIN_USER["password"],
                        ADMIN_USER["totp_secret"],
                        theme=ADMIN_USER["theme"],
                        method="manual",
                        language=ADMIN_USER["language"],
                    )
                    if err:
                        LOGGER.error(f"Couldn't update the admin user in the database: {err}")
                    else:
                        LOGGER.info("The admin user was updated successfully.")
            else:
                LOGGER.warning("The admin user wasn't created manually. You can't change it from the environment variables.")
    elif env_admin_username and env_admin_password:
        user_name = env_admin_username or "admin"

        if not DEBUG:
            if len(user_name) > 256:
                message = "The admin username is too long. It must be less than 256 characters."
                LOGGER.error(message)
                ERROR_FILE.write_text(message, encoding="utf-8")
                exit(1)
            elif not USER_PASSWORD_RX.match(env_admin_password):
                message = "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character."
                LOGGER.error(message)
                ERROR_FILE.write_text(message, encoding="utf-8")
                exit(1)

        ret = DB.create_ui_user(user_name, gen_password_hash(env_admin_password), ["admin"], admin=True)
        if ret and "already exists" not in ret:
            message = f"Couldn't create the admin user in the database: {ret}"
            LOGGER.critical(message)
            ERROR_FILE.write_text(message, encoding="utf-8")
            exit(1)

    latest_version = "unknown"
    try:
        latest_version = get_latest_stable_release()
    except BaseException as e:
        LOGGER.error(f"Exception while fetching latest release information: {e}")

    UI_DATA_FILE.write_text(
        dumps(
            {
                "LATEST_VERSION": latest_version,
                "LATEST_VERSION_LAST_CHECK": datetime.now().astimezone().isoformat(),
                "TO_FLASH": [],
                "READONLY_MODE": DB.readonly,
            }
        ),
        encoding="utf-8",
    )
    set_secure_permissions(UI_DATA_FILE)

    LOGGER.info(
        "UI will disconnect users that have their IP address changed during a session"
        + (" except for private IP addresses." if getenv("CHECK_PRIVATE_IP", "yes").lower() == "no" else ".")
    )

    UI_SESSIONS_CACHE.mkdir(parents=True, exist_ok=True)

    if TMP_PID_FILE.is_file():
        LOGGER.info("Stopping temporary UI...")
        call(["kill", "-SIGTERM", TMP_PID_FILE.read_text().strip()])
        current_time = datetime.now().astimezone()
        while TMP_PID_FILE.is_file():
            if (datetime.now().astimezone() - current_time).total_seconds() > 60:
                message = "Timed out while waiting for the temporary UI to stop."
                LOGGER.error(message)
                ERROR_FILE.write_text(message, encoding="utf-8")
                exit(1)
            sleep(1)
        LOGGER.info("Temporary UI is stopped")

    reload_plugins()

    LOGGER.info("UI is ready")


def when_ready(server):
    HEALTH_FILE.write_text("ok", encoding="utf-8")


def on_exit(server):
    HEALTH_FILE.unlink(missing_ok=True)
    UI_DATA_FILE.unlink(missing_ok=True)
