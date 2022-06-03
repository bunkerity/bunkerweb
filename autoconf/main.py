#!/usr/bin/python3

import signal, os, traceback, time, subprocess

import sys
sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")
sys.path.append("/opt/bunkerweb/api")
sys.path.append("/opt/bunkerweb/job")

from SwarmController import SwarmController
from IngressController import IngressController
from DockerController import DockerController
from logger import log

# Get variables
swarm			= os.getenv("SWARM_MODE", "no") == "yes"
kubernetes		= os.getenv("KUBERNETES_MODE", "no") == "yes"
docker_host		= os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
wait_retry_interval	= int(os.getenv("WAIT_RETRY_INTERVAL", "5"))

def exit_handler(signum, frame) :
    log("AUTOCONF", "ℹ️", "Stop signal received, exiting...")
    os._exit(0)
signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)

try :

    # Setup /data folder if needed
    #if swarm or kubernetes :
    proc = subprocess.run(["/opt/bunkerweb/helpers/data.sh", "AUTOCONF"], stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if proc.returncode != 0 :
        os._exit(1)

    # Instantiate the controller
    if swarm :
        log("AUTOCONF", "ℹ️", "Swarm mode detected")
        controller = SwarmController(docker_host)
    elif kubernetes :
        log("AUTOCONF", "ℹ️", "Kubernetes mode detected")
        controller = IngressController()
    else :
        log("AUTOCONF", "ℹ️", "Docker mode detected")
        controller = DockerController(docker_host)

    # Wait for instances
    log("AUTOCONF", "ℹ️", "Waiting for BunkerWeb instances ...")
    instances = controller.wait(wait_retry_interval)
    log("AUTOCONF", "ℹ️", "BunkerWeb instances are ready 🚀")
    i = 1
    for instance in instances :
        log("AUTOCONF", "ℹ️", "Instance #" + str(i) + " : " + instance["name"])
        i += 1

    # Run first configuration
    ret = controller.apply_config()
    if not ret :
        log("AUTOCONF", "❌", "Error while applying initial configuration")
        os._exit(1)

    # Process events
    log("AUTOCONF", "ℹ️", "Processing events ...")
    controller.process_events()

except :
    log("AUTOCONF", "❌", "Exception while running autoconf :")
    print(traceback.format_exc())
    sys.exit(1)
