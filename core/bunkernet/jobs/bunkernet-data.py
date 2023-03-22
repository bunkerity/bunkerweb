#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")
sys.path.append("/opt/bunkerweb/core/bunkernet/jobs")

import logger, jobs
from bunkernet import data

status = 0

try :

    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if os.getenv("MULTISITE") == "yes" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            if os.getenv(first_server + "_USE_BUNKERNET", os.getenv("USE_BUNKERNET")) == "yes" :
                bunkernet_activated = True
                break
    # Singlesite case
    elif os.getenv("USE_BUNKERNET") == "yes" :
        bunkernet_activated = True
    if not bunkernet_activated :
        logger.log("BUNKERNET", "ℹ️", "BunkerNet is not activated, skipping download...")
        os._exit(0)
    
    # Create directory if it doesn't exist
    os.makedirs("/opt/bunkerweb/cache/bunkernet", exist_ok=True)
    
    # Create empty file in case it doesn't exist
    if not os.path.isfile("/opt/bunkerweb/tmp/bunkernet-ip.list") :
        with open("/opt/bunkerweb/tmp/bunkernet-ip.list", "w") as f :
            pass
    
    # Check if ID is present
    if not os.path.isfile("/opt/bunkerweb/cache/bunkernet/instance.id") :
        logger.log("BUNKERNET", "❌", "Not downloading BunkerNet data because instance is not registered")
        os._exit(2)

    # Don't go further if the cache is fresh
    if jobs.is_cached_file("/opt/bunkerweb/cache/bunkernet/ip.list", "day") :
        logger.log("BUNKERNET", "ℹ️", "BunkerNet list is already in cache, skipping download...")
        os._exit(0)

    # Download data
    logger.log("BUNKERNET", "ℹ️", "Downloading BunkerNet data ...")
    ok, status, data = data()
    if not ok :
        logger.log("BUNKERNET", "❌", "Error while sending data request to BunkerNet API : " + data)
        os._exit(2)
    elif status == 429 :
        logger.log("BUNKERNET", "⚠️", "BunkerNet API is rate limiting us, trying again later...")
        os._exit(0)
    elif data["result"] != "ok" :
        logger.log("BUNKERNET", "❌", "Received error from BunkerNet API while sending db request : " + data["data"] + ", removing instance ID")
        os._exit(2)
    logger.log("BUNKERNET", "ℹ️", "Successfully downloaded data from BunkerNet API")

    # Writing data to file
    logger.log("BUNKERNET", "ℹ️", "Saving BunkerNet data ...")
    with open("/opt/bunkerweb/tmp/bunkernet-ip.list", "w") as f :
        for ip in data["data"] :
            f.write(ip + "\n")
    
    # Check if file has changed
    file_hash = jobs.file_hash("/opt/bunkerweb/tmp/bunkernet-ip.list")
    cache_hash = jobs.cache_hash("/opt/bunkerweb/cache/bunkernet/ip.list")
    if file_hash == cache_hash :
        logger.log("BUNKERNET", "ℹ️", "New file is identical to cache file, reload is not needed")
        os._exit(0)

    # Put file in cache
    cached, err = jobs.cache_file("/opt/bunkerweb/tmp/bunkernet-ip.list", "/opt/bunkerweb/cache/bunkernet/ip.list", file_hash)
    if not cached :
        logger.log("BUNKERNET", "❌", "Error while caching BunkerNet data : " + err)
        os._exit(2)
    logger.log("BUNKERNET", "ℹ️", "Successfully saved BunkerNet data")

    status = 1

except :
    status = 2
    logger.log("BUNKERNET", "❌", "Exception while running bunkernet-data.py :")
    print(traceback.format_exc())

sys.exit(status)
