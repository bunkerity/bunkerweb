#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger, jobs
import requests, datetime, gzip, maxminddb

status = 0

try :

    # Don't go further if the cache is fresh
    if jobs.is_cached_file("/opt/bunkerweb/cache/asn.mmdb", "month") :
        logger.log("JOBS", "ℹ️", "asn.mmdb is already in cache, skipping download...")
        os._exit(0)

    # Compute the mmdb URL
    today = datetime.date.today()
    mmdb_url = "https://download.db-ip.com/free/dbip-asn-lite-{}-{}.mmdb.gz".format(today.strftime("%Y"), today.strftime("%m"))

    # Download the mmdb file
    logger.log("JOBS", "ℹ️", "Downloading mmdb file from url " + mmdb_url + " ...")
    resp = requests.get(mmdb_url)
    
    # Save it to temp
    logger.log("JOBS", "ℹ️", "Saving mmdb file to tmp ...")
    with open("/opt/bunkerweb/tmp/asn.mmdb", "wb") as f :
        f.write(gzip.decompress(resp.content))
    
    # Try to load it
    logger.log("JOBS", "ℹ️", "Checking if mmdb file is valid ...")
    with maxminddb.open_database("/opt/bunkerweb/tmp/asn.mmdb") as reader :
        pass

    # Check if file has changed
    file_hash = jobs.file_hash("/opt/bunkerweb/tmp/asn.mmdb")
    cache_hash = jobs.cache_hash("/opt/bunkerweb/cache/asn.mmdb")
    if file_hash == cache_hash :
        logger.log("JOBS", "ℹ️", "New file is identical to cache file, reload is not needed")
        os._exit(0)

    # Move it to cache folder
    logger.log("JOBS", "ℹ️", "Moving mmdb file to cache ...")
    cached, err = jobs.cache_file("/opt/bunkerweb/tmp/asn.mmdb", "/opt/bunkerweb/cache/asn.mmdb", file_hash)
    if not cached :
        logger.log("JOBS", "❌", "Error while caching mmdb file : " + err)
        os._exit(2)

    # Success
    logger.log("JOBS", "ℹ️", "Downloaded new mmdb from " + mmdb_url)

    status = 1

except :
    status = 2
    logger.log("JOBS", "❌", "Exception while running mmdb-asn.py :")
    print(traceback.format_exc())

sys.exit(status)
