#!/usr/bin/env python3
"""`bwcli plugin backup downgrade --execute <version>` -- take this installation back, in place.

The third and last downgrade command, and the only one that mutates. `preflight` reports,
`quiesce` holds the writers still, this one migrates. It refuses unless all of the following are
true, and it refuses BEFORE touching anything:

* `--execute` was passed and the operator confirmed (or `--yes` on a terminal-less run);
* a `quiesce` hold is in place **for this same target**, in another shell;
* the read-only preflight -- re-run here, not trusted from an earlier shell -- says
  `in_place_possible`;
* the compatibility manifest marks this exact (from, to, engine) `in_place_tested` and names the
  Alembic revision to land on.

Then it takes a backup of the database as it stands and runs the migration. Any failure after
that point restores that backup, so every outcome leaves a startable installation.

The file is deliberately not called `downgrade.py`: `bwcli` puts this directory first on
`sys.path`, ahead of the plugin root, so a module of that name here would shadow the
`downgrade.py` library it imports.
"""

from argparse import ArgumentParser
from json import dumps
from os.path import join, sep
from sys import exit as sys_exit, path as sys_path, stdin

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import LOGGER  # noqa: E402
from downgrade import EXECUTE_EXIT_CODES, REFUSE, REFUSED, execute_downgrade, preflight, render_execute_report, render_report  # noqa: E402

status = 0

try:
    parser = ArgumentParser(description="BunkerWeb's backup plugin in-place downgrade command line interface")
    parser.add_argument("target", type=str, help="the version to go back to (e.g. 1.6.14)")
    parser.add_argument("--execute", action="store_true", help="actually downgrade; without it this only reports what the preflight found")
    parser.add_argument("--yes", action="store_true", help="with --execute: skip the confirmation prompt (for scripts)")
    parser.add_argument(
        "--json", action="store_true", help="print the result as JSON instead of a report (branch on `verdict` / `end_state` rather than on the exit code)"
    )

    args = parser.parse_args()

    if not args.execute:
        # The safe half of the same command: say what would happen, change nothing. An operator
        # who typed `downgrade 1.6.14` and meant it types it again with --execute.
        report = preflight(args.target)
        if args.json:
            print(dumps(report, default=str, sort_keys=True))
        else:
            LOGGER.info(render_report(report))
            LOGGER.warning(
                f"Nothing was changed. Add --execute to actually downgrade to {args.target}, once `bwcli plugin backup quiesce {args.target}` is holding in another shell."
            )
        # PO-4, option (b): exit 0 for `restore_only`, non-zero for `refuse`. A legitimate
        # `restore_only` answer should not make a pipeline think the command failed -- but
        # `refuse` means a half-finished migration, a database-vs-code version mismatch or jobs
        # still in flight, and a pipeline gating on this command must not sail past that.
        # `preflight` keeps lot C's stricter contract (2 for restore_only) unchanged.
        sys_exit(EXECUTE_EXIT_CODES[REFUSED] if report["verdict"] == REFUSE else 0)

    confirmed = args.yes
    if not confirmed:
        # Same shape as `quiesce --release`: a destructive action with no terminal to confirm on
        # refuses rather than assuming consent.
        if not stdin.isatty():
            LOGGER.error("Refusing to downgrade with no terminal to confirm on: re-run with --yes if that is really what you want")
            sys_exit(EXECUTE_EXIT_CODES[REFUSED])
        # The prompt used to point at "the data the preflight listed", which excluded the two
        # largest losses: the columns dropped from surviving tables (a row count does not move
        # when a table loses a column) and the tables the manifest deliberately does not count.
        # `silent_losses` is exactly those, so they are read out here rather than left unsaid.
        report = preflight(args.target)
        LOGGER.info(render_report(report))
        # Same gate as `render_report`: on a `refuse` verdict the report deliberately suppresses
        # this block, so printing it here would point at "no check above counts" for a block that
        # is not above -- and describe destruction for a downgrade that is not going to run.
        unsaid = "" if report["verdict"] == REFUSE else "".join(f"  - {line}\n" for line in report.get("silent_losses") or ())
        answer = input(
            f"This will migrate the database in place to {args.target} and DESTROY the 1.7-only data listed above.\n"
            + (f"It ALSO destroys the following, which no check above counts:\n{unsaid}" if unsaid else "")
            + "A backup is taken first and restored automatically if the migration fails.\n"
            f"Type the target version ({args.target}) to confirm, anything else to abort: "
        )
        confirmed = answer.strip() == args.target
        if not confirmed:
            LOGGER.info("Aborted, nothing was changed")
            sys_exit(EXECUTE_EXIT_CODES[REFUSED])

    result = execute_downgrade(args.target, confirmed=confirmed)

    if args.json:
        print(dumps(result, default=str, sort_keys=True))
    else:
        LOGGER.info(render_execute_report(result))

    status = EXECUTE_EXIT_CODES.get(result["end_state"], EXECUTE_EXIT_CODES[REFUSED])
except SystemExit as se:
    status = se.code if isinstance(se.code, int) else 1
except BaseException as e:
    LOGGER.error(f"Error while executing backup downgrade command: {e}")
    status = 1

sys_exit(status)
