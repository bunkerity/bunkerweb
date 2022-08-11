#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")
sys.path.append("/opt/bunkerweb/core/bunkernet/jobs")

import logger
from bunkernet import register, ping, get_id

status = 0

try :

    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if os.getenv("MULTISITE") == "yes" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            if os.getenv(first_server + "_USE_BUNKERNET", os.getenv("USE_BUNKERNET", "yes")) == "yes" :
                bunkernet_activated = True
                break
    # Singlesite case
    elif os.getenv("USE_BUNKERNET", "yes") == "yes" :
        bunkernet_activated = True
    if not bunkernet_activated :
        logger.log("BUNKERNET", "ℹ️", "BunkerNet is not activated, skipping registration...")
        os._exit(0)
    
    # Create directory if it doesn't exist
    os.makedirs("/opt/bunkerweb/cache/bunkernet", exist_ok=True)
    
    # Ask an ID if needed
    bunkernet_id = None
    if not os.path.isfile("/opt/bunkerweb/cache/bunkernet/instance.id") :
        logger.log("BUNKERNET", "ℹ️", "Registering instance on BunkerNet API ...")
        ok, status, data = register()
        if not ok :
            logger.log("BUNKERNET", "❌", "Error while sending register request to BunkerNet API : " + data)
            os._exit(1)
        elif status == 429 :
            logger.log("BUNKERNET", "⚠️", "BunkerNet API is rate limiting us, trying again later...")
            os._exit(0)
        elif status != 200 :
            logger.log("BUNKERNET", "❌", "Error " + str(status) + " from BunkerNet API : " + data["data"])
            os._exit(1)
        elif data["result"] != "ok" :
            logger.log("BUNKERNET", "❌", "Received error from BunkerNet API while sending register request : " + data["data"])
            os._exit(1)
        bunkernet_id = data["data"]
        logger.log("BUNKERNET", "ℹ️", "Successfully registered on BunkerNet API with instance id " + data["data"])
    else :
        with open("/opt/bunkerweb/cache/bunkernet/instance.id", "r") as f :
            bunkernet_id = f.read()
        logger.log("BUNKERNET", "ℹ️", "Already registered on BunkerNet API with instance id " + get_id())

    # Ping
    logger.log("BUNKERNET", "ℹ️", "Checking connectivity with BunkerNet API ...")
    bunkernet_ping = False
    for i in range(0, 5) :
        ok, status, data = ping(bunkernet_id)
        retry = False
        if not ok :
            logger.log("BUNKERNET", "❌", "Error while sending ping request to BunkerNet API : " + data)
            retry = True
        elif status == 429 :
            logger.log("BUNKERNET", "⚠️", "BunkerNet API is rate limiting us, trying again later...")
            retry = True
        elif status == 401 :
            logger.log("BUNKERNET", "⚠️", "Instance ID is not registered, removing it and retrying a register later...")
            os.remove("/opt/bunkerweb/cache/bunkernet/instance.id")
            os._exit(2)
        elif data["result"] != "ok" :
            logger.log("BUNKERNET", "❌", "Received error from BunkerNet API while sending ping request : " + data["data"] + ", removing instance ID")
            retry = True
        if not retry :
            bunkernet_ping = True
            break
        logger.log("BUNKERNET", "⚠️", "Waiting 1s and trying again ...")
        os.sleep(1)

    if bunkernet_ping :
        logger.log("BUNKERNET", "ℹ️", "Connectivity with BunkerWeb is successful !")
        status = 1
        if not os.path.isfile("/opt/bunkerweb/cache/bunkernet/instance.id") :
            with open("/opt/bunkerweb/cache/bunkernet/instance.id", "w") as f :
                f.write(bunkernet_id)
    else :
        logger.log("BUNKERNET", "❌", "Connectivity with BunkerWeb failed ...")
        status = 2

except :
    status = 2
    logger.log("BUNKERNET", "❌", "Exception while running bunkernet-register.py :")
    print(traceback.format_exc())

sys.exit(status)
