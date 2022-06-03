#!/usr/bin/env python3

import argparse, traceback, os

import sys
sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/cli")
sys.path.append("/opt/bunkerweb/utils")
sys.path.append("/opt/bunkerweb/api")

from logger import log
from CLI import CLI

if __name__ == "__main__" :

    try :
        # Global parser
        parser = argparse.ArgumentParser(description="BunkerWeb Command Line Interface")
        subparsers = parser.add_subparsers(help="command", dest="command")
        
        # Unban subparser
        parser_unban = subparsers.add_parser("unban", help="remove a ban from the cache")
        parser_unban.add_argument("ip", type=str, help="IP address to unban")

        # Parse args
        args = parser.parse_args()

        # Instantiate CLI
        cli = CLI()
        
        # Execute command
        ret, err = False, "unknown command"
        if args.command == "unban" :
            ret, err = cli.unban(args.ip)

        if not ret :
            print("CLI command status : ❌ (fail)")
            print(err)
            os._exit(1)
        else :
            print("CLI command status : ✔️ (success)")
            print(err)
            os._exit(0)

    except SystemExit as se :
        sys.exit(se.code)
    except :
        print("❌ Error while executing bwcli : ")
        print(traceback.format_exc())
        sys.exit(1)
        
    sys.exit(0)
