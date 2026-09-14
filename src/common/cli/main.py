#!/usr/bin/env python3

from argparse import ArgumentParser
from os import _exit, getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from CLI import CLI, backup_preflight, render_capabilities

if __name__ == "__main__":
    logger = getLogger("CLI")

    try:
        # Global parser
        parser = ArgumentParser(description="BunkerWeb Command Line Interface")
        subparsers = parser.add_subparsers(help="command", dest="command")

        # Unban subparser
        parser_unban = subparsers.add_parser("unban", help="remove a ban from the cache")
        parser_unban.add_argument("ip", type=str, help="IP address to unban")
        parser_unban.add_argument("-service", type=str, help="service to unban from (default: unban globally)", default=None)

        # Ban subparser
        parser_ban = subparsers.add_parser("ban", help="add a ban to the cache")
        parser_ban.add_argument("ip", type=str, help="IP address to ban")

        ban_time = getenv("BAD_BEHAVIOR_BAN_TIME", "86400")
        if not ban_time.isdigit():
            ban_time = "86400"
        ban_time = int(ban_time)

        parser_ban.add_argument(
            "-exp",
            type=int,
            help=f"banning time in seconds (default: {ban_time}, set it to 0 for permanent ban)",
            default=ban_time,
        )
        parser_ban.add_argument(
            "-reason",
            type=str,
            help="reason for ban (default: manual)",
            default="manual",
        )
        parser_ban.add_argument(
            "-service",
            type=str,
            help="service that triggered the ban (default: bwcli). If specified with a valid service name, ban will be service-specific",
            default="bwcli",
        )

        # Bans subparser
        parser_bans = subparsers.add_parser("bans", help="list current bans")

        # Plugin list subparser
        parser_plugin_list = subparsers.add_parser("plugin_list", help="list all available plugins and their commands")

        # Capabilities subparser
        subparsers.add_parser("capabilities", help="show detected API, database client and backup volume capabilities")

        # Plugin subparser
        parser_plugin = subparsers.add_parser("plugin", help="execute a custom command from a plugin")
        parser_plugin.add_argument("plugin_id", type=str, help="the plugin id that you want to execute the command on")
        parser_plugin.add_argument("plugin_command", type=str, help="the command to execute on the plugin")
        parser_plugin.add_argument("-d", "--debug", action="store_true", help="sets the LOG_LEVEL env variable to DEBUG")

        # Custom configs subparser (talks to the control-plane API, see BWCLI_API_URL/API_URL)
        parser_cc = subparsers.add_parser("custom-configs", help="manage custom configs through the control-plane API")
        cc_subparsers = parser_cc.add_subparsers(help="custom-configs command", dest="custom_configs_command")

        parser_cc_import = cc_subparsers.add_parser("import", help="import custom configs from a directory")
        parser_cc_import.add_argument("directory", type=str, help="directory laid out as <type>/[<service>/]<name>.conf")
        parser_cc_import.add_argument("--draft", action="store_true", help="mark imported custom configs as draft")
        parser_cc_import.add_argument(
            "--method",
            choices=("manual", "api"),
            default="api",
            help="api (default): per-config upserts, never deletes, sets changed per config; manual: full replace of method=manual rows, mirrors scheduler folder adoption",
        )
        parser_cc_import.add_argument("--dry-run", action="store_true", help="validate and print without writing")

        parser_cc_list = cc_subparsers.add_parser("list", help="list custom configs")
        parser_cc_list.add_argument("--service", type=str, default=None, help="filter by service id")
        parser_cc_list.add_argument("--type", dest="config_type", type=str, default=None, help="filter by config type")

        # Parse args
        args, unknown_args = parser.parse_known_args()

        logger.debug(f"args : {args}")
        logger.debug(f"unknown_args : {unknown_args}")

        if args.command == "capabilities":
            print(render_capabilities())
            sys_exit(0)

        if args.command == "plugin" and args.plugin_id == "backup" and args.plugin_command in ("list", "save", "restore"):
            backup_directory = None
            if args.plugin_command == "save":
                backup_parser = ArgumentParser(add_help=False)
                backup_parser.add_argument("--directory", default=None)
                backup_directory = backup_parser.parse_known_args(unknown_args)[0].directory
            ok, error = backup_preflight(backup_directory)
            if not ok:
                logger.error(error)
                sys_exit(1)

        # Instantiate CLI
        cli = CLI()

        # Execute command
        ret, err = False, "unknown command"
        if args.command == "unban":
            ret, err = cli.unban(args.ip, args.service)
        elif args.command == "ban":
            ret, err = cli.ban(args.ip, args.exp, args.reason, args.service)
        elif args.command == "bans":
            ret, err = cli.bans()
        elif args.command == "plugin_list":
            ret, err = cli.plugin_list()
        elif args.command == "plugin":
            if args.debug:
                logger.setLevel("DEBUG")
            ret, err = cli.custom(args.plugin_id, args.plugin_command, debug=args.debug, extra_args=unknown_args)
        elif args.command == "custom-configs":
            if args.custom_configs_command == "import":
                ret, err = cli.custom_configs_import(args.directory, draft=args.draft, method=args.method, dry_run=args.dry_run)
            elif args.custom_configs_command == "list":
                ret, err = cli.custom_configs_list(service=args.service, config_type=args.config_type)
            else:
                ret, err = False, "unknown custom-configs command, use 'import' or 'list'"

        if not ret:
            logger.error(f"CLI command status : ❌ (fail)\n{err}")
            _exit(1)
        else:
            if err:
                err = f"\n{err}"

            logger.info(f"CLI command status : ✔️ (success){err}")
            _exit(0)

    except SystemExit as se:
        sys_exit(se.code)
    except:
        logger.error(f"Error while executing bwcli :\n{format_exc()}")
        sys_exit(1)
