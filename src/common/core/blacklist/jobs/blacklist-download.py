#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError

from common_utils import bytes_hash  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

rdns_rx = re_compile(rb"^[^ ]+$")
asn_rx = re_compile(rb"^\d+$")
uri_rx = re_compile(rb"^/")


def check_line(kind: str, line: bytes) -> Tuple[bool, bytes]:
    if kind in ("IP", "IGNORE_IP"):
        if b"/" in line:
            with suppress(ValueError):
                ip_network(line.decode("utf-8"))
                return True, line
        else:
            with suppress(ValueError):
                ip_address(line.decode("utf-8"))
                return True, line
    elif kind in ("RDNS", "IGNORE_RDNS"):
        if rdns_rx.match(line):
            return True, line.lower()
    elif kind in ("ASN", "IGNORE_ASN"):
        real_line = line.replace(b"AS", b"").replace(b"as", b"")
        if asn_rx.match(real_line):
            return True, real_line
    elif kind in ("USER_AGENT", "IGNORE_USER_AGENT"):
        return True, b"(?:\\b)" + line + b"(?:\\b)"
    elif kind in ("URI", "IGNORE_URI"):
        if uri_rx.match(line):
            return True, line

    return False, b""


LOGGER = getLogger("BLACKLIST")
status = 0

KINDS = ("IP", "RDNS", "ASN", "USER_AGENT", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI")

COMMUNITY_LISTS = {
    "ip:danmeuk-tor-exit": "https://www.dan.me.uk/torlist/?exit",
    "ua:mitchellkrogza-bad-user-agents": "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list",
    "ip:laurent-minne-data-shield-aggressive": "https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt",
    "ip:laurent-minne-data-shield-critical": "https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt",
}

try:
    # Check if at least a server has Blacklist activated
    blacklist_activated = False

    services = getenv("SERVER_NAME", "www.example.com").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split()
    services_blacklist_urls = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_USE_BLACKLIST", "yes") == "yes":
                blacklist_activated = True

                # Get services URLs
                services_blacklist_urls[first_server] = {}
                for kind in KINDS:
                    services_blacklist_urls[first_server][kind] = set()
                    for url in getenv(f"{first_server}_BLACKLIST_{kind}_URLS", "").strip().split():
                        services_blacklist_urls[first_server][kind].add(url)

                # Add community blacklist URLs
                community_lists = getenv(f"{first_server}_BLACKLIST_COMMUNITY_LISTS", "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents").strip()
                for community_id in community_lists.split():
                    if not community_id:
                        continue

                    if community_id in COMMUNITY_LISTS:
                        url = COMMUNITY_LISTS[community_id]
                        # Determine kind from prefix
                        prefix = community_id.split(":", 1)[0].lower()
                        if prefix == "ip":
                            kind = "IP"
                        elif prefix == "ua":
                            kind = "USER_AGENT"
                        elif prefix == "rdns":
                            kind = "RDNS"
                        elif prefix == "asn":
                            kind = "ASN"
                        elif prefix == "uri":
                            kind = "URI"
                        else:
                            kind = "IP"  # Default fallback
                        services_blacklist_urls[first_server][kind].add(url)
                    else:
                        LOGGER.warning(f"Community blacklist {community_id} not found in predefined lists")
    # Singlesite case
    elif getenv("USE_BLACKLIST", "yes") == "yes":
        blacklist_activated = True

        # Get global URLs
        services_blacklist_urls[services[0]] = {}
        for kind in KINDS:
            services_blacklist_urls[services[0]][kind] = set()
            for url in getenv(f"BLACKLIST_{kind}_URLS", "").strip().split():
                services_blacklist_urls[services[0]][kind].add(url)

        # Add community blacklist URLs for singlesite
        community_lists = getenv("BLACKLIST_COMMUNITY_LISTS", "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents").strip()
        for community_id in community_lists.split():
            if community_id in COMMUNITY_LISTS:
                url = COMMUNITY_LISTS[community_id]
                # Determine kind from prefix
                prefix = community_id.split(":", 1)[0].lower()
                if prefix == "ip":
                    kind = "IP"
                elif prefix == "ua":
                    kind = "USER_AGENT"
                elif prefix == "rdns":
                    kind = "RDNS"
                elif prefix == "asn":
                    kind = "ASN"
                elif prefix == "uri":
                    kind = "URI"
                else:
                    kind = "IP"  # Default fallback
                services_blacklist_urls[services[0]][kind].add(url)
            else:
                LOGGER.warning(f"Community blacklist {community_id} not found in predefined lists")

    if not blacklist_activated:
        LOGGER.info("Blacklist is not activated, skipping downloads...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    if not any(url for urls in services_blacklist_urls.values() for url in urls.values()):
        LOGGER.warning("No blacklist URL is configured, nothing to do...")
        for file in list(JOB.job_path.rglob("*.list")):
            if file.parent == JOB.job_path:
                LOGGER.warning(f"Removing no longer used url file {file} ...")
                deleted, err = JOB.del_cache(file)
            else:
                LOGGER.warning(f"Removing no longer used service file {file} ...")
                deleted, err = JOB.del_cache(file, service_id=file.parent.name)

            if not deleted:
                LOGGER.warning(f"Couldn't delete file {file} from cache : {err}")
        sys_exit(0)

    urls = set()
    failed_urls = set()
    processed_urls = set()  # Track which URLs have been processed globally
    # Initialize aggregation per kind with service tracking
    aggregated_recap = {
        kind: {
            "total_services": set(),
            "total_urls": 0,
            "downloaded_urls": 0,
            "skipped_urls": 0,
            "failed_count": 0,
            "total_lines": 0,
        }
        for kind in KINDS
    }

    # Loop on services and kinds
    for service, kinds in services_blacklist_urls.items():
        for kind, urls_list in kinds.items():
            if not urls_list:
                if JOB.job_path.joinpath(service, f"{kind}.list").is_file():
                    LOGGER.warning(f"{service} blacklist for {kind} is cached but no URL is configured, removing from cache...")
                    deleted, err = JOB.del_cache(f"{kind}.list", service_id=service)
                    if not deleted:
                        LOGGER.warning(f"Couldn't delete {service} {kind}.list from cache : {err}")
                continue

            # Track that this service provided URLs for the current kind
            aggregated_recap[kind]["total_services"].add(service)

            # Use set to avoid duplicate entries
            unique_entries = set()
            content = b""
            for url in urls_list:
                url_file = f"{bytes_hash(url, algorithm='sha1')}.list"
                cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
                try:
                    # Only count URLs that haven't been processed globally
                    if url not in processed_urls:
                        aggregated_recap[kind]["total_urls"] += 1

                    # If the URL has recently been downloaded, use cache
                    if url in failed_urls:
                        if url not in processed_urls:
                            aggregated_recap[kind]["failed_count"] += 1
                    elif (
                        isinstance(cached_url, dict)
                        and cached_url.get("last_update")
                        and cached_url["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp()
                    ):
                        LOGGER.debug(f"URL {url} has already been downloaded less than 1 hour ago, skipping download...")
                        if url not in processed_urls:
                            aggregated_recap[kind]["skipped_urls"] += 1
                        # Process cached data and add to unique_entries
                        cached_data = cached_url.get("data", b"")
                        if cached_data:
                            # Skip first line (URL comment) and process entries
                            for line in cached_data.split(b"\n")[1:]:
                                line = line.strip()
                                if line:
                                    unique_entries.add(line)
                    else:
                        failed = False
                        LOGGER.info(f"Downloading blacklist data from {url} ...")
                        if url.startswith("file://"):
                            try:
                                with open(normpath(url[7:]), "rb") as f:
                                    iterable = f.readlines()
                            except OSError as e:
                                status = 2
                                LOGGER.debug(format_exc())
                                LOGGER.error(f"Error while opening file {url[7:]} : {e}")
                                failed_urls.add(url)
                                if url_file not in urls:
                                    aggregated_recap[kind]["failed_count"] += 1
                                failed = True
                        else:
                            max_retries = 3
                            retry_count = 0
                            while retry_count < max_retries:
                                try:
                                    resp = get(url, stream=True, timeout=10)
                                    break
                                except ConnectionError as e:
                                    retry_count += 1
                                    if retry_count == max_retries:
                                        raise e
                                    LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                                    sleep(3)

                            if resp.status_code != 200:
                                status = 2
                                LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                                failed_urls.add(url)
                                if url_file not in urls:
                                    aggregated_recap[kind]["failed_count"] += 1
                                failed = True
                            else:
                                iterable = resp.iter_lines()

                        if not failed:
                            if url not in processed_urls:
                                aggregated_recap[kind]["downloaded_urls"] += 1

                            url_content = b""
                            count_lines = 0
                            for line in iterable:
                                line = line.strip()
                                if not line or line.startswith((b"#", b";")):
                                    continue
                                elif kind != "USER_AGENT":
                                    line = line.split(b" ")[0]
                                ok, data = check_line(kind, line)
                                if ok:
                                    unique_entries.add(data)
                                    url_content += data + b"\n"
                                    count_lines += 1
                            if url not in processed_urls:
                                aggregated_recap[kind]["total_lines"] += count_lines

                            cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode("utf-8") + b"\n" + url_content)
                            if not cached:
                                LOGGER.error(f"Error while caching url content for {url}: {err}")
                except BaseException as e:
                    status = 2
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while getting {service} blacklist from {url} :\n{e}")
                    failed_urls.add(url)
                    if url not in processed_urls:
                        aggregated_recap[kind]["failed_count"] += 1
                finally:
                    # Mark URL as processed to avoid double counting
                    processed_urls.add(url)
                    urls.add(url_file)

            # Build final content from unique entries, sorted for consistency
            content = b"\n".join(sorted(unique_entries)) + b"\n" if unique_entries else b""

            if not content:
                continue

            # Check if file has changed
            new_hash = bytes_hash(content)
            old_hash = JOB.cache_hash(f"{kind}.list", service_id=service)
            if new_hash == old_hash:
                LOGGER.debug(f"{service} file {kind}.list is identical to cache file, reload is not needed")
                continue
            elif old_hash:
                LOGGER.debug(f"{service} file {kind}.list is different than cache file, reload is needed")
            else:
                LOGGER.debug(f"New {service} file {kind}.list is not in cache, reload is needed")

            # Put file in cache
            cached, err = JOB.cache_file(f"{kind}.list", content, service_id=service, checksum=new_hash)
            if not cached:
                LOGGER.error(f"Error while caching blacklist : {err}")
                status = 2
                continue

            status = 1 if status != 2 else 2

    # Log a detailed recap per kind across services, only if there is at least one service using the kind
    for kind, recap in aggregated_recap.items():
        service_count = len(recap["total_services"])
        if service_count == 0:
            continue
        successful = recap["downloaded_urls"]
        skipped = recap["skipped_urls"]
        failed = recap["failed_count"]
        total_lines = recap["total_lines"]
        LOGGER.info(
            f"Recap for {kind} urls: Total Services: {service_count}, Successful: {successful}, "
            f"Skipped (cached): {skipped}, Failed: {failed}, Total Lines: {total_lines}"
        )

    # Remove old files
    for url_file in JOB.job_path.glob("*.list"):
        LOGGER.debug(f"Checking if {url_file} is still in use ...")
        if url_file.name not in urls:
            LOGGER.warning(f"Removing no longer used url file {url_file} ...")
            deleted, err = JOB.del_cache(url_file)
            if not deleted:
                LOGGER.warning(f"Couldn't delete url file {url_file} from cache : {err}")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running blacklist-download.py :\n{e}")

sys_exit(status)
