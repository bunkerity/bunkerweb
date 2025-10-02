#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

# Add shared deps
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError

from common_utils import bytes_hash  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore


def check_ip_line(line: bytes) -> bytes | None:
    line = line.strip()
    if not line:
        return None
    if line.startswith((b"#", b";")):
        return None
    # Only keep first token for non-User-Agent lists
    line = line.split(b" ")[0]
    # Validate IP or CIDR
    if b"/" in line:
        with suppress(ValueError):
            ip_network(line.decode("utf-8"))
            return line
    else:
        with suppress(ValueError):
            ip_address(line.decode("utf-8"))
            return line
    return None


LOGGER = setup_logger("DNSBL")
status = 0

try:
    # Determine services
    services_raw = getenv("SERVER_NAME", "www.example.com").strip()
    if not services_raw:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)
    services = services_raw.split(" ")

    # Determine activation per service
    dnsbl_activated = False
    services_urls: dict[str, set[str]] = {}

    if getenv("MULTISITE", "no") == "yes":
        for svc in services:
            if getenv(f"{svc}_USE_DNSBL", "yes") == "yes":
                dnsbl_activated = True
                urls = set(u for u in getenv(f"{svc}_DNSBL_IGNORE_IP_URLS", "").strip().split(" ") if u)
                services_urls[svc] = urls
    else:
        if getenv("USE_DNSBL", "yes") == "yes":
            dnsbl_activated = True
            urls = set(u for u in getenv("DNSBL_IGNORE_IP_URLS", "").strip().split(" ") if u)
            services_urls[services[0]] = urls

    if not dnsbl_activated:
        LOGGER.info("DNSBL is not activated, skipping downloads...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    # If no URL is configured across all services, clean cache and exit
    if not any(urls for urls in services_urls.values()):
        LOGGER.warning("No DNSBL ignore IP URL configured, nothing to do...")
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

    processed_urls: set[str] = set()
    failed_urls: set[str] = set()
    url_cache_files: set[str] = set()

    for service, urls in services_urls.items():
        if not urls:
            # Remove stale service file
            if JOB.job_path.joinpath(service, "IGNORE_IP.list").is_file():
                LOGGER.warning(f"{service} DNSBL IGNORE_IP is cached but no URL is configured, removing from cache...")
                deleted, err = JOB.del_cache("IGNORE_IP.list", service_id=service)
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {service} IGNORE_IP.list from cache : {err}")
            continue

        unique_entries: set[bytes] = set()
        total_new_lines = 0

        for url in urls:
            url_file = f"{bytes_hash(url, algorithm='sha1')}.list"
            url_cache_files.add(url_file)
            cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
            try:
                # If URL previously failed this run, just count failure once
                if url in failed_urls:
                    pass
                # If cached recently (< 1h), reuse cached data
                elif (
                    isinstance(cached_url, dict)
                    and cached_url.get("last_update")
                    and cached_url["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp()
                ):
                    LOGGER.debug(f"URL {url} cached < 1h ago, skipping download...")
                    cached_data = cached_url.get("data", b"")
                    if cached_data:
                        for line in cached_data.split(b"\n")[1:]:
                            line = line.strip()
                            if not line:
                                continue
                            unique_entries.add(line)
                else:
                    # Download
                    iterable = None
                    failed = False
                    LOGGER.info(f"Downloading DNSBL ignore IP data from {url} ...")
                    if url.startswith("file://"):
                        try:
                            with open(url[7:], "rb") as f:
                                iterable = f.readlines()
                        except OSError as e:
                            status = 2
                            LOGGER.debug(format_exc())
                            LOGGER.error(f"Error while opening file {url[7:]} : {e}")
                            failed_urls.add(url)
                            failed = True
                    else:
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                resp = get(url, stream=True, timeout=10)
                                break
                            except ConnectionError:
                                retry_count += 1
                                if retry_count == max_retries:
                                    raise
                                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                                sleep(3)

                        if resp.status_code != 200:
                            status = 2
                            LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                            failed_urls.add(url)
                            failed = True
                        else:
                            iterable = resp.iter_lines()

                    if not failed and iterable is not None:
                        url_content = b""
                        added_lines = 0
                        for line in iterable:
                            valid = check_ip_line(line)
                            if valid is None:
                                continue
                            if valid not in unique_entries:
                                added_lines += 1
                            unique_entries.add(valid)
                            url_content += valid + b"\n"
                        total_new_lines += added_lines

                        cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode() + b"\n" + url_content)
                        if not cached:
                            LOGGER.error(f"Error while caching url content for {url}: {err}")
            except BaseException as e:
                status = 2
                LOGGER.debug(format_exc())
                LOGGER.error(f"Exception while getting {service} DNSBL ignore IPs from {url} :\n{e}")
                failed_urls.add(url)
            finally:
                processed_urls.add(url)

        # Build final content
        content = b"\n".join(sorted(unique_entries)) + b"\n" if unique_entries else b""
        if not content:
            continue

        # Check if file changed
        new_hash = bytes_hash(content)
        old_hash = JOB.cache_hash("IGNORE_IP.list", service_id=service)
        if new_hash == old_hash:
            LOGGER.debug(f"{service} file IGNORE_IP.list is identical to cache file, reload is not needed")
            continue
        elif old_hash:
            LOGGER.debug(f"{service} file IGNORE_IP.list is different than cache file, reload is needed")
        else:
            LOGGER.debug(f"New {service} file IGNORE_IP.list is not in cache, reload is needed")

        # Cache service file
        cached, err = JOB.cache_file("IGNORE_IP.list", content, service_id=service, checksum=new_hash)
        if not cached:
            LOGGER.error(f"Error while caching DNSBL ignore IP list for {service} : {err}")
            status = 2
            continue

        status = 1 if status != 2 else 2

    # Clean old url cache files no longer referenced
    for url_file in JOB.job_path.glob("*.list"):
        if url_file.name not in url_cache_files:
            LOGGER.warning(f"Removing no longer used url file {url_file} ...")
            deleted, err = JOB.del_cache(url_file)
            if not deleted:
                LOGGER.warning(f"Couldn't delete url file {url_file} from cache : {err}")

except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running dnsbl-download.py :\n{e}")

sys_exit(status)
