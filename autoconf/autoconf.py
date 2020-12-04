#!/usr/bin/python3

import docker, datetime, subprocess, shutil

def log(event) :
	print("[" + datetime.datetime.now().replace(microsecond=0) + "] AUTOCONF - " + event)

def replace_in_file(file, old_str, new_str) :
	with open(file) as f :
		data = f.read()
	data = data[::-1].replace(old_str[::-1], new_str[::-1], 1)[::-1]
	with open(file, "w") as f :
		f.write(data)

def generate(vars) :
	subprocess.run(["/opt/entrypoint/site-config.sh", vars["SERVER_NAME"]], env=vars)
	log("Generated config for " + vars["SERVER_NAME"])

def activate(vars) :
	replace_in_file("/etc/nginx/nginx.conf", "}", "include /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf;")
	subprocess.run(["/usr/sbin/nginx", "-s", "reload"])
	log("Activated config for " + vars["SERVER_NAME"])

def deactivate(vars) :
	replace_in_file("/etc/nginx/nginx.conf", "include /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf;", "")
	subprocess.run(["/usr/sbin/nginx", "-s", "reload"])
	log("Deactivated config for " + vars["SERVER_NAME"])

def remove(vars) :
	shutil.rmtree("/etc/nginx/" + vars["SERVER_NAME"])
	log("Removed config for " + vars["SERVER_NAME"])

def process(id, event, vars) :
	global containers
	if event == "create" :
		generate(labels)
		containers.append(id)
	elif event == "start" :
		activate(vars)
	elif event == "die" :
		deactivate(vars)
	elif event == "destroy" :
		remove(vars)
		containers.remove(id)

containers = []

client = docker.DockerClient(base_url='unix:///var/run/docker.sock')

# Process containers created before
for container in client.containers.list(all=True, filters={"label" : "bunkerized-nginx.SERVER_NAME"}) :

	# Extract bunkerized-nginx.* labels
	labels = container.labels.copy()
	for label in labels :
		if not label.startswith("bunkerized-nginx.") :
			del labels[label]
	# Remove bunkerized-nginx. on labels
	vars = { k.replace("bunkerized-nginx.", "", 1) : v for k, v in labels.items()}

	# Container is restarting or running
	if container.status == "restarting" or container.status == "running" :
		process(container.id, "create", vars)
		process(container.id, "activate", vars)

	# Container is created or exited
	if container.status == "created" or container.status == "exited" :
		process(container.id, "create", vars)

for event in client.events(decode=True) :

	# Process only container events
	if event["Type"] != "container" :
			continue

	# Check if a bunkerized-nginx.* label is present
	present = False
	for label in event["Actor"]["Attributes"] :
			if label.startswith("bunkerized-nginx.") :
					present = True
					break
	if not present :
			continue

	# Only process if we generated a config
	if not event["id"] in containers and event["Action"] != "create" :
			continue

	# Extract bunkerized-nginx.* labels
	labels = event["Actor"]["Attributes"].copy()
	for label in labels :
			if not label.startswith("bunkerized-nginx.") :
					del labels[label]
	# Remove bunkerized-nginx. on labels
	vars = { k.replace("bunkerized-nginx.", "", 1) : v for k, v in labels.items()}

	# Process the event
	process(event["id"], event["Action"], vars
