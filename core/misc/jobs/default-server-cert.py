#!/usr/bin/python3

import sys, os, subprocess, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger

status = 0

try :

    # Check if we need to generate a self-signed default cert for non-SNI "clients"
    need_default_cert = False
    if ((os.getenv("MULTISITE") == "no" and os.getenv("DISABLE_DEFAULT_SERVER") == "yes") and 
        (os.getenv("USE_CUSTOM_HTTPS") == "yes" or os.getenv("AUTO_LETS_ENCRYPT") == "yes" or os.getenv("GENERATE_SELF_SIGNED_SSL") == "yes")) :
        need_default_cert = True
    elif os.getenv("MULTISITE") == "no" :
        for first_server in os.getenv("SERVER_NAME").split(" ") :
            for check_var in ["USE_CUSTOM_HTTPS", "AUTO_LETS_ENCRYPT", "GENERATE_SELF_SIGNED_SSL"] :
                if os.getenv(first_server + "_" + check_var, os.getenv(check_var)) == "yes" :
                    need_default_cert = True
                    break
            if need_default_cert :
                break
    
    # Generate the self-signed certificate
    if need_default_cert :
        os.makedirs("/opt/bunkerweb/cache/default-server-cert", exist_ok=True)
        if not os.path.isfile("/opt/bunkerweb/cache/default-server-cert/cert.pem") :
            cmd = "openssl req -nodes -x509 -newkey rsa:4096 -keyout /opt/bunkerweb/cache/default-server-cert/cert.key -out /opt/bunkerweb/cache/default-server-cert/cert.pem -days 3650".split(" ")
            cmd.extend(["-subj", "\"/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/\""])
            proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if proc.returncode != 0 :
                logger.log("DEFAULT-SERVER-CERT", "❌", "Self-signed certificate generation failed for default server")
                status = 2
            else :
                logger.log("DEFAULT-SERVER-CERT", "ℹ️", "Successfully generated self-signed certificate for default server")
    else :
        logger.log("DEFAULT-SERVER-CERT", "ℹ️", "Skipping generation of self-signed certificate for default server (already present)")

except :
    status = 2
    logger.log("DEFAULT-SERVER-CERT", "❌", "Exception while running default-server-cert.py :")
    print(traceback.format_exc())

sys.exit(status)