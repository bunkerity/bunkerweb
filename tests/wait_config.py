#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Wait until the configuration a restart dispatched has actually been pushed.

Since 1.7 the scheduler does not push the configuration itself: it queues push-configs on
the broker and returns as soon as the job is accepted. A stack whose containers report
healthy can therefore still be serving the previous action's configuration, which makes
any assertion that follows a race.

The worker records every run in bw_jobs_runs. `--mark` stores how many push-configs runs
exist just before the stack is restarted, and the default mode waits for one more than that,
with no change left pending. Counting alone would be satisfied by a run the previous action
triggered, or by the push a restart does on boot before it has read the new environment.
"""

from argparse import ArgumentParser
from logging import CRITICAL, getLogger
from re import search
from sys import exit as sys_exit, path
from time import sleep

path.append("tests")

from redis import Redis  # noqa: E402

import utils.logger  # noqa: E402,F401
from utils import execute_query  # noqa: E402

LOGGER = getLogger("WAIT_CONFIG")

# A stack that is down is expected here, and the query helper reports it as an error before
# exiting. Polling through this logger keeps that out of the CI output.
QUIET = getLogger("WAIT_CONFIG_QUIET")
QUIET.setLevel(CRITICAL)

REDIS_KEY = "push_configs_runs"
QUERY = "SELECT COUNT(*) FROM bw_jobs_runs WHERE job_name = 'push-configs'"
# What autoconf's own readiness gate reads: a change is pending until the run that applied
# it acknowledges it. Bare column names rather than `= 1`, which PostgreSQL rejects on a
# boolean.
# Any job, not just push-configs: a spec can be about what a job produced (a downloaded
# blocklist, a generated certificate), and the worker runs those asynchronously too.
ALL_RUNS_QUERY = "SELECT COUNT(*) FROM bw_jobs_runs"
# `certificates_changed` belongs here for a reason the others do not have: the provider jobs
# (self-signed, custom-cert, letsencrypt) and the job that materializes what they decided
# (deploy-certificates) are dispatched in the same batch and run in parallel, so the deploy
# routinely runs first and ships material the provider is about to detach. The provider raises
# this flag, the scheduler re-dispatches the deploy, and only then does the instance stop
# serving the old certificate. Ignore it and a spec that turns GENERATE_SELF_SIGNED_SSL off
# asserts against a service that is still on HTTPS.
PENDING_QUERY = (
    "SELECT (SELECT COUNT(*) FROM bw_plugins WHERE config_changed) + "
    "(SELECT COUNT(*) FROM bw_metadata WHERE custom_configs_changed OR external_plugins_changed "
    "OR pro_plugins_changed OR instances_changed OR certificates_changed)"
)


def query_count(integration: str, database: str, query: str) -> int:
    try:
        # get_container() exits the process when the stack is down, which is a normal
        # state here: the mark is taken before the restart, and the first polls can land
        # before the database is back.
        exit_code, output = execute_query(QUIET, integration, database, query)
    except SystemExit:
        return -1

    if exit_code != 0:
        LOGGER.debug(f"Query failed ({exit_code}): {output}")
        return -1

    # Every client formats its output differently; the count is the only number in it.
    match = search(r"\d+", output)
    return int(match.group()) if match else -1


if __name__ == "__main__":
    parser = ArgumentParser(prog="Wait for config", description="Wait for the dispatched configuration to reach the instances")
    parser.add_argument("integration", type=str, choices=["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"])
    parser.add_argument("--mark", action="store_true", help="Record the current number of runs instead of waiting for a new one")
    parser.add_argument("--settle", type=int, default=5, help="Seconds the pushed and no-pending state must hold before it counts as settled")
    parser.add_argument("--timeout", type=int, default=120)
    ARGS = parser.parse_args()

    redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)
    database = redis_client.get("database") or "sqlite"

    if ARGS.mark:
        # A stack that is down, or a database that was just dropped, marks zero: the next
        # push then satisfies the wait, which is what a fresh stack should do anyway.
        runs = query_count(ARGS.integration, database, QUERY)
        redis_client.set(REDIS_KEY, max(runs, 0))
        LOGGER.info(f"📤 {max(runs, 0)} push-configs runs before the restart")
        sys_exit(0)

    previous = int(redis_client.get(REDIS_KEY) or 0)
    seen = -1
    settled = 0

    for _ in range(ARGS.timeout):
        runs = query_count(ARGS.integration, database, QUERY)
        pending = query_count(ARGS.integration, database, PENDING_QUERY)
        all_runs = query_count(ARGS.integration, database, ALL_RUNS_QUERY)

        # A full clean drops the database, so fewer runs than the mark means a fresh one
        # rather than a job running backwards.
        if 0 <= runs < previous:
            previous = 0

        # A restart used to push twice, and releasing on the first handed the test the
        # configuration it was supposed to be replacing. The scheduler no longer re-dispatches
        # its own boot save (main.py seeds the polling baseline), so it is one push per restart
        # now -- but the wait still requires a push of *this* restart, no change waiting to be
        # applied, and both holding still for a moment: the flags are set after the push, so a
        # single clear reading proves nothing, and a job that lands late moves the run count.
        if runs > previous and pending == 0:
            if all_runs != seen:
                seen = all_runs
                settled = 0
            else:
                settled += 1

            if settled >= ARGS.settle:
                redis_client.set(REDIS_KEY, runs)
                LOGGER.info(f"📤 Configuration pushed and jobs quiet ✅ ({runs} push-configs runs, {all_runs} job runs)")
                sys_exit(0)

        sleep(1)

    LOGGER.error(f"📤 No settled push-configs run in the {ARGS.timeout} seconds after the restart")
    sys_exit(1)
