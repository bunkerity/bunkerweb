#!/usr/bin/env python3
"""`bwcli plugin backup preflight <version>` -- can this installation go back to <version>?

Read-only. It opens the database for reading -- deliberately NOT through `Database()`, whose
constructor probes the connection with a `CREATE TABLE`/`DROP TABLE` pair -- counts rows, looks at
the backup directory and asks the job broker what is in flight. It issues no DDL and no
INSERT/UPDATE/DELETE, creates no database, and writes nothing to the broker. `--execute` is
refused on purpose: this command reports, it never downgrades.
"""

from argparse import ArgumentParser
from json import dumps
from os.path import join, sep
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import LOGGER  # noqa: E402
from downgrade import EXIT_CODES, REFUSE, preflight, render_report  # noqa: E402

status = 0

try:
    parser = ArgumentParser(description="BunkerWeb's backup plugin downgrade preflight command line interface")
    parser.add_argument("target", type=str, help="the version this installation would go back to (e.g. 1.6.12)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON instead of a table")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="not implemented: this command never downgrades",
    )

    args = parser.parse_args()

    if args.execute:
        LOGGER.error("The preflight never downgrades: --execute is not implemented, see lot D of the controlled-downgrade design")
        sys_exit(1)

    report = preflight(args.target)

    if args.json:
        print(dumps(report, default=str, sort_keys=True))
    else:
        LOGGER.info(render_report(report))

    status = EXIT_CODES.get(report["verdict"], EXIT_CODES[REFUSE])
except SystemExit as se:
    status = se.code
except BaseException as e:
    LOGGER.error(f"Error while executing backup preflight command: {e}")
    status = 1

sys_exit(status)
