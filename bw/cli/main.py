#!/usr/bin/env python3

from argparse import ArgumentParser
from os import _exit
from sys import exit as sys_exit, path
from traceback import format_exc

path.append("/opt/bunkerweb/deps/python")
path.append("/opt/bunkerweb/cli")
path.append("/opt/bunkerweb/utils")
path.append("/opt/bunkerweb/api")

from logger import setup_logger
from CLI import CLI

if __name__ == "__main__":
    logger = setup_logger("CLI", "INFO")

    try:
        # Global parser
        parser = ArgumentParser(description="BunkerWeb Command Line Interface")
        subparsers = parser.add_subparsers(help="command", dest="command")

        # Unban subparser
        parser_unban = subparsers.add_parser(
            "unban", help="remove a ban from the cache"
        )
        parser_unban.add_argument("ip", type=str, help="IP address to unban")

        # Parse args
        args = parser.parse_args()

        # Instantiate CLI
        cli = CLI()

        # Execute command
        ret, err = False, "unknown command"
        if args.command == "unban":
            ret, err = cli.unban(args.ip)

        if not ret:
            logger.error(f"CLI command status : ❌ (fail)\n{err}")
            _exit(1)
        else:
            logger.info(f"CLI command status : ✔️ (success)\n{err}")
            _exit(0)

    except SystemExit as se:
        sys_exit(se.code)
    except:
        logger.error(f"Error while executing bwcli :\n{format_exc()}")
        sys_exit(1)

    sys_exit(0)
