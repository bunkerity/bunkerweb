#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from logging import getLogger
from math import ceil
from os import getenv
from os.path import join
from pathlib import Path
from time import sleep
from typing import Optional

from redis import Redis
from selenium.webdriver.support.ui import WebDriverWait
from yaml import safe_load

from utils import resolve_env_placeholders, get_logs
import utils.logger  # noqa: F401
from utils.action import parse_action
from ui_handlers.common import UiContext, build_driver, maybe_sleep
from ui_handlers import (
    setup_handle,
    login_handle,
    access_handle,
    find_handle,
    save_data_handle,
    click_handle,
    access_page_handle,
    send_keys_handle,
    refresh_handle,
    switch_tab_handle,
    close_tab_handle,
    config_flow_handle,
    instance_create_handle,
    instance_delete_handle,
    service_flow_handle,
)

LOGGER = getLogger("UI_TEST")

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

file_path = join("tests", "ui", f"{filename}.yml")

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
    "ui",
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
    for x in range(ceil(wait_duration)):
        LOGGER.debug(f"⏲ {wait_duration - x} seconds left ...")
        if ARGS.integration in ("Autoconf", "Kubernetes") and delay == 0.0:
            last_test: Optional[str] = redis_client.get("last_test")
            bw_logs = get_logs(LOGGER, ARGS.integration, last_test)
            found = 0
            for log in bw_logs:
                if "BunkerWeb is ready" in log:
                    found += 1

            if found >= 1:
                LOGGER.info("🚀 BunkerWeb is ready, skipping the rest of the delay ...")
                break
        sleep(1)

LOGGER.info(f"📡 Starting {action.type} test...")

with build_driver(LOGGER, accept_insecure_certs=True) as driver:
    try:
        driver.delete_all_cookies()
        driver.maximize_window()
        driver_wait = WebDriverWait(driver, 30)
        ctx = UiContext(LOGGER, driver, driver_wait)

        for x, (step, step_data) in enumerate(action.steps.items(), 1):
            LOGGER.info(f"🦊 Executing step {x}: {step}...")
            LOGGER.debug(step_data)

            maybe_sleep(LOGGER, step_data.sleep)

            if step_data.type == "setup":
                ctx.base_url = setup_handle(LOGGER, ctx, step_data)
            elif step_data.type == "login":
                login_handle(LOGGER, ctx, step_data)
            elif step_data.type == "access":
                access_handle(LOGGER, ctx, step_data)
            elif step_data.type == "find":
                find_handle(LOGGER, ctx, step_data)
            elif step_data.type == "save_data":
                save_data_handle(LOGGER, ctx, step_data)
            elif step_data.type == "click":
                click_handle(LOGGER, ctx, step_data)
            elif step_data.type == "access_page":
                access_page_handle(LOGGER, ctx, step_data)
            elif step_data.type == "send_keys":
                send_keys_handle(LOGGER, ctx, step_data)
            elif step_data.type == "refresh":
                refresh_handle(LOGGER, ctx, step_data)
            elif step_data.type == "del_data":
                ctx.saved_data.pop(step_data.key, None)
                LOGGER.info(f"🦊 Deleted data {step_data.key} ✅")
            elif step_data.type == "switch_tab":
                switch_tab_handle(LOGGER, ctx, step_data)
            elif step_data.type == "close_tab":
                close_tab_handle(LOGGER, ctx, step_data)
            else:
                if step_data.item in ("service", "global_config"):
                    service_flow_handle(LOGGER, ctx, step_data)
                elif step_data.item == "instance":
                    if step_data.type == "delete":
                        instance_delete_handle(LOGGER, ctx, step_data)
                    else:
                        instance_create_handle(LOGGER, ctx, step_data)
                elif step_data.item == "config":
                    config_flow_handle(LOGGER, ctx, step_data)

                # TODO

            print("   ", flush=True)
    except BaseException:
        driver.save_screenshot("error.png")
        raise

    if getenv("TESTS_WAIT", "no") == "yes":
        sleep(1000)
