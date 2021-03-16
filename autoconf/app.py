#!/usr/bin/python3

from AutoConf import AutoConf
from ReloadServer import run_reload_server
import utils
import docker, os, stat, sys, select, threading

# Connect to the endpoint
endpoint = "/var/run/docker.sock"
if not os.path.exists(endpoint) or not stat.S_ISSOCK(os.stat(endpoint).st_mode) :
	utils.log("[!] /var/run/docker.sock not found (is it mounted ?)")
	sys.exit(1)
try :
	client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
except Exception as e :
	utils.log("[!] Can't instantiate DockerClient : " + str(e))
	sys.exit(2)

# Check if we are in Swarm mode
swarm = os.getenv("SWARM_MODE") == "yes"

# Our object to process events
api = ""
if swarm :
	api = os.getenv("API_URI")
autoconf = AutoConf(swarm, api)
lock = threading.Lock()
if swarm :
	(server, thread) = run_reload_server(autoconf, lock)

# Get all bunkerized-nginx instances and web services created before
try :
	if swarm :
		before = client.services.list(filters={"label" : "bunkerized-nginx.AUTOCONF"}) + client.services.list(filters={"label" : "bunkerized-nginx.SERVER_NAME"})
	else :
		before = client.containers.list(all=True, filters={"label" : "bunkerized-nginx.AUTOCONF"}) + client.containers.list(filters={"label" : "bunkerized-nginx.SERVER_NAME"})
except docker.errors.APIError as e :
	utils.log("[!] Docker API error " + str(e))
	sys.exit(3)

# Process them before events
with lock :
	autoconf.pre_process(before)

# Process events received from Docker
try :
	for event in client.events(decode=True) :

		# Process only container/service events
		if (swarm and event["Type"] != "service") or (not swarm and event["Type"] != "container") :
			continue

		# Get Container/Service object
		try :
			if swarm :
				server = client.services.get(service_id=event["Actor"]["ID"])
			else :
				server = client.containers.get(event["id"])
		except docker.errors.NotFound as e :
			continue

		# Process the event
		with lock :
			autoconf.process(server, event["Action"])

except docker.errors.APIError as e :
	utils.log("[!] Docker API error " + str(e))
	sys.exit(4)
