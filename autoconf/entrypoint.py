#!/usr/bin/python3

import utils, config
import docker, os, stat, sys

def process(id, event, vars) :
	global containers
	if event == "create" :
		config.generate(vars)
		containers.append(id)
	elif event == "start" :
		config.activate(vars)
	elif event == "die" :
		config.deactivate(vars)
	elif event == "destroy" :
		config.remove(vars)
		containers.remove(id)

# Connect to the endpoint
endpoint = "/var/run/docker.sock"
if not os.path.exists(endpoint) or not stat.S_ISSOCK(os.stat(endpoint).st_mode) :
	print("[!] /var/run/docker.sock not found (is it mounted ?)")
	sys.exit(1)
try :
	client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
except Exception as e :
	print("[!] Can't instantiate DockerClient : " + str(e))
	sys.exit(2)

# Get all bunkerized-nginx instances
instances = []
try :
	instances = client.containers.list(all=True, filters={"label" : "bunkerized-nginx.AUTOCONF"})
except docker.errors.APIError as e :
	print("[!] Docker API error " + str(e))
	sys.exit(3)

# Get all containers created before and do the config
containers = []
try :
	containers_before = client.containers.list(all=True, filters={"label" : "bunkerized-nginx.SERVER_NAME"})
except docker.errors.APIerror as e :
	print("[!] Docker API error " + str(e))
	sys.exit(4)
for container in containers_before :
	if container.status in ("restarting", "running", "created", "exited") :
		process(container, "create")
	if container.status in ("restarting", "running") :
		process(container, "start")

# Process events received from Docker
try :
	for event in client.events(decode=True) :
		print(event)
except docker.errors.APIerror as e :
	print("[!] Docker API error " + str(e))
	sys.exit(5)
