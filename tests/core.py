#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from logging import getLogger
from math import ceil
from os.path import join
from pathlib import Path
from time import sleep
from typing import Optional

from redis import Redis
from yaml import safe_load

from utils import resolve_env_placeholders, get_logs
import utils.logger  # noqa: F401
from utils.action import is_derived_from_selenium_action, parse_action

# Handlers
from core_handlers import (
    redis_handler,
    database_handler,
    bwcli_handler,
    tool_handler,
    export_handler,
    http_string_handler,
    http_path_handler,
    http_status_handler,
    http_header_handler,
    http_ssl_handler,
    selenium_xpath_handler,
    selenium_cookie_handler,
    limit_handler,
)

LOGGER = getLogger("CORE_TEST")

parser = ArgumentParser(prog="Tests runner", description="Run a test.")
parser.add_argument("test", type=str, help="Test to run")
integration_action = parser.add_argument(
    "integration", type=str, help="Integration to test", choices=["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"]
)
ARGS = parser.parse_args()

test_split = ARGS.test.split(";")
filename = test_split[0]
action_str = test_split[1]

LOGGER.info(f"🚀 Running {filename} / {action_str} test")

file_path = join("tests", "core", f"{filename}.yml")

content = Path(file_path).read_text()

# Replace ${VAR} patterns with the corresponding environment variable
content = resolve_env_placeholders(content)

data = safe_load(content)

action = parse_action(
    LOGGER,
    integration_action.choices,
    ARGS.integration,
    action_str,
    data["actions"][action_str],
)

if ARGS.integration not in action.integrations:
    LOGGER.error(f"Action {action_str} is not compatible with integration {ARGS.integration}")
    exit(1)

redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)

resp = redis_client.ping()
if not resp:
    LOGGER.error("Redis server is not running")
    exit(1)

delay: float = action.delay
wait_duration = delay

INTEGRATION_MIN_DELAY = {
    "Docker": 0.0,
    "Linux": 0.0,
    "Autoconf": 60.0,
    "Kubernetes": 90.0,
    "All-in-one": 0.0,
}

if ARGS.integration in ("Autoconf", "Kubernetes") and delay == 0.0 and wait_duration < INTEGRATION_MIN_DELAY[ARGS.integration]:
    LOGGER.info(f"🔍 We need at least a {INTEGRATION_MIN_DELAY[ARGS.integration]} seconds delay to let the {ARGS.integration} stack be ready...")
    wait_duration = INTEGRATION_MIN_DELAY[ARGS.integration]

full_clean = redis_client.get("full_clean")
full_clean = int(full_clean) if full_clean is not None else 1

annotations = data.get("annotations", {}) | action.annotations
if wait_duration > 0:
    LOGGER.info(f"⏲ Waiting {wait_duration} seconds ...")
    last_test: Optional[str] = redis_client.get("last_test")
    x = 0
    while x < ceil(wait_duration):
        LOGGER.debug(f"⏲ {wait_duration - x} seconds left ...")
        if ARGS.integration in ("Autoconf", "Kubernetes") and delay == 0.0:
            scheduler_logs = get_logs(LOGGER, ARGS.integration, last_test, log_from="scheduler")
            latest_log = scheduler_logs[-1]
            LOGGER.debug(f"Scheduler latest log: {latest_log}")
            scheduler_ready = "Executing job scheduler ..." in latest_log

            if scheduler_ready:
                sleep(5)
                x += 5
                scheduler_logs = get_logs(LOGGER, ARGS.integration, last_test, log_from="scheduler")
                latest_log = scheduler_logs[-1]
                LOGGER.debug(f"Scheduler latest log: {latest_log}")
                scheduler_ready = "Executing job scheduler ..." in latest_log

            LOGGER.debug(f"Scheduler ready: {scheduler_ready}")

            bw_logs = get_logs(LOGGER, ARGS.integration, last_test)
            found = 0
            for log in bw_logs:
                if "BunkerWeb is ready" in log:
                    found += 1

            LOGGER.debug(f"Found {found} 'BunkerWeb is ready' logs in the last test logs")

            if scheduler_ready and (
                found
                >= (
                    2
                    if (last_test is None or full_clean)
                    and (ARGS.integration != "Kubernetes" or annotations.get("bunkerweb.io/REVERSE_PROXY_URL", annotations.get("REVERSE_PROXY_URL", "/")))
                    else 1
                )
            ):
                LOGGER.info("🚀 BunkerWeb is ready, skipping the rest of the delay ...")
                break
        sleep(1)
        x += 1

LOGGER.info(f"📡 Starting {action.type} test" + (f" {action.repeat + 1} times" if action.repeat else "") + " ...")

url = action.url
database: str = redis_client.get("database") or "sqlite"
log_from: str = redis_client.get("log_from") or "bunkerweb"

for x in range(action.repeat + 1):
    if action.cooldown and x > 0:
        sleep(action.cooldown)

    if action.type == "redis":
        redis_handler.handle(LOGGER, action)
    elif action.type == "database":
        database_handler.handle(LOGGER, ARGS.integration, database, action)
    elif action.type == "bwcli":
        bwcli_handler.handle(LOGGER, ARGS.integration, action)
    elif action.type == "tool":
        tool_handler.handle(LOGGER, action)
    elif action.type == "export":
        export_handler.handle(LOGGER, action)
    elif action.type == "limit":
        limit_handler.handle(LOGGER, action)
    elif not is_derived_from_selenium_action(type(action)):
        if action.type == "string":
            http_string_handler.handle(LOGGER, action)
        elif action.type == "path":
            http_path_handler.handle(LOGGER, action)
        elif action.type == "status":
            http_status_handler.handle(LOGGER, action)
        elif action.type == "header":
            http_header_handler.handle(LOGGER, action)
        elif action.type == "ssl":
            http_ssl_handler.handle(LOGGER, action)
    else:
        if action.type == "xpath":
            selenium_xpath_handler.handle(LOGGER, action)
        elif action.type == "cookie":
            selenium_cookie_handler.handle(LOGGER, action)

    if action.log:
        LOGGER.info(f"📜 Checking {log_from} logs if they contain {action.log!r} ...")

        sleep(1)  # Wait for the logs to be written
        raw_logs = get_logs(LOGGER, ARGS.integration, log_from=log_from)
        if ARGS.integration in ("Autoconf", "Kubernetes"):
            start_idx = 0
            for i, line in enumerate(raw_logs):
                if "Executing job scheduler ..." in line:
                    start_idx = i + 1
                    break
            service_logs = raw_logs[start_idx:]
            service_logs.reverse()
        else:
            service_logs = raw_logs
            service_logs.reverse()

        found = False
        for bw_log in service_logs:
            if action.log in bw_log:
                found = True
                break

        if not found:
            LOGGER.error(f"📜 Log {action.log!r} not found in {log_from} logs, exiting ...")
            exit(1)

        LOGGER.info(f"📜 Log {action.log!r} found in {log_from} logs")

    if action.not_log:
        LOGGER.info(f"📜 Checking {log_from} logs if they don't contain {action.not_log!r} ...")

        sleep(1)  # Wait for the logs to be written
        raw_logs = get_logs(LOGGER, ARGS.integration, log_from=log_from)
        if ARGS.integration in ("Autoconf", "Kubernetes"):
            start_idx = 0
            for i, line in enumerate(raw_logs):
                if "Executing job scheduler ..." in line:
                    start_idx = i + 1
                    break
            service_logs = raw_logs[start_idx:]
            service_logs.reverse()
        else:
            service_logs = raw_logs
            service_logs.reverse()

        found = False
        for bw_log in service_logs:
            if action.not_log in bw_log:
                found = True
                break

        if found:
            LOGGER.error(f"📜 Log {action.not_log!r} found in {log_from} logs, exiting ...")
            exit(1)

        LOGGER.info(f"📜 Log {action.not_log!r} not found in {log_from} logs")

    LOGGER.info("✅ Test passed")

redis_client.set("full_clean", int(action.full_clean))
redis_client.set("restart_stack", int(action.restart_stack))
