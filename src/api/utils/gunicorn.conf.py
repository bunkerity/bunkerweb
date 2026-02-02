from datetime import datetime
from hashlib import sha256
from json import JSONDecodeError, dump, loads
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from secrets import token_hex
from stat import S_IRUSR, S_IWUSR
from sys import exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from biscuit_auth import KeyPair, PublicKey, PrivateKey

from common_utils import effective_cpu_count, handle_docker_secrets  # type: ignore
from logger import getLogger, log_types  # type: ignore

from app.models.api_database import APIDatabase
from app.utils import BISCUIT_PRIVATE_KEY_FILE, BISCUIT_PUBLIC_KEY_FILE, USER_PASSWORD_RX, check_password, gen_password_hash

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
TMP_UI_DIR = TMP_DIR.joinpath("api")
RUN_DIR = Path(sep, "var", "run", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

# ACL cache (file-backed like a tiny redis)
API_ACL_FILE = LIB_DIR.joinpath("api_acl.json")

HEALTH_FILE = TMP_DIR.joinpath("api.healthy")

PID_FILE = RUN_DIR.joinpath("api.pid")

BISCUIT_PUBLIC_KEY_HASH_FILE = BISCUIT_PUBLIC_KEY_FILE.with_suffix(".hash")  # File to store hash of Biscuit public key
BISCUIT_PRIVATE_KEY_HASH_FILE = BISCUIT_PRIVATE_KEY_FILE.with_suffix(".hash")  # File to store hash of Biscuit private key

MAX_WORKERS = int(getenv("MAX_WORKERS", max(effective_cpu_count() - 1, 1)))
LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "info"))
LISTEN_ADDR = getenv("API_LISTEN_ADDR", getenv("LISTEN_ADDR", "0.0.0.0"))
LISTEN_PORT = getenv("API_LISTEN_PORT", getenv("LISTEN_PORT", "8888"))
"""
Trusted proxies / forwarded headers

Default to local/private networks for container installs so reverse proxies on
typical Docker networks can be trusted without opening this to the world.
Linux packages set FORWARDED_ALLOW_IPS explicitly (127.0.0.1) via service
scripts. Operators can override via API_FORWARDED_ALLOW_IPS or
FORWARDED_ALLOW_IPS.
"""
FORWARDED_ALLOW_IPS = getenv(
    "API_FORWARDED_ALLOW_IPS",
    getenv("FORWARDED_ALLOW_IPS", "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"),
)
PROXY_ALLOW_IPS = getenv("API_PROXY_ALLOW_IPS", getenv("PROXY_ALLOW_IPS", FORWARDED_ALLOW_IPS))

"""
TLS/SSL support

Enable TLS by setting API_SSL_ENABLED to yes/true/1 and providing
API_SSL_CERTFILE and API_SSL_KEYFILE. Optional: API_SSL_CA_CERTS,
"""
API_SSL_ENABLED = getenv("API_SSL_ENABLED", getenv("SSL_ENABLED", "no")).lower() in ("1", "true", "yes", "on")
API_SSL_CERTFILE = getenv("API_SSL_CERTFILE", getenv("SSL_CERTFILE", ""))
API_SSL_KEYFILE = getenv("API_SSL_KEYFILE", getenv("SSL_KEYFILE", ""))
API_SSL_CA_CERTS = getenv("API_SSL_CA_CERTS", getenv("SSL_CA_CERTS", ""))

CAPTURE_OUTPUT = getenv("CAPTURE_OUTPUT", "no").lower() == "yes"

if CAPTURE_OUTPUT or "file" in log_types:
    errorlog = getenv("LOG_FILE_PATH", join(sep, "var", "log", "bunkerweb", "api.log"))
    accesslog = f"{errorlog.rsplit('.', 1)[0]}-access.log"
else:
    errorlog = "-"
    accesslog = "-"

if "syslog" in log_types:
    syslog = True
    syslog_addr = getenv("LOG_SYSLOG_ADDRESS", "").strip()
    if not syslog_addr.startswith(("/", "udp://", "tcp://")):
        syslog_addr = f"udp://{syslog_addr}"
    syslog_prefix = getenv("LOG_SYSLOG_TAG", "bw-api")

wsgi_app = "app.main:app"
proc_name = "bunkerweb-api"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
capture_output = CAPTURE_OUTPUT
limit_request_line = 0
limit_request_fields = 32768
limit_request_field_size = 0
reuse_port = True
daemon = False
chdir = join(sep, "usr", "share", "bunkerweb", "api")
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
pythonpath = join(sep, "usr", "share", "bunkerweb", "deps", "python") + "," + join(sep, "usr", "share", "bunkerweb", "api")
proxy_allow_ips = PROXY_ALLOW_IPS
casefold_http_method = True
workers = MAX_WORKERS
bind = f"{LISTEN_ADDR}:{LISTEN_PORT}"
worker_class = "utils.worker.ApiUvicornWorker"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 30
http_protocols = "h3,h2,h1"

DEBUG = getenv("DEBUG", False)

loglevel = "debug" if DEBUG else LOG_LEVEL.lower()

if DEBUG:
    reload = True
    reload_extra_files = [
        file.as_posix()
        for file in Path(sep, "usr", "share", "bunkerweb", "api", "app").rglob("*")
        if "__pycache__" not in file.parts and "static" not in file.parts
    ]

# Configure TLS when enabled and files provided
if API_SSL_ENABLED and API_SSL_CERTFILE and API_SSL_KEYFILE:
    certfile = API_SSL_CERTFILE
    keyfile = API_SSL_KEYFILE
    if API_SSL_CA_CERTS:
        ca_certs = API_SSL_CA_CERTS


def on_starting(server):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    TMP_UI_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    # Handle Docker secrets first
    docker_secrets = handle_docker_secrets()
    if docker_secrets:
        environ.update(docker_secrets)

    LOGGER = getLogger("API")

    if docker_secrets:
        LOGGER.info(f"Loaded {len(docker_secrets)} Docker secrets")

    def set_secure_permissions(file_path: Path):
        """Set file permissions to 600 (owner read/write only)."""
        file_path.chmod(S_IRUSR | S_IWUSR)

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
        LOGGER.debug(format_exc())
        LOGGER.critical(f"An error occurred while handling Biscuit keys: {e}")
        exit(1)

    DB = APIDatabase(LOGGER)
    current_time = datetime.now().astimezone()

    ready = False
    while not ready:
        if (datetime.now().astimezone() - current_time).total_seconds() > 60:
            LOGGER.error("Timed out while waiting for the database to be initialized.")
            exit(1)

        db_metadata = DB.get_metadata()
        if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
            LOGGER.warning("Database is not initialized, retrying in 5s ...")
        else:
            ready = True
            continue
        sleep(5)

    current_time = datetime.now().astimezone()

    API_USER = "Error"
    while API_USER == "Error":
        if (datetime.now().astimezone() - current_time).total_seconds() > 60:
            LOGGER.error("Timed out while waiting for the api user.")
            exit(1)

        try:
            API_USER = DB.get_api_user(as_dict=True)
        except BaseException as e:
            LOGGER.debug(f"Couldn't get the api user: {e}")
            sleep(1)

    env_api_username = getenv("API_USERNAME", "")
    env_api_password = getenv("API_PASSWORD", "")

    if API_USER:
        # Note: UI TOTP keys logic does not apply to API users

        if env_api_username or env_api_password:
            override_api_creds = getenv("OVERRIDE_API_CREDS", "no").lower() == "yes"
            if API_USER["method"] == "manual" or override_api_creds:
                updated = False
                if env_api_username and API_USER["username"] != env_api_username:
                    API_USER["username"] = env_api_username
                    updated = True

                if env_api_password and not check_password(env_api_password, API_USER["password"]):
                    if not USER_PASSWORD_RX.match(env_api_password):
                        LOGGER.warning(
                            "The api password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character. It will not be updated."
                        )
                    else:
                        API_USER["password"] = gen_password_hash(env_api_password)
                        updated = True

                if updated:
                    if override_api_creds:
                        LOGGER.warning("Overriding the api user credentials, as the OVERRIDE_api_CREDS environment variable is set to 'yes'.")
                    err = DB.update_api_user(
                        API_USER["username"],
                        API_USER["password"],
                        method="manual",
                    )
                    if err:
                        LOGGER.error(f"Couldn't update the api user in the database: {err}")
                    else:
                        LOGGER.info("The api user was updated successfully.")
            else:
                LOGGER.warning("The api user wasn't created manually. You can't change it from the environment variables.")
    elif env_api_username and env_api_password:
        user_name = env_api_username

        if not DEBUG:
            if len(user_name) > 256:
                LOGGER.error("The api username is too long. It must be less than 256 characters.")
                exit(1)
            elif not USER_PASSWORD_RX.match(env_api_password):
                LOGGER.error(
                    "The api password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character."
                )
                exit(1)

        ret = DB.create_api_user(user_name, gen_password_hash(env_api_password), admin=True, method="manual")
        if ret and "already exists" not in ret:
            LOGGER.critical(f"Couldn't create the api user in the database: {ret}")
            exit(1)

    # Build ACL cache file (redis-like JSON) for API users
    try:
        acl_data = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "users": {},
        }

        # Collect all API users and their permissions using model helper
        all_users = DB.list_api_users()

        for uname, is_admin in all_users:
            if is_admin:
                acl_data["users"][uname] = {
                    "admin": True,
                    "permissions": {},
                }
            else:
                # as_dict=True to get nested mapping resource_type -> resource_id|* -> {perm: True}
                perms = DB.get_api_permissions(uname, as_dict=True)
                acl_data["users"][uname] = {
                    "admin": False,
                    "permissions": perms,
                }

        # Persist to disk with 600 perms
        with API_ACL_FILE.open("w", encoding="utf-8") as f:
            dump(acl_data, f)
        set_secure_permissions(API_ACL_FILE)
        LOGGER.info(f"ACL cache written to {API_ACL_FILE}")
    except Exception as e:
        LOGGER.error(f"Failed to build ACL cache: {e}")

    # Optional: bootstrap API users and permissions from a JSON file
    # Env: API_ACL_BOOTSTRAP_FILE (defaults to /var/lib/bunkerweb/api_acl_bootstrap.json if present)
    try:
        bootstrap_path = (getenv("API_ACL_BOOTSTRAP_FILE", "") or "").strip()
        default_bootstrap = LIB_DIR.joinpath("api_acl_bootstrap.json")
        if not bootstrap_path and default_bootstrap.is_file():
            bootstrap_path = default_bootstrap.as_posix()

        if bootstrap_path:
            bp = Path(bootstrap_path)
            if not bp.is_file():
                LOGGER.warning(f"API_ACL_BOOTSTRAP_FILE set but not found: {bootstrap_path}")
            else:
                LOGGER.info(f"Bootstrapping API users/permissions from {bootstrap_path}")
                raw = bp.read_text(encoding="utf-8")
                data = loads(raw)

                users_obj = data.get("users", [])
                # Allow both dict and list forms
                if isinstance(users_obj, dict):
                    iterable = [(uname, udata) for uname, udata in users_obj.items()]
                elif isinstance(users_obj, list):
                    iterable = []
                    for entry in users_obj:
                        if isinstance(entry, dict) and "username" in entry:
                            uname = str(entry.get("username", "")).strip()
                            if uname:
                                iterable.append((uname, entry))
                else:
                    iterable = []

                # Helper: check if user exists and admin flag
                def _get_user(username: str):
                    try:
                        u = DB.get_api_user(username=username)  # type: ignore[arg-type]
                        return u
                    except Exception:
                        return None

                for uname, udata in iterable:
                    if not uname:
                        continue
                    admin_flag = bool(udata.get("admin", False)) if isinstance(udata, dict) else False
                    pwd_hash = None
                    if isinstance(udata, dict):
                        # Accept either plaintext password or bcrypt hash
                        plain = udata.get("password")
                        hashed = udata.get("password_hash") or udata.get("password_bcrypt")
                        if isinstance(hashed, str) and hashed:
                            pwd_hash = hashed.encode("utf-8")
                        elif isinstance(plain, str) and plain:
                            if not DEBUG and not USER_PASSWORD_RX.match(plain):
                                LOGGER.warning(f"Skipping weak password for user {uname}; generating a random one instead")
                                plain = token_hex(24)
                            pwd_hash = gen_password_hash(plain)

                    existing = _get_user(uname)
                    if existing:
                        # Update password if provided
                        if pwd_hash is not None:
                            err = DB.update_api_user(uname, pwd_hash, method="manual")
                            if err:
                                LOGGER.error(f"Couldn't update API user {uname}: {err}")
                    else:
                        # No user -> create
                        if pwd_hash is None:
                            # Generate a secure random password when not provided
                            rand_pwd = token_hex(24)
                            pwd_hash = gen_password_hash(rand_pwd)
                            LOGGER.warning(f"No password provided for {uname}; generated a random one. Please rotate it.")

                        ret = DB.create_api_user(uname, pwd_hash, admin=admin_flag, method="manual")
                        if ret:
                            if admin_flag and "An admin user already exists" in ret:
                                LOGGER.warning(f"Admin user already exists; creating {uname} as non-admin")
                                ret2 = DB.create_api_user(uname, pwd_hash, admin=False, method="manual")
                                if ret2:
                                    LOGGER.error(f"Couldn't create API user {uname}: {ret2}")
                            elif "already exists" in ret:
                                LOGGER.info(f"User {uname} already exists; skipping creation")
                            else:
                                LOGGER.error(f"Couldn't create API user {uname}: {ret}")

                    # Apply permissions if provided
                    perms = {}
                    if isinstance(udata, dict):
                        perms = udata.get("permissions", {}) or {}

                    try:
                        if isinstance(perms, dict):
                            for rtype, rid_map in perms.items():
                                if not isinstance(rtype, str):
                                    continue
                                if isinstance(rid_map, dict):
                                    for rid, perm_map in rid_map.items():
                                        # Accept "*" or null as global
                                        rid_norm = None if rid in (None, "*", "") else rid
                                        if isinstance(perm_map, dict):
                                            for pname, granted in perm_map.items():
                                                if not isinstance(pname, str):
                                                    continue
                                                if bool(granted):
                                                    err = DB.grant_api_permission(uname, pname, resource_type=rtype, resource_id=rid_norm, granted=True)
                                                    if err:
                                                        LOGGER.warning(f"Couldn't grant {uname}:{pname} on {rtype}/{rid_norm or '*'}: {err}")
                                else:
                                    LOGGER.warning(f"Invalid permissions format for user {uname} at resource_type={rtype}")
                        elif isinstance(perms, list):
                            for p in perms:
                                if not isinstance(p, dict):
                                    continue
                                pname = p.get("permission")
                                rtype = p.get("resource_type")
                                rid = p.get("resource_id")
                                granted = bool(p.get("granted", True))
                                if isinstance(pname, str) and isinstance(rtype, str) and granted:
                                    err = DB.grant_api_permission(uname, pname, resource_type=rtype, resource_id=rid, granted=True)
                                    if err:
                                        LOGGER.warning(f"Couldn't grant {uname}:{pname} on {rtype}/{rid or '*'}: {err}")
                    except Exception as e:
                        LOGGER.error(f"Failed to apply permissions for {uname}: {e}")
    except JSONDecodeError as e:
        LOGGER.error(f"Invalid JSON in API ACL bootstrap file: {e}")
    except Exception as e:
        LOGGER.error(f"Error while bootstrapping API ACL: {e}")

    # Safety check: ensure at least one auth path is configured
    try:
        admin_exists = bool(DB.get_api_user(as_dict=True))
    except Exception:
        admin_exists = False

    api_token_present = bool(getenv("API_TOKEN", "").strip())

    if not (keys_loaded or admin_exists or api_token_present):
        LOGGER.critical("No authentication configured: no Biscuit keys provided (ACL), no admin API user, and no API_TOKEN. Exiting.")
        exit(1)

    LOGGER.info("API is ready")


def when_ready(server):
    HEALTH_FILE.write_text("ok", encoding="utf-8")


def on_exit(server):
    HEALTH_FILE.unlink(missing_ok=True)
    API_ACL_FILE.unlink(missing_ok=True)
