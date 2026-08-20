#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from subprocess import DEVNULL, PIPE, Popen
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from common_utils import file_hash  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore
from certbot_concurrency import ensure_accounts_for_orphans
from letsencrypt_utils import (
    CERTBOT_BIN,
    DEPS_PATH,
    LETSENCRYPT_CACHE_PATH as CACHE_PATH,
    LETSENCRYPT_DATA_PATH as DATA_PATH,
    LETSENCRYPT_LOGS_DIR as LOGS_DIR,
    LETSENCRYPT_WORK_DIR as WORK_DIR,
    ZEROSSL_BOT_SCRIPT,
    account_id_for_cert,
    build_certbot_env,
    certbot_log_backup_flags,
    failed_renewal_cert,
    is_stale_account_line,
    is_zerossl_used_in_env,
    le_cache_write_lock,
    letsencrypt_cache_consistent,
    prepare_logs_dir,
    purge_stale_account,
    purge_stale_account_by_uri,
    resolve_certbot_entrypoint,
    stale_account_uri,
    stream_certbot,
    sanitize_and_persist,
)


def _live_cert_hashes() -> dict:
    """Map each live cert dir name -> SHA512 of its fullchain.pem (follows the live/->archive symlink)."""
    hashes = {}
    for fullchain in DATA_PATH.glob("live/*/fullchain.pem"):
        try:
            hashes[fullchain.parent.name] = file_hash(str(fullchain))
        except BaseException:
            hashes[fullchain.parent.name] = ""
    return hashes


LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper()

LOGGER = getLogger("LETS-ENCRYPT.RENEW")

LOGGER_CERTBOT = getLogger("LETS-ENCRYPT.RENEW.CERTBOT")
CERTBOT_TIMEOUT = 900  # 15 minutes max for a single certbot invocation
status = 0

try:
    # Check if we're using let's encrypt
    use_letsencrypt = False

    if getenv("MULTISITE", "no") == "no":
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
    else:
        for first_server in getenv("SERVER_NAME", "www.example.com").split():
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping renew...")
        sys_exit(0)

    prepare_logs_dir(LOGS_DIR, LOGGER)

    JOB = Job(LOGGER, __file__)

    cmd_env = build_certbot_env(JOB, DEPS_PATH)

    # Register an account for any CA whose renewal confs are orphaned and that has none left, so
    # the repoint inside sanitize_and_persist has somewhere to point. This job is the one that hits
    # the problem, since a deployment where every certificate already exists never runs issuance
    # and so never registers an account as a side effect of one.
    ensure_accounts_for_orphans(DATA_PATH, cmd_env.copy(), CERTBOT_BIN, LOG_LEVEL, WORK_DIR, LOGS_DIR, LOGGER)

    # Quarantine broken renewal confs before `certbot renew` reads them: one lineage whose name
    # disagrees with its filename makes the whole run fail to parse. Persists the cleaned tree so
    # the break can't be restored from the DB cache blob on the next tick.
    sanitized_lineages = sanitize_and_persist(JOB, DATA_PATH, LOGGER)

    # Every provider (route53 included) now persists its credentials in renewal/<cert>.conf via
    # dns_multi_credentials, so a plain `certbot renew` re-reads them uniformly — no per-provider
    # credential re-derivation is needed here anymore.

    acme_server = "zerossl" if is_zerossl_used_in_env() else "letsencrypt"
    certbot_entrypoint = resolve_certbot_entrypoint(
        acme_server,
        CERTBOT_BIN,
        ZEROSSL_BOT_SCRIPT,
        LOGGER,
        cmd_env=cmd_env,
        fallback_to_certbot=True,
    )
    certbot_bin = certbot_entrypoint[0]
    if acme_server == "zerossl" and certbot_bin != CERTBOT_BIN:
        LOGGER.info("Using zerossl-bot wrapper for certificate renewal.")

    # Snapshot live cert fingerprints so we can tell whether `certbot renew` actually renewed
    # anything (it returns 0 either way). Only an actual renewal should trigger delivery/reload.
    before_hashes = _live_cert_hashes()

    process = Popen(
        [
            certbot_bin,
            "renew",
            "-n",
            "--no-random-sleep-on-renew",
            "--config-dir",
            DATA_PATH.as_posix(),
            "--work-dir",
            WORK_DIR,
            "--logs-dir",
            LOGS_DIR,
            *certbot_log_backup_flags(cmd_env),
        ]
        + (["-v"] if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG" else []),
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=cmd_env,
    )
    # `certbot renew` covers every lineage in one run and pins no --account, so unlike issuance
    # there is no local account id to blame when the CA rejects one. Two ways to identify it, both
    # needed: the "not found" phrasing embeds the account URI, which certbot also stores in that
    # account's regr.json, while the "deactivated" phrasing names no account at all and has to be
    # resolved through the lineage certbot reports on the same line.
    # Without this, a deployment whose certificates all exist never runs issuance, never detects
    # the rejection, and every renewal fails forever with no recovery path.
    stale_account_uris = set()
    stale_account_certs = set()

    def watch_stale_account(line: str) -> None:
        if not is_stale_account_line(line):
            return
        uri = stale_account_uri(line)
        if uri:
            stale_account_uris.add(uri)
            return
        cert_name = failed_renewal_cert(line)
        if cert_name:
            stale_account_certs.add(cert_name)
        else:
            LOGGER.error(f"The CA rejected the ACME account but named neither it nor a certificate, so it cannot be replaced automatically: {line}")

    if not stream_certbot(process, LOGGER_CERTBOT, CERTBOT_TIMEOUT, watch_stale_account):
        LOGGER.error(f"certbot renew timed out after {CERTBOT_TIMEOUT}s, killing process.")
        status = 2

    if process.returncode and process.returncode != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")

    # `certbot renew` exits 0 whether or not it renewed anything. Compare cert fingerprints to
    # detect a real renewal; only then signal a reload (status=1) so the renewed cert is delivered
    # to the instances. Without this, a successful renewal stayed status=0 and the new cert was
    # cached to the DB but never pushed to instances until an unrelated reload happened.
    renewed = False
    if status == 0:
        after_hashes = _live_cert_hashes()
        renewed = after_hashes != before_hashes
        if renewed:
            LOGGER.info("Detected renewed certificate(s); will deliver them to the instances.")
            status = 1

    # Recover in this run, not the next one. The persist below refuses an inconsistent tree, so a
    # purge left unrepaired would never reach the DB row, the dead account would be restored from
    # it on the next tick, and the run would purge it again forever.
    if stale_account_uris or stale_account_certs:
        purged = False
        for uri in sorted(stale_account_uris):
            purged = purge_stale_account_by_uri(DATA_PATH, uri, LOGGER) or purged
        for account_id in sorted({account_id_for_cert(DATA_PATH, cert_name) for cert_name in stale_account_certs} - {""}):
            purged = purge_stale_account(DATA_PATH, account_id, LOGGER) or purged
        if purged:
            ensure_accounts_for_orphans(DATA_PATH, cmd_env.copy(), CERTBOT_BIN, LOG_LEVEL, WORK_DIR, LOGS_DIR, LOGGER)
            sanitized_lineages = sorted(set(sanitized_lineages) | set(sanitize_and_persist(JOB, DATA_PATH, LOGGER)))

    # Save Let's Encrypt data to db cache.
    # Guards: only re-cache if the initial restore succeeded AND we actually have live
    # certs on disk. Without these guards, a failed restore leaves DATA_PATH empty
    # (rmtree runs before extraction in Job.restore_cache) and a blind cache_dir() call
    # would overwrite the good DB row with the empty post-rmtree state, losing the certs
    # from both disk and DB.
    if not JOB.restore_ok:
        LOGGER.error("Skipping db cache update: initial cache restore failed, refusing to overwrite good DB state with current disk state.")
        status = 2
    elif not sanitized_lineages and (not DATA_PATH.is_dir() or not any(DATA_PATH.glob("live/*/fullchain.pem"))):
        # Skip the "no live certs" persist only when nothing was sanitized; if a broken lineage was
        # quarantined we must still write the cleaned tree back so it can't be restored again.
        LOGGER.warning("Skipping db cache update: no live certificates found under DATA_PATH/live/*/fullchain.pem.")
    else:
        # Refuse to re-cache when renewal/ references account IDs that are missing from accounts/.
        # That snapshot would self-propagate certbot AccountNotFound errors across every renew.
        consistent, reason = letsencrypt_cache_consistent(DATA_PATH)
        if not consistent:
            LOGGER.error(
                "Skipping db cache update to avoid persisting an inconsistent Let's Encrypt state "
                f"({reason}). The DB cache row is left untouched. Renewals for the affected certificates fail until an "
                "account exists for their CA; the next run repoints them automatically once one does."
            )
            # If certbot itself succeeded, the fresh certs are already on disk — signal a reload
            # (ret=1) so nginx picks them up. Persistence failure is logged separately above; do
            # not escalate to status=2 here, otherwise JobScheduler suppresses the reload and the
            # newly-renewed certs sit unused until the next restart.
            if status == 0:
                status = 1
        else:
            # Serialize this cache writer with other Let's Encrypt cache users.
            with le_cache_write_lock():
                cached, err = JOB.cache_dir(DATA_PATH)
            if not cached:
                LOGGER.error(f"Error while saving Let's Encrypt data to db cache : {err}")
            else:
                LOGGER.info("Successfully saved Let's Encrypt data to db cache")
                try:
                    import_summary = JOB.db.import_legacy_certbot_certificates()
                    if import_summary.get("errors"):
                        LOGGER.warning(f"Certificate inventory sync completed with errors: {import_summary['errors']}")
                except Exception as exc:
                    LOGGER.warning(f"Unable to sync the certificate inventory: {exc}")
                # Only when a cert was actually renewed this run (status==1): deliver the renewed LE
                # cache to every live instance NOW, directly. Same whole-/var/cache push + /reload the
                # worker's reload path performs on ret==1 (src/worker/tasks.py:81), issued here so it
                # CANNOT be silently dropped by the shared 10s bw:reload_pending debounce that any other
                # reload-flagged job finishing in the same window can steal. On any failure we leave
                # status==1 so the worker's debounced reload path still runs as a fallback. We hold
                # le_cache_write_lock around the read so push-configs cannot rmtree/rebuild the tree mid-send.
                if status == 1:
                    try:
                        token = getenv("API_TOKEN") or None
                        instances = [i for i in JOB.db.get_instances(with_credential=True) if i.get("status") != "down"]
                        if instances:
                            api_caller = ApiCaller([API.from_instance(i, token=token) for i in instances])
                            with le_cache_write_lock():
                                pushed = bool(api_caller.send_files(str(CACHE_PATH.parent), "/cache"))
                            if not pushed:
                                LOGGER.error("Failed to push renewed Let's Encrypt cache to one or more instances; leaving worker reload path as fallback")
                            else:
                                test = "no" if getenv("DISABLE_CONFIGURATION_TESTING", "no").lower() == "yes" else "yes"
                                sent = api_caller.send_to_apis("POST", f"/reload?test={test}")[0]
                                if not sent:
                                    LOGGER.error(
                                        "Renewed LE cache pushed but reload request failed on at least one instance; leaving worker reload path as fallback"
                                    )
                                else:
                                    LOGGER.info("Successfully delivered renewed Let's Encrypt cache and reloaded instances")
                                    status = 0  # delivered here; don't double-fire the debounced worker reload
                        else:
                            LOGGER.info("No live instances registered; leaving delivery to the reload path")
                    except BaseException as e:
                        LOGGER.error(f"Exception while delivering renewed LE cache to instances: {e}; falling back to reload path")
                        # status stays 1 → the worker's debounced reload path retries the push+reload
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-renew.py :\n{e}")

sys_exit(status)
