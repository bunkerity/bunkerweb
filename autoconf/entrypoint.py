#!/usr/bin/python3

import utils, config
import docker, os, stat, sys

def process(container, event) :
	global instances, containers

	# Process instance event
	if "bunkerized-nginx.AUTOCONF" in container.labels :
		if event == "create" :
			instances[container.id] = container
			utils.log("[*] bunkerized-nginx instance created : " + container.name + " / " + container.id)
		elif event == "start" :
			instances[container.id].reload()
			utils.log("[*] bunkerized-nginx instance started : " + container.name + " / " + container.id)
		elif event == "die" :
			instances[container.id].reload()
			utils.log("[*] bunkerized-nginx instance stopped : " + container.name + " / " + container.id)
		elif event == "destroy" :
			del instances[container.id]
			utils.log("[*] bunkerized-nginx instance removed : " + container.name + " / " + container.id)

	# Process container event
	elif "bunkerized-nginx.SERVER_NAME" in container.labels :
		# Convert labels to env vars
		vars = { k.replace("bunkerized-nginx.", "", 1) : v for k, v in container.labels.items() if k.startswith("bunkerized-nginx.")}
		if event == "create" :
			if config.generate(instances, vars) :
				utils.log("[*] Generated config for " + vars["SERVER_NAME"])
				containers[container.id] = container
			else :
				utils.log("[!] Can't generate config for " + vars["SERVER_NAME"])
		elif event == "start" :
			containers[container.id].reload()
			if config.activate(instances, vars) :
				utils.log("[*] Activated config for " + vars["SERVER_NAME"])
			else :
				utils.log("[!] Can't activate config for " + vars["SERVER_NAME"])
		elif event == "die" :
			containers[container.id].reload()
			if config.deactivate(instances, vars) :
				utils.log("[*] Deactivated config for " + vars["SERVER_NAME"])
			else :
				utils.log("[!] Can't deactivate config for " + vars["SERVER_NAME"])
		elif event == "destroy" :
			del containers[container.id]
			if config.remove(vars) :
				utils.log("[*] Removed config for " + vars["SERVER_NAME"])
			else :
				utils.log("[!] Can't remove config for " + vars["SERVER_NAME"])

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

# Get all bunkerized-nginx instances and web services created before
instances = {}
containers = {}
try :
	before = client.containers.list(all=True, filters={"label" : "bunkerized-nginx.AUTOCONF"}) + client.containers.list(all=True, filters={"label" : "bunkerized-nginx.SERVER_NAME"})
except docker.errors.APIError as e :
	utils.log("[!] Docker API error " + str(e))
	sys.exit(3)
for container in before :
	if container.status in ("restarting", "running", "created", "exited") :
		process(container, "create")
	if container.status == "running" :
		process(container, "start")

# Process events received from Docker
try :
	for event in client.events(decode=True) :

		# Process only container events
		if event["Type"] != "container" :
			continue

		# Get Container object
		try :
			container = client.containers.get(event["id"])
		except docker.errors.NotFound as e :
			continue

		# Check if there is an interesting label
		interesting = False
		for label in container.labels :
			if label in ("bunkerized-nginx.SERVER_NAME", "bunkerized-nginx.AUTOCONF") :
				interesting = True
				break
		if not interesting :
			continue

		# Process the event
		process(container, event["Action"])

except docker.errors.APIError as e :
	utils.log("[!] Docker API error " + str(e))
	sys.exit(4)
