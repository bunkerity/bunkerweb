#!/usr/bin/env python3
"""`bwcli plugin backup quiesce <version>` -- hold the writers still, reversibly.

Takes the single downgrade hold in the job broker, proves the API actually observes it, waits
for the job queue to drain, then keeps holding until the operator stops it. Stopping it --
Ctrl-C, SIGTERM, a failure anywhere in the middle -- gives the system back; so does the TTL, if
the holder dies without getting the chance.

It never downgrades anything. Lot D runs the downgrade itself, in another shell, while this one
holds.
"""

from argparse import ArgumentParser
from os.path import join, sep
from signal import SIGINT, SIGTERM, signal
from sys import exit as sys_exit, path as sys_path, stdin
from time import sleep

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import LOGGER  # noqa: E402
from downgrade import (
    DEFAULT_HOLD_TTL,
    acquire_hold,
    broker_client,
    drain,
    hold_observed_by_api,
    hold_status,
    hold_ttl,
    refresh_hold,
    release_hold,
)  # noqa: E402

status = 0
client = None
handle = ""


def _stop(signum, _frame):
    """Turn a signal into an ordinary exit so the `finally` below actually runs."""
    LOGGER.info(f"Interrupted by signal {signum}, releasing the downgrade hold ...")
    raise SystemExit(0)


try:
    parser = ArgumentParser(description="BunkerWeb's backup plugin downgrade quiescence command line interface")
    parser.add_argument("target", nargs="?", default="", type=str, help="the version the downgrade is heading for, recorded in the hold")
    parser.add_argument("--status", action="store_true", help="print who holds the downgrade hold and exit")
    parser.add_argument("--release", action="store_true", help="release the hold, including one whose holder is gone")
    parser.add_argument("--force", action="store_true", help="with --release: skip the confirmation (for scripts; releasing a live hold unfreezes the fleet)")
    parser.add_argument("--ttl", type=int, default=DEFAULT_HOLD_TTL, help=f"seconds before an unrefreshed hold expires by itself (default: {DEFAULT_HOLD_TTL})")
    parser.add_argument("--drain-timeout", type=float, default=120.0, help="seconds to wait for the job queue to go idle (default: 120)")
    parser.add_argument("--verify-timeout", type=float, default=15.0, help="seconds to wait for the API to report the hold (default: 15)")

    args = parser.parse_args()

    client = broker_client()

    if args.status:
        held = hold_status(client)
        LOGGER.info(f"Downgrade hold: {held}" if held else "No downgrade hold is in place")
        sys_exit(0)

    if args.release:
        held = hold_status(client)
        if not held:
            LOGGER.info("No downgrade hold is in place, nothing to release")
            sys_exit(0)
        # This is the only release path an operator types, and it deletes the key unconditionally
        # -- the byte-comparing anti-steal guard protects the programmatic path, not this one. A
        # stray `--release` while lot D is mid-migration puts the fleet back into service under a
        # half-downgraded schema, so a live hold has to be confirmed rather than assumed stale.
        remaining = hold_ttl(client)
        if not args.force:
            if not stdin.isatty():
                LOGGER.error(
                    f"Refusing to release a live downgrade hold ({remaining}s left, taken at {held.get('started_at')} for "
                    f"{held.get('target')}) with no terminal to confirm on: re-run with --force if that is really what you want"
                )
                sys_exit(1)
            prompt = (
                f"A downgrade hold for {held.get('target')} was taken at {held.get('started_at')} and has {remaining}s left.\n"
                "Releasing it lets the scheduler, autoconf and the UI write again immediately.\n"
                f"Type the target version ({held.get('target')}) to confirm, anything else to abort: "
            )
            if input(prompt).strip() != (held.get("target") or ""):
                LOGGER.info("Aborted, the downgrade hold is still in place")
                sys_exit(1)

        release_hold(client, "", force=True)
        LOGGER.warning(f"Released the downgrade hold taken at {held.get('started_at')} for {held.get('target')}: the fleet can be written to again")
        sys_exit(0)

    if not args.target:
        LOGGER.error("A target version is required to take the hold (or use --status / --release)")
        sys_exit(1)

    signal(SIGINT, _stop)
    signal(SIGTERM, _stop)

    handle, existing = acquire_hold(client, args.target, ttl=args.ttl)
    if not handle:
        LOGGER.error(
            f"A downgrade hold is already in place (taken at {(existing or {}).get('started_at')} for {(existing or {}).get('target')}), refusing to interleave"
        )
        sys_exit(1)

    LOGGER.info(f"Downgrade hold taken for {args.target}; it expires by itself in {args.ttl}s if this process dies")

    # The key alone holds nothing: what stops the writers is the API reporting read-only, which
    # every one of them polls. If the API cannot see the hold -- no broker in its environment,
    # a netsplit, an image without it -- the fleet is still writable and this must refuse rather
    # than let a downgrade run against a live system.
    observed, reason = hold_observed_by_api(timeout=args.verify_timeout)
    if not observed:
        LOGGER.error(f"The API does not report the fleet as read-only ({reason}): the hold is not being honoured, refusing to proceed")
        sys_exit(1)

    LOGGER.info("The API reports the fleet read-only: scheduler dispatch, autoconf pushes and UI writes are held")
    # Say the gap out loud, every time, right where the operator is about to start a downgrade.
    # Every API write guard tests `Database.readonly`, an attribute fixed when the API process built
    # its Database (src/common/db/Database.py:163) from DATABASE_URI_READONLY. This hold changes
    # what GET /system/readonly REPORTS, which is what the HTTP pollers act on; it does not and
    # cannot change that attribute inside the running API. `POST /services` from a token holder
    # therefore still lands (routers/services.py -> save_config -> db_methods/config_save.py:422).
    LOGGER.warning(
        "NOT held: direct writes to the API itself. A token holder -- automation, a CI job, a second operator with curl -- can "
        "still mutate the database through the API while this hold is in place. Stop or firewall those callers before downgrading."
    )

    drained, state = drain(client, timeout=args.drain_timeout)
    if not drained:
        LOGGER.error(f"The job queue did not go idle within {args.drain_timeout}s ({state}), releasing the hold rather than downgrading on top of it")
        sys_exit(1)

    LOGGER.info("Writers are idle. Run the downgrade now, in another shell; press Ctrl-C here to give the system back.")

    # Refresh well inside the TTL so a slow downgrade never loses the hold mid-way, while a dead
    # holder still expires within it. Re-checking observability on every lap is what catches the
    # hold lapsing silently: the operator sees the message below, not a fleet that quietly
    # started writing again.
    interval = max(1, args.ttl // 3)
    while refresh_hold(client, handle, ttl=args.ttl):
        observed, reason = hold_observed_by_api(timeout=args.verify_timeout)
        if not observed:
            LOGGER.error(f"The fleet is no longer held read-only ({reason}): stop the downgrade, the system may be taking writes again")
            status = 1
            break
        sleep(interval)
    else:
        LOGGER.error("The downgrade hold was lost (it expired, or someone released it): the system may be taking writes again")
        status = 1
        handle = ""
except SystemExit as se:
    status = se.code if isinstance(se.code, int) else 1
except BaseException as e:
    LOGGER.error(f"Error while executing backup quiesce command: {e}")
    status = 1
finally:
    if client is not None and handle:
        if release_hold(client, handle):
            LOGGER.info("Downgrade hold released, the system is running again")
        else:
            LOGGER.warning("The downgrade hold was already gone, nothing to release")

sys_exit(status)
