#!/usr/bin/python3

import sys, os, traceback, tarfile
from io import BytesIO


sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")
sys.path.append("/opt/bunkerweb/api")

from logger import log
from API import API

status = 0

try :
    # Get env vars
    is_kubernetes_mode = os.getenv("KUBERNETES_MODE") == "yes"
    is_swarm_mode = os.getenv("SWARM_MODE") == "yes"
    is_autoconf_mode = os.getenv("AUTOCONF_MODE") == "yes"
    token = os.getenv("CERTBOT_TOKEN")

    # Cluster case
    if is_kubernetes_mode or is_swarm_mode or is_autoconf_mode :

        # Create tarball of /data/letsencrypt
        tgz = BytesIO()
        with tarfile.open(mode="w:gz", fileobj=tgz) as tf :
            tf.add("/data/letsencrypt", arcname=".")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}

        for variable, value in os.environ.items() :
            if not variable.startswith("CLUSTER_INSTANCE_") :
                continue
            endpoint = value.split(" ")[0]
            host = value.split(" ")[1]
            api = API(endpoint, host=host)
            sent, err, status, resp = api.request("POST", "/lets-encrypt/certificates", files=files)
            if not sent :
                status = 1
                log("LETS-ENCRYPT", "❌", "Can't send API request to " + api.get_endpoint() + "/lets-encrypt/certificates : " + err)
            else :
                if status != 200 :
                    status = 1
                    log("LETS-ENCRYPT", "❌", "Error while sending API request to " + api.get_endpoint() + "/lets-encrypt/certificates : status = " + resp["status"] + ", msg = " + resp["msg"])
                else :
                    log("LETS-ENCRYPT", "ℹ️", "Successfully sent API request to " + api.get_endpoint() + "/lets-encrypt/certificates")
                    sent, err, status, resp = api.request("POST", "/reload")
                    if not sent :
                        status = 1
                        log("LETS-ENCRYPT", "❌", "Can't send API request to " + api.get_endpoint() + "/reload : " + err)
                    else :
                        if status != 200 :
                            status = 1
                            log("LETS-ENCRYPT", "❌", "Error while sending API request to " + api.get_endpoint() + "/reload : status = " + resp["status"] + ", msg = " + resp["msg"])
                        else :
                            log("LETS-ENCRYPT", "ℹ️", "Successfully sent API request to " + api.get_endpoint() + "/reload")

    # Docker or Linux case
    else :
        cmd = "/usr/sbin/nginx -s reload"
        proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if proc.returncode != 0 :
            status = 1
            log("LETS-ENCRYPT", "❌", "Error while reloading nginx")
        else :
            log("LETS-ENCRYPT", "ℹ️", "Successfully reloaded nginx")

except :
    status = 1
    log("LETS-ENCRYPT", "❌", "Exception while running certbot-deploy.py :")
    print(traceback.format_exc())

sys.exit(status)
