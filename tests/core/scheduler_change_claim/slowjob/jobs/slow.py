#!/usr/bin/env python3
from os import getenv
from sys import path as sys_path, exit as sys_exit
from time import sleep

sys_path.append("/usr/share/bunkerweb/utils")

from logger import getLogger  # type: ignore

LOGGER = getLogger("SLOWJOB")
LOGGER.info(f"slow job start, SERVER_NAME={getenv('SERVER_NAME')}")
sleep(25)
LOGGER.info("slow job end")
sys_exit(0)
