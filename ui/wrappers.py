#!/usr/bin/python3

import utils
import docker, os, stat, sys, subprocess, shutil

def get_client() :
	endpoint = "/var/run/docker.sock"
	if not os.path.exists(endpoint) or not stat.S_ISSOCK(os.stat(endpoint).st_mode) :
		return False, "Can't connect to /var/run/docker.sock (is it mounted ?)"
	try :
		client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
	except Exception as e :
		return False, "Can't instantiate DockerClient : " + str(e)
	return True, client

def get_containers(client, label) :
	try :
		containers = client.containers.list(all=True, filters={"label" : "bunkerized-nginx." + label})
	except docker.errors.APIError as e :
		return False, "Docker API error " + str(e)
	return True, containers

def get_instances(client) :
	return get_containers(client, "UI")

def get_services() :
	services = []
	try :
		for root, dirs, files in os.walk("/etc/nginx") :
			for file in files :
				filepath = os.path.join(root, file)
				if filepath.endswith("/nginx.env") :
					with open(filepath, "r") as f :
						service = {}
						for line in f.readlines() :
							name = line.split("=")[0]
							value = line.replace(name + "=", "", 1).strip()
							service[name] = value
						services.append(service)
	except Exception as e :
		return False, str(e)
	return True, services

def reload_instances(client) :
	check, instances = get_instances(client)
	if not check :
		return check, instances
	i = 0
	for instance in instances :
		try :
			instance.kill(signal="SIGHUP")
		except docker.errors.APIError as e :
			return False, str(e)
		i += 1
	return True, i

def new_service(client, env) :
	proc = subprocess.run(["/bin/su", "-s", "/bin/sh", "-c", "/opt/entrypoint/site-config.sh" + " " + env["SERVER_NAME"], "nginx"], env=env, capture_output=True)
	if proc.returncode != 0 :
		return False, "Error code " + str(proc.returncode) + " while generating config."
	utils.replace_in_file("/etc/nginx/nginx.conf", "}", "include /etc/nginx/" + env["SERVER_NAME"] + "/server.conf;\n}")
	check, nb = reload_instances(client)
	if not check :
		return check, nb
	return True, "Web service " + env["SERVER_NAME"] + " has been added."

def edit_service(client, old_server_name, env) :
	check, delete = delete_service(client, old_server_name)
	if not check :
		return check, delete
	check, new = new_service(client, env)
	if not check :
		return check, new
	return True, "Web service " + old_server_name + " has been edited."

def delete_service(client, server_name) :
	if not os.path.isdir("/etc/nginx/" + server_name) :
		return False, "Config doesn't exist."
	try :
		shutil.rmtree("/etc/nginx/" + server_name)
	except Exception as e :
		return False, str(e)
	utils.replace_in_file("/etc/nginx/nginx.conf", "include /etc/nginx/" + server_name + "/server.conf;\n", "")
	check, nb = reload_instances(client)
	if not check :
		return check, nb
	return True, "Web service " + server_name + " has been deleted."

def operation_service(client, form, env) :
	if form["operation"] == "new" :
		return new_service(client, env)
	if form["operation"] == "edit" :
		return edit_service(client, form["OLD_SERVER_NAME"], env)
	if form["operation"] == "delete" :
		return delete_service(client, form["SERVER_NAME"])
	return False, "Wrong operation parameter."

def get_instance(client, id) :
	try :
		instance = client.containers.get(id)
		if not "bunkerized-nginx.UI" in instance.labels :
			raise docker.errors.NotFound()
	except Exception as e :
		return False, str(e)
	return True, instance

def reload_instance(client, id) :
	check, instance = get_instance(client, id)
	if not check :
		return check, instance
	try :
		instance.kill(signal="SIGHUP")
	except docker.errors.APIError as e :
		return False, str(e)
	return True, "Instance " + id + " has been reloaded."

def start_instance(client, id) :
	check, instance = get_instance(client, id)
	if not check :
		return check, instance
	try :
		instance.start()
	except docker.errors.APIError as e :
		return False, str(e)
	return True, "Instance " + id + " has been started."

def stop_instance(client, id) :
	check, instance = get_instance(client, id)
	if not check :
		return check, instance
	try :
		instance.stop()
	except docker.errors.APIError as e :
		return False, str(e)
	return True, "Instance " + id + " has been stopped."

def restart_instance(client, id) :
	check, instance = get_instance(client, id)
	if not check :
		return check, instance
	try :
		instance.restart()
	except docker.errors.APIError as e :
		return False, str(e)
	return True, "Instance " + id + " has been restarted."

def delete_instance(client, id) :
	check, instance = get_instance(client, id)
	if not check :
		return check, instance
	try :
		instance.remove(v=True, force=True)
	except docker.errors.APIError as e :
		return False, str(e)
	return True, "Instance " + id + " has been deleted."

def operation_instance(client, form) :
	if form["operation"] == "reload" :
		return reload_instance(client, form["INSTANCE_ID"])
	if form["operation"] == "start" :
		return start_instance(client, form["INSTANCE_ID"])
	if form["operation"] == "stop" :
		return stop_instance(client, form["INSTANCE_ID"])
	if form["operation"] == "restart" :
		return restart_instance(client, form["INSTANCE_ID"])
	if form["operation"] == "delete" :
		return delete_instance(client, form["INSTANCE_ID"])
	return False, "Wrong operation parameter."
