#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from pathlib import Path
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

from common_utils import bytes_hash, iter_list_entries, parse_duration, split_list_url  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

rdns_rx = re_compile(rb"^[^ ]+$")
asn_rx = re_compile(rb"^\d+$")
uri_rx = re_compile(rb"^/")


def check_line(kind: str, line: bytes) -> Tuple[bool, bytes]:
    if kind in ("IP", "IGNORE_IP"):
        # a zone id ("fe80::1%eth0") names an interface of the downloading host, not an address the matcher can load
        if b"%" in line:
            return False, b""
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


UA_WRAP = b"(?:\\b)"


def read_cached_entries(kind: str, data: bytes) -> set:
    """Entries of a cache file that are still valid for this kind. User agents are cached already wrapped, so they are checked, not wrapped twice."""
    entries = set()
    for line in data.split(b"\n")[1:]:  # the first line names the URL
        line = line.strip()
        if not line:
            continue
        if kind in ("USER_AGENT", "IGNORE_USER_AGENT"):
            ok = len(line) > 2 * len(UA_WRAP) and line.startswith(UA_WRAP) and line.endswith(UA_WRAP)
        else:
            ok, line = check_line(kind, line)
        if ok:
            entries.add(line)
    return entries


LOGGER = getLogger("BLACKLIST")
status = 0
list_changed = False  # a published list changed: the scheduler must reload (exit 1 or 3)
run_failed = False  # a source or a cache failed (exit 2 or 3)


def exit_status() -> int:
    return 3 if list_changed and run_failed else (1 if list_changed else (2 if run_failed else 0))


KINDS = ("IP", "RDNS", "ASN", "USER_AGENT", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI")

COMMUNITY_LISTS = {
    "ip:danmeuk-tor-exit": "https://www.dan.me.uk/torlist/?exit",
    "ua:mitchellkrogza-bad-user-agents": "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list",
    "ip:laurent-minne-data-shield-aggressive": "https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt",
}

# Retired preset ids that stored values may still hold: they resolve to their replacement and are no longer offered in the UI.
# Data-Shield moved its Critical profile to the paid Data-Shield Pro: the public critical URL answers 404 and the Pro feed needs
# authentication, which this job cannot send. The free Community Standard list is the closest public list.
DEPRECATED_COMMUNITY_LISTS = {"ip:laurent-minne-data-shield-critical": "ip:laurent-minne-data-shield-aggressive"}
# Their old URLs are never downloaded again, but the last good cache of one stays in use until its replacement has a valid cache.
RETIRED_COMMUNITY_URLS = {
    "ip:laurent-minne-data-shield-critical": "https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt"
}
notified_deprecated_lists = set()
retired_fallbacks = {}  # {service: {kind: {replacement url: retired url}}}


def resolve_community_id(community_id: str) -> str:
    replacement = DEPRECATED_COMMUNITY_LISTS.get(community_id)
    if replacement is None:
        return community_id
    if community_id not in notified_deprecated_lists:
        notified_deprecated_lists.add(community_id)
        LOGGER.warning(
            f"Community blacklist {community_id} is deprecated: Critical is now part of the paid Data-Shield Pro (https://data-shield.eu), "
            f"this preset now downloads the free Community Standard list ({replacement})"
        )
    return replacement


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

                    retired_id = community_id
                    community_id = resolve_community_id(community_id)
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
                        if retired_id in RETIRED_COMMUNITY_URLS:
                            retired_fallbacks.setdefault(first_server, {}).setdefault(kind, {})[url] = RETIRED_COMMUNITY_URLS[retired_id]
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
            retired_id = community_id
            community_id = resolve_community_id(community_id)
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
                if retired_id in RETIRED_COMMUNITY_URLS:
                    retired_fallbacks.setdefault(services[0], {}).setdefault(kind, {})[url] = RETIRED_COMMUNITY_URLS[retired_id]
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
                deleted, err = JOB.del_cache(file.name)
            else:
                LOGGER.warning(f"Removing no longer used service file {file} ...")
                deleted, err = JOB.del_cache(file.name, service_id=file.parent.name)

            if not deleted:
                LOGGER.warning(f"Couldn't delete file {file} from cache : {err}")
        sys_exit(0)

    urls = set()
    failed_urls = set()
    processed_urls = set()  # Track which (url, kind) pairs have been processed globally
    rejected_urls = set()  # (url, kind) pairs whose downloaded content has no valid entry for that kind
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

    # A URL shared by several services is due as soon as the shortest interval among them says so, whatever the service order
    service_intervals = {}
    url_intervals = {}
    url_consumers = {}  # url -> number of (service, kind) pairs that still have to read its body
    for service, kinds in services_blacklist_urls.items():
        interval_value = getenv("BLACKLIST_URLS_REFRESH_INTERVAL", "1h")
        if getenv("MULTISITE", "no") == "yes":
            interval_value = getenv(f"{service}_BLACKLIST_URLS_REFRESH_INTERVAL", interval_value)
        try:
            service_intervals[service] = parse_duration(interval_value, "s")
        except ValueError:
            LOGGER.warning(f"Invalid BLACKLIST_URLS_REFRESH_INTERVAL for {service}: {interval_value}, using 1h")
            service_intervals[service] = 3600
        for urls_list in kinds.values():
            for url in urls_list:
                url_intervals[url] = min(url_intervals.get(url, service_intervals[service]), service_intervals[service])
                url_consumers[url] = url_consumers.get(url, 0) + 1

    # url -> (body, content type) downloaded during this run, so a URL is never requested twice. Only the raw body is shared:
    # every kind validates and caches its own parsed entries, and the body is dropped once its last consumer is done.
    fetched = {}
    # (url, kind) -> (entries of the first complete parse of this run, whether its cache write succeeded): that is the source's data for every
    # later service, whatever the cache says. A failed write is not persisted for any of them, so each keeps its own fallback files.
    completed = {}

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
            frozen = False  # a source of this service and kind has data that cannot be read: its published list is left as it is
            for url in urls_list:
                cache_key = (url, kind)
                url_file = f"{bytes_hash(f'{kind} {url}', algorithm='sha1')}.list"  # parsed entries depend on the kind
                # Older jobs kept one file per URL, whatever the kind; a replaced preset also has its retired URL. They are used in this order
                # only when the kind has no data of its own, and stay in use (never cleaned) until then.
                retired_url = retired_fallbacks.get(service, {}).get(kind, {}).get(url)
                fallback_files = {fallback_url: f"{bytes_hash(fallback_url, algorithm='sha1')}.list" for fallback_url in (url, retired_url) if fallback_url}
                cache_error = None
                cached_url = None
                if cache_key not in completed:
                    try:
                        cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
                    except BaseException as e:
                        cache_error = e  # raised below if this run has no data of its own
                use_cached_url = False
                url_has_data = False
                downloaded = False  # this run parsed the source completely and got valid entries
                refresh_interval = url_intervals[url]
                try:
                    # Only count URLs that haven't been processed globally
                    if cache_key not in processed_urls:
                        aggregated_recap[kind]["total_urls"] += 1

                    if cache_key in completed:
                        unique_entries |= completed[cache_key][0]
                        url_has_data = downloaded = True
                        if not completed[cache_key][1]:
                            urls.update(fallback_files.values())
                    # If the URL has recently been downloaded, use cache
                    elif url in failed_urls or cache_key in rejected_urls:
                        if cache_key not in processed_urls:
                            aggregated_recap[kind]["failed_count"] += 1
                    elif (
                        isinstance(cached_url, dict)
                        and refresh_interval > 0
                        and cached_url.get("last_update")
                        and cached_url["last_update"] > datetime.now().astimezone().timestamp() - refresh_interval
                    ):
                        LOGGER.debug(f"URL {url} has already been downloaded less than {refresh_interval} seconds ago, skipping download...")
                        if cache_key not in processed_urls:
                            aggregated_recap[kind]["skipped_urls"] += 1
                        use_cached_url = True
                    else:
                        failed = False
                        LOGGER.info(f"Downloading blacklist data from {url} ...")
                        download_url, url_filter = split_list_url(url)
                        content_type = ""
                        if url in fetched:
                            body, content_type = fetched[url]
                        elif download_url.startswith("file://"):
                            try:
                                body = Path(normpath(download_url[7:])).read_bytes()
                                fetched[url] = (body, content_type)
                            except OSError as e:
                                run_failed = True
                                LOGGER.debug(format_exc())
                                LOGGER.error(f"Error while opening file {download_url[7:]} : {e}")
                                failed_urls.add(url)
                                if url_file not in urls:
                                    aggregated_recap[kind]["failed_count"] += 1
                                failed = True
                        else:
                            max_retries = 3
                            retry_count = 0
                            while retry_count < max_retries:
                                try:
                                    resp = get(download_url, stream=True, timeout=10)
                                    break
                                except ConnectionError as e:
                                    retry_count += 1
                                    if retry_count == max_retries:
                                        raise e
                                    LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                                    sleep(3)

                            if resp.status_code != 200:
                                run_failed = True
                                LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                                failed_urls.add(url)
                                if url_file not in urls:
                                    aggregated_recap[kind]["failed_count"] += 1
                                failed = True
                            else:
                                body = resp.content
                                content_type = resp.headers.get("Content-Type", "")
                                fetched[url] = (body, content_type)

                        if not failed:
                            # Parsing and caching are scoped to this kind: the body in memory stays usable by the other kinds
                            try:
                                # Entries are merged only once the whole body is parsed: a parser that raises contributes nothing
                                parsed_entries = set()
                                url_content = b""
                                parsed_lines = 0
                                for line in iter_list_entries(
                                    body,
                                    content_type=content_type,
                                    url_filter=url_filter,
                                    ip_list=kind in ("IP", "IGNORE_IP"),
                                    whole_line=kind in ("USER_AGENT", "IGNORE_USER_AGENT"),
                                    logger=LOGGER,
                                ):
                                    ok, data = check_line(kind, line)
                                    if ok:
                                        parsed_entries.add(data)
                                        url_content += data + b"\n"
                                        parsed_lines += 1
                                if not parsed_lines:
                                    LOGGER.warning(f"No valid {kind} entry found in {url} (Content-Type: {content_type or 'unknown'})")
                                    run_failed = True
                                    rejected_urls.add(cache_key)
                                    if url_file not in urls:
                                        aggregated_recap[kind]["failed_count"] += 1
                                    continue
                                unique_entries |= parsed_entries
                                # A complete download is this source's data for this run, persisted or not: no fallback file is merged over it
                                url_has_data = downloaded = True
                                if cache_key not in processed_urls:
                                    aggregated_recap[kind]["downloaded_urls"] += 1
                                    aggregated_recap[kind]["total_lines"] += parsed_lines

                                try:
                                    cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode("utf-8") + b"\n" + url_content)
                                except Exception as e:
                                    cached, err = False, e
                                if not cached:
                                    run_failed = True
                                    # Not persisted: keep the fallback files so the next run can still fall back to them, and retry the write
                                    urls.update(fallback_files.values())
                                    LOGGER.error(f"Error while caching url content for {url}: {err}")
                                completed[cache_key] = (parsed_entries, bool(cached))
                            except Exception as e:
                                run_failed = True
                                LOGGER.debug(format_exc())
                                LOGGER.error(f"Exception while processing {kind} entries of {url} for {service} :\n{e}")
                                if cache_key not in rejected_urls and cache_key not in processed_urls:
                                    aggregated_recap[kind]["failed_count"] += 1
                                rejected_urls.add(cache_key)
                except BaseException as e:
                    # Only a transport error (download or file read) reaches here: it fails the URL for every kind
                    run_failed = True
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while getting {service} blacklist from {url} :\n{e}")
                    failed_urls.add(url)
                    if cache_key not in processed_urls:
                        aggregated_recap[kind]["failed_count"] += 1
                finally:
                    try:
                        if cache_error and not downloaded:
                            raise cache_error
                        if (use_cached_url or url in failed_urls or cache_key in rejected_urls) and isinstance(cached_url, dict):
                            cached_entries = read_cached_entries(kind, cached_url.get("data", b""))
                            if cached_entries:
                                unique_entries |= cached_entries
                                url_has_data = True

                        if not url_has_data:
                            for fallback_url, fallback_file in fallback_files.items():
                                fallback_cache = JOB.get_cache(fallback_file, with_info=True, with_data=True)
                                fallback_entries = read_cached_entries(kind, fallback_cache.get("data", b"")) if isinstance(fallback_cache, dict) else set()
                                if fallback_entries:
                                    LOGGER.warning(f"{url} has no valid {kind} data yet, {service} keeps using the cached content of {fallback_url}")
                                    unique_entries |= fallback_entries
                                    urls.add(fallback_file)
                                    url_has_data = True
                                    break
                    except BaseException as e:
                        run_failed = True
                        LOGGER.debug(format_exc())
                        LOGGER.error(f"Exception while getting {service} blacklist from cached {url} :\n{e}")
                        if url not in failed_urls and cache_key not in rejected_urls and cache_key not in processed_urls:
                            aggregated_recap[kind]["failed_count"] += 1
                        rejected_urls.add(cache_key)
                        if not downloaded:
                            # Its data exists but cannot be read: the source is not "without data", so the published list must not be rebuilt without it
                            frozen = True
                            urls.update(fallback_files.values())
                            LOGGER.warning(f"Cannot read the cached data of {url} for {service} {kind}, the published {kind}.list is left unchanged")
                    # Mark URL as processed to avoid double counting
                    processed_urls.add(cache_key)
                    urls.add(url_file)
                    url_consumers[url] -= 1
                    if not url_consumers[url]:
                        fetched.pop(url, None)
                        for done_kind in KINDS:
                            completed.pop((url, done_kind), None)
                        body = resp = None

            if frozen:
                continue

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
                run_failed = True
                continue

            list_changed = True

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
            deleted, err = JOB.del_cache(url_file.name)
            if not deleted:
                LOGGER.warning(f"Couldn't delete url file {url_file} from cache : {err}")

    status = exit_status()
except SystemExit as e:
    status = e.code
except BaseException as e:
    run_failed = True
    status = exit_status()
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running blacklist-download.py :\n{e}")

sys_exit(status)
