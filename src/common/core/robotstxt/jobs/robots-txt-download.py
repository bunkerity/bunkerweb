#!/usr/bin/env python3

from datetime import datetime, timedelta
from os import getenv, sep
from os.path import join, normpath
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError

from common_utils import bytes_hash  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("ROBOTSTXT")
status = 0

COMMUNITY_LISTS = {
    "ai-robots-txt": "https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/refs/heads/main/robots.txt",
    "robots-disallowed": "https://raw.githubusercontent.com/danielmiessler/RobotsDisallowed/refs/heads/master/curated.txt",
}

try:
    # Check if at least a server has RobotsTxt activated
    robotstxt_activated = False

    services = getenv("SERVER_NAME", "www.example.com").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_robotstxt_urls = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_USE_ROBOTSTXT", "no") == "yes":
                robotstxt_activated = True

                # Get services URLs
                services_robotstxt_urls[first_server] = set()
                for url in getenv(f"{first_server}_ROBOTSTXT_URLS", "").strip().split(" "):
                    if url:
                        services_robotstxt_urls[first_server].add(url)

                # Add community blacklist URLs
                community_lists = getenv(f"{first_server}_ROBOTSTXT_COMMUNITY_LISTS", "").strip()
                for community_id in community_lists.split(" "):
                    if not community_id:
                        continue

                    if community_id in COMMUNITY_LISTS:
                        url = COMMUNITY_LISTS[community_id]
                        services_robotstxt_urls[first_server].add(url)
                    else:
                        LOGGER.warning(f"Community list {community_id} not found in predefined lists")
    # Singlesite case
    elif getenv("USE_ROBOTSTXT", "no") == "yes":
        robotstxt_activated = True

        # Get global URLs
        services_robotstxt_urls[services[0]] = set()
        for url in getenv("ROBOTSTXT_URLS", "").strip().split(" "):
            if url:
                services_robotstxt_urls[services[0]].add(url)

        # Add community blacklist URLs for singlesite
        community_lists = getenv("ROBOTSTXT_COMMUNITY_LISTS", "").strip()
        for community_id in community_lists.split(" "):
            if not community_id:
                continue

            if community_id in COMMUNITY_LISTS:
                url = COMMUNITY_LISTS[community_id]
                services_robotstxt_urls[services[0]].add(url)
            else:
                LOGGER.warning(f"Community list {community_id} not found in predefined lists")

    if not robotstxt_activated:
        LOGGER.info("Robots.txt is not activated, skipping downloads...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    if not any(services_robotstxt_urls.values()):
        LOGGER.warning("No robots.txt URL is configured, nothing to do...")
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
    processed_urls = set()
    aggregated_recap = {
        "total_services": set(),
        "total_urls": 0,
        "downloaded_urls": 0,
        "skipped_urls": 0,
        "failed_count": 0,
        "total_lines": 0,
    }

    # Loop on services
    for service, urls_list in services_robotstxt_urls.items():
        if not urls_list:
            if JOB.job_path.joinpath(service, "rules.list").is_file():
                LOGGER.warning(f"{service} rules.list is cached but no URL is configured, removing from cache...")
                deleted, err = JOB.del_cache("rules.list", service_id=service)
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {service} rules.list from cache : {err}")
            continue

        aggregated_recap["total_services"].add(service)

        unique_entries = set()
        content = b""
        for url in urls_list:
            url_file = f"{bytes_hash(url, algorithm='sha1')}.list"
            cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
            is_robots_disallowed = url == COMMUNITY_LISTS.get("robots-disallowed")
            try:
                if url not in processed_urls:
                    aggregated_recap["total_urls"] += 1

                if url in failed_urls:
                    if url not in processed_urls:
                        aggregated_recap["failed_count"] += 1
                elif (
                    isinstance(cached_url, dict)
                    and cached_url.get("last_update")
                    and cached_url["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp()
                ):
                    LOGGER.debug(f"URL {url} has already been downloaded less than 1 hour ago, skipping download...")

                    if url not in processed_urls:
                        aggregated_recap["skipped_urls"] += 1

                    cached_data = cached_url.get("data", b"")
                    if cached_data:
                        for line in cached_data.split(b"\n")[1:]:
                            line = line.strip()
                            if line:
                                unique_entries.add(line)
                else:
                    failed = False
                    LOGGER.info(f"Downloading robots.txt data from {url} ...")
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
                                aggregated_recap["failed_count"] += 1
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
                                aggregated_recap["failed_count"] += 1
                            failed = True
                        else:
                            iterable = resp.iter_lines()

                    if not failed:
                        if url not in processed_urls:
                            aggregated_recap["downloaded_urls"] += 1

                        url_content = b"User-agent: *\n" if is_robots_disallowed else b""
                        count_lines = 0
                        for line in iterable:
                            line = line.strip()

                            if not line or line.startswith((b"#", b";")):
                                continue

                            if is_robots_disallowed:
                                line = b"Disallow: " + line

                            unique_entries.add(line)
                            url_content += line + b"\n"
                            count_lines += 1
                        if url not in processed_urls:
                            aggregated_recap["total_lines"] += count_lines

                        cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode("utf-8") + b"\n" + url_content)
                        if not cached:
                            LOGGER.error(f"Error while caching url content for {url}: {err}")
            except BaseException as e:
                status = 2
                LOGGER.debug(format_exc())
                LOGGER.error(f"Exception while getting {service} robots.txt from {url} :\n{e}")
                failed_urls.add(url)
                if url not in processed_urls:
                    aggregated_recap["failed_count"] += 1
            finally:
                processed_urls.add(url)
                urls.add(url_file)

        content = b"\n".join(sorted(unique_entries)) + b"\n" if unique_entries else b""

        if not content:
            continue

        new_hash = bytes_hash(content)
        old_hash = JOB.cache_hash("rules.list", service_id=service)
        if new_hash == old_hash:
            LOGGER.debug(f"{service} file rules.list is identical to cache file, reload is not needed")
            continue
        elif old_hash:
            LOGGER.debug(f"{service} file rules.list is different than cache file, reload is needed")
        else:
            LOGGER.debug(f"New {service} file rules.list is not in cache, reload is needed")

        cached, err = JOB.cache_file("rules.list", content, service_id=service, checksum=new_hash)
        if not cached:
            LOGGER.error(f"Error while caching robots.txt rules : {err}")
            status = 2
            continue

        status = 1 if status != 2 else 2

    service_count = len(aggregated_recap["total_services"])
    if service_count > 0:
        successful = aggregated_recap["downloaded_urls"]
        skipped = aggregated_recap["skipped_urls"]
        failed = aggregated_recap["failed_count"]
        total_lines = aggregated_recap["total_lines"]
        LOGGER.info(
            f"Recap for robots.txt urls: Total Services: {service_count}, Successful: {successful}, "
            f"Skipped (cached): {skipped}, Failed: {failed}, Total Lines: {total_lines}"
        )

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
    LOGGER.error(f"Exception while running robots-txt-download.py :\n{e}")

sys_exit(status)
