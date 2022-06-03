#!/usr/bin/python3

import sys, os, subprocess, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger

def renew(domain) :
    cmd = "/opt/bunkerweb/deps/python/bin/certbot renew --cert-name " + domain + " --deploy-hook /opt/bunkerweb/core/letsencrypt/jobs/certbot-deploy.py"
    os.environ["PYTHONPATH"] = "/opt/bunkerweb/deps/python"
    proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=os.environ)
    return proc.returncode

status = 0

try :

    if os.getenv("MULTISITE") == "yes" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            if first_server == "" :
                continue
            if os.getenv(first_server + "_AUTO_LETS_ENCRYPT", os.getenv("AUTO_LETS_ENCRYPT")) != "yes" :
                continue
            if not os.path.exists("/etc/letsencrypt/live/" + first_server + "/cert.pem") :
                continue
            ret = renew(first_server)
            if ret != 0 :
                status = 2
                logger.log("LETS-ENCRYPT", "❌", "Certificates renewal for " + first_server + " failed")
            else :
                logger.log("LETS-ENCRYPT", "ℹ️", "Certificates renewal for " + first_server + " successful")            
            
    elif os.getenv("AUTO_LETS_ENCRYPT") == "yes" and os.getenv("SERVER_NAME") != "" :
        first_server = os.getenv("SERVER_NAME").split(" ")[0]
        if os.path.exists("/etc/letsencrypt/live/" + first_server + "/cert.pem") :
            ret = renew(first_server)
            if ret != 0 :
                status = 2
                logger.log("LETS-ENCRYPT", "❌", "Certificates renewal for " + first_server + " failed")
            else :
                logger.log("LETS-ENCRYPT", "ℹ️", "Certificates renewal for " + first_server + " successful")

except :
    status = 2
    logger.log("LETS-ENCRYPT", "❌", "Exception while running certbot-renew.py :")
    print(traceback.format_exc())

sys.exit(status)