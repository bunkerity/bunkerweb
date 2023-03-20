#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger, jobs, requests, ipaddress

def check_line(line) :
    if "/" in line :
        try :
            ipaddress.ip_network(line)
            return True, line
        except :
            pass
    else :
        try :
            ipaddress.ip_address(line)
            return True, line
        except :
            pass
    return False, ""

status = 0

try :

    # Check if at least a server has Blacklist activated
    blacklist_activated = False
    # Multisite case
    if os.getenv("MULTISITE") == "yes" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            if os.getenv(first_server + "_USE_REAL_IP", os.getenv("USE_REAL_IP")) == "yes" :
                blacklist_activated = True
                break
    # Singlesite case
    elif os.getenv("USE_REAL_IP") == "yes" :
        blacklist_activated = True
    if not blacklist_activated :
        logger.log("REALIP", "ℹ️", "RealIP is not activated, skipping download...")
        os._exit(0)

    # Create directory if it doesn't exist
    os.makedirs("/opt/bunkerweb/cache/realip", exist_ok=True)

    # Don't go further if the cache is fresh
    if jobs.is_cached_file("/opt/bunkerweb/cache/realip/combined.list", "hour") :
        logger.log("REALIP", "ℹ️", "RealIP list is already in cache, skipping download...")
        os._exit(0)

    # Get URLs
    urls = []
    for url in os.getenv("REAL_IP_FROM_URLS", "").split(" ") :
        if url != "" and url not in urls :
            urls.append(url)

    # Download and write data to temp file
    i = 0
    f = open("/opt/bunkerweb/tmp/realip-combined.list", "w")
    for url in urls :
        try :
            logger.log("REALIP", "ℹ️", "Downloading RealIP list from " + url + " ...")
            resp = requests.get(url, stream=True)
            if resp.status_code != 200 :
                continue
            for line in resp.iter_lines(decode_unicode=True) :
                line = line.strip().split(" ")[0]
                if line == "" or line.startswith("#") or line.startswith(";") :
                    continue
                ok, data = check_line(line)
                if ok :
                    f.write(data + "\n")
                    i += 1
        except :
            status = 2
            logger.log("REALIP", "❌", "Exception while getting RealIP list from " + url + " :")
            print(traceback.format_exc())
    f.close()

    # Check if file has changed
    file_hash = jobs.file_hash("/opt/bunkerweb/tmp/realip-combined.list")
    cache_hash = jobs.cache_hash("/opt/bunkerweb/cache/realip/combined.list")
    if file_hash == cache_hash :
        logger.log("REALIP", "ℹ️", "New file is identical to cache file, reload is not needed")
        os._exit(0)

    # Put file in cache
    cached, err = jobs.cache_file("/opt/bunkerweb/tmp/realip-combined.list", "/opt/bunkerweb/cache/realip/combined.list", file_hash)
    if not cached :
        logger.log("REALIP", "❌", "Error while caching list : " + err)
        os._exit(2)

    logger.log("REALIP", "ℹ️", "Downloaded " + str(i) + " trusted IP/net")

    status = 1

except :
    status = 2
    logger.log("REALIP", "❌", "Exception while running realip-download.py :")
    print(traceback.format_exc())

sys.exit(status)
