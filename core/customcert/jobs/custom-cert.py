#!/usr/bin/python3

import sys, os, subprocess, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger, jobs

def check_cert(cert_path) :
    try :
        cache_path = "/opt/bunkerweb/cache/customcert/" + cert_path.replace("/", "_") + ".hash"
        current_hash = jobs.file_hash(cert_path)
        if not os.path.isfile(cache_path) :
            with open(cache_path, "w") as f :
                f.write(current_hash)
        old_hash = jobs.file_hash(cache_path)
        if old_hash == current_hash :
            return False
        with open(cache_path, "w") as f :
            f.write(current_hash)
        return True
    except :
        logger.log("CUSTOM-CERT", "❌", "Exception while running custom-cert.py (check_cert) :")
        print(traceback.format_exc())
    return False

status = 0

try :

    os.makedirs("/opt/bunkerweb/cache/customcert/", exist_ok=True)

    # Multisite case
    if os.getenv("MULTISITE") == "yes" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            if os.getenv(first_server + "_USE_CUSTOM_HTTPS", os.getenv("USE_CUSTOM_HTTPS")) != "yes" :
                continue
            if first_server == "" :
                continue
            cert_path = os.getenv(first_server + "_CUSTOM_HTTPS_CERT")
            logger.log("CUSTOM-CERT", "ℹ️", "Checking if certificate " + cert_path + " changed ...")
            need_reload = check_cert(cert_path)
            if need_reload :
                logger.log("CUSTOM-CERT", "ℹ️", "Detected change for certificate " + cert_path)
                status = 1
            else :
                logger.log("CUSTOM-CERT", "ℹ️", "No change for certificate " + cert_path)

    # Singlesite case
    elif os.getenv("USE_CUSTOM_HTTPS") == "yes" and os.getenv("SERVER_NAME") != "" :
        cert_path = os.getenv("CUSTOM_HTTPS_CERT")
        logger.log("CUSTOM-CERT", "ℹ️", "Checking if certificate " + cert_path + " changed ...")
        need_reload = check_cert(cert_path)
        if need_reload :
            logger.log("CUSTOM-CERT", "ℹ️", "Detected change for certificate " + cert_path)
            status = 1
        else :
            logger.log("CUSTOM-CERT", "ℹ️", "No change for certificate " + cert_path)

except :
    status = 2
    logger.log("CUSTOM-CERT", "❌", "Exception while running custom-cert.py :")
    print(traceback.format_exc())

sys.exit(status)
