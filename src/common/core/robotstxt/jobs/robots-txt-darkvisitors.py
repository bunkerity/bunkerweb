#!/usr/bin/env python3

from datetime import datetime, timedelta
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from re import compile as re_compile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import post
from requests.exceptions import ConnectionError

from common_utils import bytes_hash
from logger import setup_logger
from jobs import Job

LOGGER = setup_logger("ROBOTSTXT.DarkVisitors")
status = 0

DARKVISITORS_API_URL = "https://api.darkvisitors.com/robots-txts"
CONFIG_HASH_RX = re_compile(rb"^# config_hash: (.*)$")

try:
    # Check if at least a server has RobotsTxt activated
    robotstxt_activated = False
    services = getenv("SERVER_NAME", "www.example.com").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_darkvisitors_configs = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for service in services:
            if getenv(f"{service}_USE_ROBOTSTXT", "no") == "yes":
                token = getenv(f"{service}_ROBOTSTXT_DARKVISITORS_TOKEN", "").strip()
                if token:
                    robotstxt_activated = True
                    services_darkvisitors_configs[service] = {
                        "token": token,
                        "agent_types": getenv(f"{service}_ROBOTSTXT_DARKVISITORS_AGENT_TYPES", "").strip(),
                        "disallow": getenv(f"{service}_ROBOTSTXT_DARKVISITORS_DISALLOW", "/").strip(),
                    }
    # Singlesite case
    elif getenv("USE_ROBOTSTXT", "no") == "yes":
        token = getenv("ROBOTSTXT_DARKVISITORS_TOKEN", "").strip()
        if token:
            robotstxt_activated = True
            services_darkvisitors_configs[services[0]] = {
                "token": token,
                "agent_types": getenv("ROBOTSTXT_DARKVISITORS_AGENT_TYPES", "").strip(),
                "disallow": getenv("ROBOTSTXT_DARKVISITORS_DISALLOW", "/").strip(),
            }

    if not robotstxt_activated:
        LOGGER.info("Robots.txt with DarkVisitors is not activated, skipping downloads...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    if not services_darkvisitors_configs:
        LOGGER.warning("No DarkVisitors token is configured, nothing to do...")
        # Clean up old files if any
        for service in services:
            if JOB.job_path.joinpath(service, "darkvisitors.list").is_file():
                LOGGER.warning(f"{service} darkvisitors.list is cached but no token is configured, removing from cache...")
                deleted, err = JOB.del_cache("darkvisitors.list", service_id=service)
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {service} darkvisitors.list from cache : {err}")
        sys_exit(0)

    for service, config in services_darkvisitors_configs.items():
        cache_file = "darkvisitors.list"

        if not config["agent_types"]:
            LOGGER.warning(f"DarkVisitors API call for service {service} skipped: at least one agent_type must be declared.")
            if JOB.job_path.joinpath(service, cache_file).is_file():
                LOGGER.warning(f"Removing stale DarkVisitors cache file for service {service} due to missing agent_types.")
                deleted, err = JOB.del_cache(cache_file, service_id=service)
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {service} {cache_file} from cache : {err}")
            continue

        # Calculate new config hash
        config_str = f"{config['token']}{config['agent_types']}{config['disallow']}"
        new_config_hash = bytes_hash(config_str.encode("utf-8"))

        # Get cached data and info
        cached_info = JOB.get_cache(cache_file, service_id=service, with_info=True, with_data=False)

        # Check if we need to download
        should_download = True
        if isinstance(cached_info, dict) and cached_info.get("path") and cached_info["path"].is_file():
            old_config_hash = None
            with open(cached_info["path"], "rb") as f:
                first_line = f.readline()
                match = CONFIG_HASH_RX.match(first_line)
                if match:
                    old_config_hash = match.group(1).decode("utf-8")

            is_config_same = old_config_hash == new_config_hash
            is_cache_fresh = cached_info.get("last_update") and cached_info["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp()

            if is_config_same and is_cache_fresh:
                LOGGER.debug(f"DarkVisitors list for {service} is fresh and config is unchanged, skipping download...")
                should_download = False

        if should_download:
            LOGGER.info(f"Fetching robots.txt from DarkVisitors API for service {service}...")
            try:
                headers = {
                    "Authorization": f"Bearer {config['token']}",
                    "Content-Type": "application/json",
                }
                data = {}
                if config["agent_types"]:
                    agent_types_list = [s.strip() for s in config["agent_types"].split(",") if s.strip()]
                    if agent_types_list:
                        data["agent_types"] = agent_types_list
                if config["disallow"]:
                    data["disallow"] = config["disallow"]

                LOGGER.debug(f"Requesting DarkVisitors API with data: {data}")

                resp = post(DARKVISITORS_API_URL, headers=headers, json=data, timeout=10)

                if resp.status_code == 200:
                    content = resp.content
                    content_hash = bytes_hash(content)

                    content_to_cache = f"# config_hash: {new_config_hash}\n".encode("utf-8") + content

                    cached, err = JOB.cache_file(cache_file, content_to_cache, service_id=service, checksum=content_hash)
                    if not cached:
                        LOGGER.error(f"Error while caching DarkVisitors content for {service}: {err}")
                        status = 2
                    else:
                        LOGGER.info(f"Successfully fetched and cached DarkVisitors robots.txt for {service}")
                        status = 1 if status != 2 else 2
                else:
                    LOGGER.error(f"Failed to fetch from DarkVisitors API for {service}. Status code: {resp.status_code}, Response: {resp.text}")
                    status = 2

            except ConnectionError as e:
                LOGGER.error(f"Connection error while fetching from DarkVisitors API for {service}: {e}")
                status = 2
            except Exception as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"An unexpected error occurred for {service}: {e}")
                status = 2

except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running robots-txt-darkvisitors.py :\n{e}")

sys_exit(status)
