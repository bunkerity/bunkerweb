from os import W_OK, X_OK, access, environ, getenv, sep, umask
from os.path import join
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Union

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")
LETSENCRYPT_PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
LETSENCRYPT_JOBS_PATH = LETSENCRYPT_PLUGIN_PATH.joinpath("jobs")
ZEROSSL_BOT_SCRIPT = LETSENCRYPT_PLUGIN_PATH.joinpath("lib", "zerossl-bot.sh")
LETSENCRYPT_CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
LETSENCRYPT_DATA_PATH = LETSENCRYPT_CACHE_PATH.joinpath("etc")
LETSENCRYPT_WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LETSENCRYPT_LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

LETSENCRYPT_PRODUCTION_DIRECTORY = "https://acme-v02.api.letsencrypt.org/directory"
LETSENCRYPT_STAGING_DIRECTORY = "https://acme-staging-v02.api.letsencrypt.org/directory"
ZEROSSL_DIRECTORY = "https://acme.zerossl.com/v2/DV90"


_API_SETTINGS_WHITELIST = frozenset(
    {
        "API_HTTP_PORT",
        "API_HTTPS_PORT",
        "API_LISTEN_IP",
        "API_LISTEN_HTTP",
        "API_LISTEN_HTTPS",
        "API_SERVER_NAME",
        "API_TOKEN",
        "API_WHITELIST_IP",
    }
)


def add_internal_api_env(cmd_env: Dict[str, str], env_vars: Optional[Mapping[str, str]] = None) -> None:
    """Re-add internal API env vars removed with DB config keys."""
    if env_vars is None:
        env_vars = environ
    for key in _API_SETTINGS_WHITELIST:
        value = env_vars.get(key)
        if value:
            cmd_env[key] = value


def build_certbot_env(job, deps_path: str, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build a clean certbot execution environment from process env + job DB config."""
    cmd_env = dict(base_env) if base_env is not None else environ.copy()

    db_config = job.db.get_config()
    for key in db_config:
        cmd_env.pop(key, None)

    current_pythonpath = cmd_env.get("PYTHONPATH", "")
    pythonpath_entries = [entry for entry in current_pythonpath.split(":") if entry]
    if deps_path not in pythonpath_entries:
        pythonpath_entries.append(deps_path)
    cmd_env["PYTHONPATH"] = ":".join(pythonpath_entries)

    database_uri = getenv("DATABASE_URI", "")
    if database_uri:
        cmd_env["DATABASE_URI"] = database_uri

    add_internal_api_env(cmd_env)
    return cmd_env


def prepare_logs_dir(logs_dir: Union[str, Path], logger) -> None:
    """Ensure the Let's Encrypt logs directory is writable by the running user."""
    try:
        umask(0o007)
    except BaseException:
        logger.debug("Failed to set umask to 007 for letsencrypt logs")

    logs_path = Path(logs_dir)
    try:
        logs_path.mkdir(parents=True, exist_ok=True)
    except BaseException as e:
        logger.error(f"Failed to create Let's Encrypt logs directory {logs_path}: {e}")
        return

    try:
        logs_path.chmod(0o2770)
    except BaseException as e:
        logger.debug(f"Failed to set permissions on {logs_path}: {e}")

    for log_file in logs_path.glob("*.log*"):
        try:
            if access(log_file, W_OK):
                log_file.chmod(0o660)
            else:
                logger.warning(f"Removing unwritable Let's Encrypt log file {log_file}")
                log_file.unlink(missing_ok=True)
        except BaseException as e:
            logger.debug(f"Failed to adjust permissions on log file {log_file}: {e}")


def is_zerossl_used_in_env(env_vars: Optional[Mapping[str, str]] = None) -> bool:
    """Return True when at least one active service uses LETS_ENCRYPT_SERVER=zerossl."""
    if env_vars is None:
        env_vars = environ

    if env_vars.get("MULTISITE", "no") != "yes":
        return env_vars.get("AUTO_LETS_ENCRYPT", "no") == "yes" and env_vars.get("LETS_ENCRYPT_SERVER", "letsencrypt").lower() == "zerossl"

    for first_server in env_vars.get("SERVER_NAME", "www.example.com").split():
        if not first_server:
            continue
        if env_vars.get(f"{first_server}_AUTO_LETS_ENCRYPT", "no") != "yes":
            continue
        if env_vars.get(f"{first_server}_LETS_ENCRYPT_SERVER", env_vars.get("LETS_ENCRYPT_SERVER", "letsencrypt")).lower() == "zerossl":
            return True
    return False


def resolve_certbot_entrypoint(
    acme_server: str,
    certbot_bin: str,
    zerossl_bot_script: Path,
    logger,
    cmd_env: Optional[Dict[str, str]] = None,
    fallback_to_certbot: bool = False,
) -> List[str]:
    """Resolve which executable to use for ACME operations."""
    if acme_server != "zerossl":
        return [certbot_bin]

    if zerossl_bot_script.is_file() and access(zerossl_bot_script, X_OK):
        if cmd_env is not None:
            cmd_env["CERTBOT_BIN"] = certbot_bin
        return [zerossl_bot_script.as_posix()]

    message = f"ZeroSSL is enabled but zerossl-bot is missing or not executable ({zerossl_bot_script})."
    if fallback_to_certbot:
        logger.warning(f"{message} Falling back to certbot.")
        return [certbot_bin]

    logger.error(message)
    return []


def get_expected_acme_directory(server: str, staging: bool) -> str:
    if server == "zerossl":
        return ZEROSSL_DIRECTORY
    if staging:
        return LETSENCRYPT_STAGING_DIRECTORY
    return LETSENCRYPT_PRODUCTION_DIRECTORY
