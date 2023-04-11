#!/usr/bin/python3

import sys, os, subprocess, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger

def generate_cert(first_server, days, subj) :
    if os.path.isfile("/opt/bunkerweb/cache/selfsigned/" + first_server + ".pem") :
        cmd = "openssl x509 -checkend 86400 -noout -in /opt/bunkerweb/cache/selfsigned/" + first_server + ".pem"
        proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if proc.returncode == 0 :
            logger.log("SELF-SIGNED", "ℹ️", "Self-signed certificate already present for " + first_server)
            return True, 0
    logger.log("SELF-SIGNED", "ℹ️", "Generating self-signed certificate for " + first_server)
    cmd = "openssl req -nodes -x509 -newkey rsa:4096 -keyout /opt/bunkerweb/cache/selfsigned/" + first_server + ".key -out /opt/bunkerweb/cache/selfsigned/" + first_server + ".pem -days " + days + " -subj " + subj
    proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if proc.returncode != 0 :
        logger.log("SELF-SIGNED", "❌", "Self-signed certificate generation failed for " + first_server)
        return False, 2
    logger.log("SELF-SIGNED", "ℹ️", "Successfully generated self-signed certificate for " + first_server)   
    return True, 1

status = 0

try :

    os.makedirs("/opt/bunkerweb/cache/selfsigned/", exist_ok=True)

    # Multisite case
    if os.getenv("MULTISITE") == "yes" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            if os.getenv(first_server + "_GENERATE_SELF_SIGNED_SSL", os.getenv("GENERATE_SELF_SIGNED_SSL")) != "yes" :
                continue
            if first_server == "" :
                continue
            if os.path.isfile("/opt/bunkerweb/cache/selfsigned/" + first_server + ".pem") :
                continue
            ret, ret_status = generate_cert(first_server, os.getenv(first_server + "_SELF_SIGNED_SSL_EXPIRY", "365"), os.getenv(first_server + "_SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"))
            if not ret :
                status = ret_status
            elif ret_status == 1 and ret_status != 2 :
                status = 1

    # Singlesite case
    elif os.getenv("GENERATE_SELF_SIGNED_SSL") == "yes" and os.getenv("SERVER_NAME") != "" :
        first_server = os.getenv("SERVER_NAME").split(" ")[0]
        ret, ret_status = generate_cert(first_server, os.getenv("SELF_SIGNED_SSL_EXPIRY", "365"), os.getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"))
        if not ret :
            status = ret_status
        elif ret_status == 1 and ret_status != 2 :
            status = 1

except :
    status = 2
    logger.log("SELF-SIGNED", "❌", "Exception while running self-signed.py :")
    print(traceback.format_exc())

sys.exit(status)
