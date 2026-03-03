from os import W_OK, X_OK, access, environ, getenv, sep, umask
from os.path import join
from pathlib import Path
from re import sub
from select import select
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired
from time import time
from typing import Dict, List, Mapping, Optional, Set, Tuple, Union

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


def add_internal_api_env(cmd_env: Dict[str, str], env_vars: Optional[Mapping[str, str]] = None) -> None:
    """Re-add internal API env vars removed with DB config keys."""
    if env_vars is None:
        env_vars = environ
    for key, value in env_vars.items():
        if key.startswith("API_") and value:
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


def prepare_logs_dir(logs_dir: Union[str, Path], logger, clear_main_log: bool = False) -> None:
    """Ensure the Let's Encrypt logs directory is writable by the running user.

    Args:
        logs_dir: Path to logs directory
        logger: Logger instance
        clear_main_log: If True, clear letsencrypt.log at the start (only once)
    """
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

    # Clear main letsencrypt.log only once at job start
    if clear_main_log:
        main_log = logs_path / "letsencrypt.log"
        try:
            if main_log.exists():
                main_log.write_text("")
                logger.debug(f"Cleared main log file: {main_log}")
        except BaseException as e:
            logger.debug(f"Failed to clear main log file {main_log}: {e}")

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


# CAA property tag values accepted by each supported ACME server.
# A domain is permitted when at least one governing ``issue`` / ``issuewild``
# record contains one of these values (RFC 8659 §4).
# ZeroSSL certificates are backed by Sectigo's CA infrastructure; all four
# name aliases are currently accepted.
_CAA_ISSUERS: Dict[str, Set[str]] = {
    "letsencrypt": {"letsencrypt.org"},
    # Sourced from the live ZeroSSL ACME directory's caaIdentities field.
    "zerossl": {"sectigo.com", "comodoca.com", "comodo.com", "trust-provider.com", "usertrust.com", "entrust.net", "affirmtrust.com"},
}


def _check_caa_for_domain(domain: str, ca_identifiers: Set[str], wildcard: bool, logger) -> bool:
    """Walk the DNS tree for *domain* checking CAA records (RFC 8659).

    Starts at the domain itself and moves up one label at a time until CAA
    records are found.  Returns ``True`` when the CA is permitted to issue
    (including when no CAA records exist anywhere up the tree) and ``False``
    when records are found that forbid it.

    Callers must ensure dnspython is available before calling this function.
    """
    import dns.exception  # type: ignore[import-untyped]
    import dns.resolver  # type: ignore[import-untyped]

    labels = domain.split(".")
    for i in range(len(labels)):
        check_name = ".".join(labels[i:])
        try:
            answers = dns.resolver.resolve(check_name, "CAA")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            # No CAA records at this level — walk up.
            continue
        except dns.exception.DNSException as exc:
            logger.debug(f"DNS error querying CAA for '{check_name}': {exc}")
            continue

        # CAA records found — parse issue / issuewild tags.
        issue_values: Set[str] = set()
        issuewild_values: Set[str] = set()
        for rdata in answers:
            tag_raw = rdata.tag
            tag = (tag_raw.decode("ascii") if isinstance(tag_raw, (bytes, bytearray)) else str(tag_raw)).lower()
            val_raw = rdata.value
            # Strip surrounding quotes, whitespace, and any parameters after ";".
            value = (val_raw.decode("ascii") if isinstance(val_raw, (bytes, bytearray)) else str(val_raw)).strip().strip('"').split(";")[0].strip().lower()
            if tag == "issue":
                issue_values.add(value)
            elif tag == "issuewild":
                issuewild_values.add(value)

        # RFC 8659 §4.1: for wildcard requests issuewild governs when present;
        # otherwise fall back to issue.  For non-wildcard, only issue governs.
        governing = issuewild_values if (wildcard and issuewild_values) else issue_values

        if not governing:
            # Records exist but carry only non-issuance tags (e.g. iodef).
            # RFC 8659 §4: no restriction on issuance.
            return True

        matched = ca_identifiers & governing
        if matched:
            logger.debug(f"CAA record at '{check_name}' permits issuance (matched: {', '.join(sorted(matched))}).")
            return True

        # No CA identifier found in the governing set → forbidden.
        logger.debug(
            f"CAA record at '{check_name}' for '{domain}' forbids issuance. "
            f"Governing values: {', '.join(sorted(governing))}. "
            f"Expected one of: {', '.join(sorted(ca_identifiers))}."
        )
        return False

    # No CAA records found at any level — issuance is open.
    return True


def check_caa_records(
    domains: List[str],
    acme_server: str,
    wildcard: bool,
    logger,
) -> Tuple[bool, List[str]]:
    """Check CAA DNS records to verify the CA may issue a certificate.

    For each domain the DNS tree is walked from the domain up to the root,
    stopping at the first level that carries CAA records.  Behaviour follows
    RFC 8659:

    * No CAA records found anywhere → issuance permitted.
    * CAA records exist but no ``issue`` / ``issuewild`` tags → no restriction.
    * ``issue`` / ``issuewild`` present and CA identifier not listed → forbidden.

    For wildcard requests ``issuewild`` records take precedence over ``issue``
    when both are present.  If only ``issue`` records exist they govern wildcard
    requests too (RFC 8659 §4.1).

    If *dnspython* is not installed the check is skipped and all domains pass.

    Args:
        domains:     Hostnames to check.  Leading ``*.`` wildcard prefixes are
                     stripped before the DNS lookup.
        acme_server: ACME server in use (``'letsencrypt'`` or ``'zerossl'``).
        wildcard:    ``True`` when requesting a wildcard certificate.
        logger:      Logger instance.

    Returns:
        ``(all_permitted, blocked)`` where *blocked* is the list of domains
        whose CAA records forbid the requested CA.
    """
    from importlib.util import find_spec

    if find_spec("dns") is None:
        logger.debug("dnspython is not installed; skipping CAA record check.")
        return True, []

    ca_identifiers = _CAA_ISSUERS.get(acme_server, set())
    if not ca_identifiers:
        logger.debug(f"No CAA identifiers configured for ACME server '{acme_server}'; skipping CAA check.")
        return True, []

    blocked: List[str] = []
    for domain in domains:
        bare = domain.lstrip("*.")
        if not _check_caa_for_domain(bare, ca_identifiers, wildcard, logger):
            blocked.append(domain)

    return not bool(blocked), blocked


def run_process_with_timeout(
    command: List[str],
    timeout: int,
    logger,
    env: Optional[Dict[str, str]] = None,
) -> int:
    """Run a process with a timeout and real-time stderr logging.

    Args:
        command: Command and arguments to execute
        timeout: Maximum time in seconds to wait for process completion
        logger: Logger object for output
        env: Environment variables for the process

    Returns:
        Process return code

    Raises:
        TimeoutExpired: If process exceeds timeout
    """
    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=env)
    start_time = time()

    try:
        while process.poll() is None:
            elapsed = time() - start_time
            remaining = timeout - elapsed

            if remaining <= 0:
                process.kill()
                raise TimeoutExpired(command[0], timeout)

            if process.stderr:
                # select() with a 2-second (or remaining-time) timeout avoids busy-waiting.
                # We read one line per iteration to keep the log stream flowing in real time
                # while still checking the timeout on each loop pass.
                rlist, _, _ = select([process.stderr], [], [], min(remaining, 2))
                if rlist:
                    for line in process.stderr:
                        logger.info(line.strip())
                        break

        return process.returncode
    except TimeoutExpired:
        process.kill()
        raise


def update_renewal_config_authenticator(
    renewal_dir: Union[str, Path],
    domain: str,
    new_authenticator: str,
    logger,
) -> bool:
    """Update the authenticator in a renewal .conf file.

    Args:
        renewal_dir: Path to renewal directory (containing .conf files)
        domain: Domain name (certificate name)
        new_authenticator: New authenticator value (e.g., 'dns-cloudflare', 'webroot')
        logger: Logger object for output

    Returns:
        True if updated successfully, False otherwise
    """
    renewal_path = Path(renewal_dir) / f"{domain}.conf"

    if not renewal_path.is_file():
        return False

    try:
        content = renewal_path.read_text()
        # flags=8 is re.MULTILINE — needed so ^ and $ match line boundaries, not
        # just start/end of the entire string (the renewal conf spans many lines).
        updated_content = sub(r"^authenticator\s*=\s*[^\n]*$", f"authenticator = {new_authenticator}", content, flags=8)

        if updated_content != content:
            renewal_path.write_text(updated_content)
            logger.info(f"Updated authenticator for {domain} to '{new_authenticator}'")
            return True
        return False
    except BaseException as e:
        logger.error(f"Failed to update renewal config for {domain}: {e}")
        return False
