#!/usr/bin/python3

from ReloadServer import run_reload_server

import docker, os, stat, sys, select, threading

from DockerController import DockerController
from SwarmController import SwarmController
from IngressController import IngressController

from logger import log

# Get variables
swarm		= os.getenv("SWARM_MODE", "no") == "yes"
kubernetes	= os.getenv("KUBERNETES_MODE", "no") == "yes"
api_uri		= os.getenv("API_URI", "")
docker_host	= os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")

# Instantiate the controller
if swarm :
	log("autoconf", "INFO", "swarm mode detected")
	controller = SwarmController(docker_host, api_uri)
elif kubernetes :
	log("autoconf", "INFO", "kubernetes mode detected")
	controller = IngressController(api_uri)
else :
	log("autoconf", "INFO", "docker mode detected")
	controller = DockerController(docker_host)

# Run the reload server in background if needed
if swarm or kubernetes :
	log("autoconf", "INFO", "start reload server in background")
	(server, thread) = run_reload_server(controller)

# Apply the first config for existing services
current_env = controller.get_env()
if current_env != {} :
	log("autoconf", "INFO", "generating the initial configuration...")
	if controller.gen_conf(current_env) :
		log("autoconf", "INFO", "initial configuration successfully generated")
	else :
		log("autoconf", "ERROR", "error while generating initial configuration")

# Wait for instances
if controller.wait() :
	log("autoconf", "INFO", "bunkerized-nginx instances started")
else :
	log("autoconf", "ERROR", "bunkerized-nginx instances not started")

# Process events
log("autoconf", "INFO", "waiting for events ...")
controller.process_events(current_env)
