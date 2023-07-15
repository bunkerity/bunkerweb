#!/usr/bin/python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv, sep
from os.path import join, normpath
from pathlib import Path
from re import IGNORECASE, compile as re_compile
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Any, Dict, Tuple

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("api",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from API import API  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, cache_hash, file_hash, is_cached_file, send_cache_to_api

rdns_rx = re_compile(rb"^[^ ]+$", IGNORECASE)
asn_rx = re_compile(rb"^\d+$")
uri_rx = re_compile(rb"^/")


def check_line(kind: str, line: bytes) -> Tuple[bool, bytes]:
    if kind == "IP":
        if b"/" in line:
            with suppress(ValueError):
                ip_network(line.decode("utf-8"))
                return True, line
        else:
            with suppress(ValueError):
                ip_address(line.decode("utf-8"))
                return True, line
    elif kind == "RDNS":
        if rdns_rx.match(line):
            return True, line.lower()
    elif kind == "ASN":
        real_line = line.replace(b"AS", b"").replace(b"as", b"")
        if asn_rx.match(real_line):
            return True, real_line
    elif kind == "USER_AGENT":
        return True, b"(?:\\b)" + line + b"(?:\\b)"
    elif kind == "URI":
        if uri_rx.match(line):
            return True, line

    return False, b""


logger = setup_logger("WHITELIST", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    lock = Lock()
    with lock:
        configs: Dict[str, Dict[str, Any]] = db.get_config()
        bw_instances = db.get_instances()

    apis = []
    for instance in bw_instances:
        endpoint = f"http://{instance['hostname']}:{instance['port']}"
        host = instance["server_name"]
        apis.append(API(endpoint, host=host))

    # Check if at least a server has Whitelist activated
    whitelist_instances = []

    for instance, config in configs.items():
        # Multisite case
        configs[instance]["WHITELIST_ACTIVATED"] = False
        if config.get("MULTISITE", "no") == "yes":
            for first_server in config.get("SERVER_NAME", "").split(" "):
                if (
                    config.get(
                        f"{first_server}_USE_WHITELIST",
                        config.get("USE_WHITELIST", "yes"),
                    )
                    == "yes"
                ):
                    whitelist_instances.append(instance)
                    break
        # Singlesite case
        elif config.get("USE_WHITELIST", "yes") == "yes":
            whitelist_instances.append(instance)

    if not whitelist_instances:
        logger.info("Whitelist is not activated, skipping downloads...")
        _exit(0)

    # Create directories if they don't exist
    whitelist_path = Path(sep, "var", "cache", "bunkerweb", "whitelist")
    tmp_whitelist_path = Path(sep, "var", "tmp", "bunkerweb", "whitelist")
    instances_urls = {}

    for instance in whitelist_instances:
        # Our urls data
        urls = {
            "IP": [],
            "RDNS": [],
            "ASN": [],
            "USER_AGENT": [],
            "URI": [],
        }
        for kind in urls:
            for url in configs[instance].get(f"WHITELIST_{kind}_URLS", "").split(" "):
                if url and url not in urls[kind]:
                    urls[kind].append(url)

        same_as = None

        for instance_urls in instances_urls:
            if set(urls) == set(instances_urls[instance_urls]):
                same_as = instance_urls
                break

        instance_whitelist_path = whitelist_path.joinpath(
            same_as or (instance if instance != "127.0.0.1" else "")
        )
        instance_whitelist_path.mkdir(parents=True, exist_ok=True)

        for api in apis:
            if f"{instance}:" in api.endpoint:
                instance_api = api
                break

        if not instance_api:
            logger.error(
                f"Could not find an API for instance {instance}, configuration will not work as expected...",
            )
            continue

        if same_as:
            if instance != "127.0.0.1":
                sent, res = send_cache_to_api(instance_whitelist_path, instance_api)
                if not sent:
                    logger.error(f"Error while sending whitelist to API : {res}")
                    sys_exit(2)
                logger.info(res)
            continue

        instances_urls[instance] = urls

        # Don't go further if the cache is fresh
        kinds_fresh = {
            "IP": True,
            "RDNS": True,
            "ASN": True,
            "USER_AGENT": True,
            "URI": True,
        }
        all_fresh = True
        for kind in kinds_fresh:
            if not is_cached_file(
                instance_whitelist_path.joinpath(f"{kind}.list"),
                "hour",
                instance,
                db,
            ):
                kinds_fresh[kind] = False
                all_fresh = False
                logger.info(
                    f"Whitelist for {kind} is not cached, processing downloads..",
                )
            else:
                logger.info(
                    f"Whitelist for {kind} is already in cache, skipping downloads...",
                )

        if all_fresh:
            continue

        # Loop on kinds
        for kind, urls_list in urls.items():
            if kinds_fresh[kind]:
                continue
            # Write combined data of the kind to a single temp file
            for url in urls_list:
                try:
                    logger.info(f"Downloading whitelist data from {url} ...")
                    if url.startswith("file://"):
                        with open(normpath(url[7:]), "rb") as f:
                            iterable = f.readlines()
                    else:
                        resp = get(url, stream=True, timeout=10)

                        if resp.status_code != 200:
                            logger.warning(
                                f"Got status code {resp.status_code}, skipping..."
                            )
                            continue

                        iterable = resp.iter_lines()

                    i = 0
                    content = b""
                    for line in iterable:
                        line = line.strip()

                        if not line or line.startswith(b"#") or line.startswith(b";"):
                            continue
                        elif kind != "USER_AGENT":
                            line = line.split(b" ")[0]

                        ok, data = check_line(kind, line)
                        if ok:
                            content += data + b"\n"
                            i += 1

                    instance_tmp_whitelist_path = tmp_whitelist_path.joinpath(
                        instance if instance != "127.0.0.1" else ""
                    )
                    instance_tmp_whitelist_path.mkdir(parents=True, exist_ok=True)
                    instance_tmp_whitelist_path.joinpath(f"{kind}.list").write_bytes(
                        content
                    )

                    logger.info(f"Downloaded {i} bad {kind}")
                    # Check if file has changed
                    new_hash = file_hash(
                        instance_tmp_whitelist_path.joinpath(f"{kind}.list")
                    )
                    old_hash = cache_hash(
                        instance_whitelist_path.joinpath(f"{kind}.list"),
                        instance,
                        db,
                    )
                    if new_hash == old_hash:
                        logger.info(
                            f"New file {kind}.list is identical to cache file, reload is not needed",
                        )
                    else:
                        logger.info(
                            f"New file {kind}.list is different than cache file, reload is needed",
                        )
                        # Put file in cache
                        cached, err = cache_file(
                            instance_tmp_whitelist_path.joinpath(f"{kind}.list"),
                            instance_whitelist_path.joinpath(f"{kind}.list"),
                            new_hash,
                            instance,
                            db,
                        )

                        if not cached:
                            logger.error(f"Error while caching whitelist : {err}")
                            status = 2
                        else:
                            status = 1
                except:
                    status = 2
                    logger.error(
                        f"Exception while getting whitelist from {url} :\n{format_exc()}"
                    )

        if instance != "127.0.0.1":
            sent, res = send_cache_to_api(instance_whitelist_path, instance_api)
            if not sent:
                logger.error(f"Error while sending whitelist to API : {res}")
                status = 2
            logger.info(res)
except SystemExit as e:
    status = e.code
except:
    status = 2
    logger.error(f"Exception while running whitelist-download.py :\n{format_exc()}")

sys_exit(status)
