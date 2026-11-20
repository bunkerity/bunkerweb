#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Wait for the backup plugin's job queue to drain before a downgrade preflight runs.

`downgrade_finds_the_shipped_manifest` in `tests/core/backup.yml` reds whenever a job happens to
still be in flight when the harness reaches it (push 15, Autoconf CI): `check_writers`
(`src/common/core/backup/downgrade.py:350-379`) refuses the preflight on ANY job queued or in
flight, by design -- the product is right to refuse, the harness was wrong not to wait it out.

This polls `bwcli plugin backup preflight <target>` -- the exact read-only `check_writers` the
mutating-adjacent `downgrade` command also runs, and which its own module docstring says issues
no DDL/DML and writes nothing to the broker -- until its "writers" row stops being refused (an
in-flight job, a pending reload, or an undelivered ack), or the bound below is spent. It cannot
mask a real refusal from a DIFFERENT check: the real test right after this one re-runs the full
preflight for real and asserts on it exactly as it did before this script existed.

Timeout and poll interval mirror `downgrade.py`'s own bounded `drain()`, which answers the
identical "is the queue idle?" question for the same reason.
"""

from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from time import monotonic, sleep

# `core.py` gets `utils` on its path for free because it is invoked as `python3 tests/core.py`
# (sys.path[0] becomes `tests`); this script lives two directories deeper, so it has to add the
# same `tests` directory itself.
sys_path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils import run_command  # noqa: E402
import utils.logger  # noqa: E402,F401

# The exact check-name/verdict-glyph pair `render_report` prints for a refused "writers" row
# (src/common/core/backup/downgrade.py:929-931,912). Matching this instead of the detail
# sentence covers all three refusal reasons check_writers can print (queued/in-flight, a
# pending reload, an undelivered ack) without pinning the wait to one of their exact wordings.
REFUSED_WRITERS = "❌ writers"
TIMEOUT = 120.0
POLL = 2.0

LOGGER = getLogger("BACKUP_DRAIN")


def main() -> int:
    parser = ArgumentParser(description="Poll the backup plugin's preflight until the job queue is idle.")
    parser.add_argument("integration", help="Docker, Linux, Autoconf, Kubernetes or All-in-one")
    parser.add_argument("target", help="the downgrade target version to pass to the preflight, e.g. 1.6.14")
    args = parser.parse_args()

    deadline = monotonic() + TIMEOUT
    output = ""
    while True:
        _, output = run_command(LOGGER, args.integration, f"plugin backup preflight {args.target}")
        if REFUSED_WRITERS not in output:
            print(f"writers are idle, proceeding: {output}")
            return 0
        if monotonic() >= deadline:
            break
        sleep(POLL)

    print(f"job queue never drained within {TIMEOUT}s, last preflight output:\n{output}")
    return 1


if __name__ == "__main__":
    sys_exit(main())
