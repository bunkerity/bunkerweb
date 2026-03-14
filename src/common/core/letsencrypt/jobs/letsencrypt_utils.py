from configparser import ConfigParser
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


def _renewal_config_is_broken(conf: Path) -> bool:
    """
    Return True if the renewal config is empty, unparseable, or missing required file references
    so certbot would fail on it (parsefail / "missing a required file reference").
    Reissue does not use this file; callers use service definitions from env (load_services) instead.
    """
    try:
        if conf.stat().st_size == 0:
            return True
        parser = ConfigParser(interpolation=None)  # paths may contain %; avoid InterpolationError
        read_ok = parser.read(str(conf), encoding="utf-8")
        if not read_ok or len(parser.sections()) == 0:
            return True
        # Certbot requires at least one section with cert/fullchain/privkey pointing into archive/
        has_required_ref = False
        for section in parser.sections():
            for key in ("cert", "fullchain", "privkey"):
                if parser.has_option(section, key):
                    val = parser.get(section, key).strip()
                    if val and "archive" in val:
                        has_required_ref = True
                        break
            if has_required_ref:
                break
        if not has_required_ref:
            return True
        # Certbot also fails with "expected .../live/<lineage>/cert.pem to be a symlink" when live/ files are regular files.
        # Treat as broken so we remove the config and reissue from service definition (repair may have skipped if archive missing).
        etc_path = conf.parent.parent  # renewal/ -> etc/
        live_lineage = etc_path.joinpath("live", conf.stem)
        for name in ("cert.pem", "fullchain.pem", "privkey.pem"):
            f = live_lineage.joinpath(name)
            if f.exists() and not f.is_symlink():
                return True
        return False
    except Exception:
        # Any read/parse error (e.g. InterpolationError, bad INI) = broken; treat as such and let caller remove/reissue.
        return True


def remove_empty_renewal_configs(etc_path: Path, logger) -> List[str]:
    """
    Remove broken (0-byte or unparseable) renewal config files so certbot renew does not fail.
    Returns the list of removed cert names (filename without .conf) so callers can trigger reissue.
    Reissue uses service definitions from env (load_services), not the failing config file.
    Cert names can have an -ecdsa or -rsa suffix (e.g. www.example.com-ecdsa).

    Why this exists: after a DB restore or corruption, renewal configs can be empty or invalid INI.
    Certbot aborts the whole renewal run on one bad file. We remove broken configs and reissue
    using the service configuration so the certificate is recreated without relying on the bad file.
    """
    removed: List[str] = []
    renewal_dir = etc_path.joinpath("renewal")
    if not renewal_dir.is_dir():
        return removed
    for conf in renewal_dir.glob("*.conf"):
        try:
            try:
                is_broken = _renewal_config_is_broken(conf)
            except Exception as e:
                logger.debug(f"Error checking renewal config {conf.name}: {e}, treating as broken.")
                is_broken = True
            if not is_broken:
                continue
            cert_name = conf.stem
            conf.unlink()
            removed.append(cert_name)
            logger.info(f"Removed broken renewal config {conf.name}; will reissue from service definition.")
        except OSError as e:
            logger.debug(f"Could not remove renewal config {conf}: {e}")
    return removed


def repair_live_symlinks(etc_path: Path, logger) -> None:
    """
    Ensure live/<domain>/cert.pem, fullchain.pem, privkey.pem (and chain.pem) are symlinks
    into archive/. After restore from DB, tar extraction may have created regular files
    instead of symlinks, which breaks certbot renew.
    <domain> can have an -ecdsa or -rsa suffix (e.g. www.example.com-ecdsa).

    Why this exists: when Let's Encrypt state is restored from a tar archive, symlinks may be
    materialized as regular files. Certbot expects live/ files to be symlinks into archive/.
    """
    live_dir = etc_path.joinpath("live")
    archive_dir = etc_path.joinpath("archive")
    renewal_dir = etc_path.joinpath("renewal")
    if not live_dir.is_dir() or not archive_dir.is_dir():
        return
    for live_domain in live_dir.iterdir():
        if not live_domain.is_dir():
            continue
        domain = live_domain.name
        archive_domain = archive_dir.joinpath(domain)
        if not archive_domain.is_dir():
            continue
        # Resolve target filenames (cert1.pem, fullchain1.pem, etc.) from renewal config or default to 1
        targets: Dict[str, str] = {}
        renewal_conf = renewal_dir.joinpath(f"{domain}.conf")
        if renewal_conf.is_file():
            try:
                parser = ConfigParser(interpolation=None)  # paths may contain %
                parser.read(str(renewal_conf), encoding="utf-8")
                for section in parser.sections():
                    for key in ("cert", "privkey", "fullchain", "chain"):
                        if parser.has_option(section, key):
                            val = parser.get(section, key).strip()
                            if val and "archive" in val:
                                # path is relative to config file (renewal/), e.g. ../../archive/domain/cert1.pem
                                targets[key] = val
                                break
                    if targets:
                        break
            except Exception as e:
                logger.debug(f"Could not parse renewal config {renewal_conf}: {e}")
        # Fallback: use cert1.pem, fullchain1.pem, privkey1.pem, chain1.pem
        for key, default in (("cert", "cert1.pem"), ("privkey", "privkey1.pem"), ("fullchain", "fullchain1.pem"), ("chain", "chain1.pem")):
            if key not in targets:
                if key == "chain" and not archive_domain.joinpath("chain1.pem").exists():
                    continue
                targets[key] = f"../../archive/{domain}/{default}"
        for live_name, archive_rel in (("cert.pem", targets.get("cert")), ("fullchain.pem", targets.get("fullchain")), ("privkey.pem", targets.get("privkey")), ("chain.pem", targets.get("chain"))):
            if not archive_rel:
                continue
            live_file = live_domain.joinpath(live_name)
            archive_basename = Path(archive_rel).name
            archive_file = archive_domain.joinpath(archive_basename)
            if not archive_file.exists():
                continue
            # Symlink from live/domain/ to archive/domain/: use relative path ../../archive/domain/basename
            link_target = f"../../archive/{domain}/{archive_basename}"
            try:
                if live_file.exists():
                    if live_file.is_symlink():
                        if live_file.resolve() == archive_file.resolve():
                            continue
                        live_file.unlink()
                    else:
                        live_file.unlink()
                live_file.symlink_to(link_target)
            except OSError as e:
                logger.debug(f"Could not repair symlink {live_file} -> {link_target}: {e}")
