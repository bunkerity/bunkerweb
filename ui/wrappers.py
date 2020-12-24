#!/usr/bin/python3

import utils, config
import docker, os, stat, sys

def get_client() :
	endpoint = "/var/run/docker.sock"
	if not os.path.exists(endpoint) or not stat.S_ISSOCK(os.stat(endpoint).st_mode) :
		return False, "Can't connect to /var/run/docker.sock (is it mounted ?)"
	try :
		client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
	except Exception as e :
		return False, "Can't instantiate DockerClient : " + str(e)
	return True, client

def get_containers(label) :
	check, client = get_client()
	if not check :
		return check, client
	try :
		containers = client.containers.list(all=True, filters={"label" : "bunkerized-nginx." + label})
	except docker.errors.APIError as e :
		return False, "Docker API error " + str(e)
	return True, containers

def get_instances() :
	return get_containers("UI")

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

def new_service(env) :
	return True, "Web service " + env["SERVER_NAME"] + " has been added."

def edit_service(old_server_name, env) :
	return True, "Web service " + old_server_name + " has been edited."

def delete_service(server_name) :
	return True, "Web service " + server_name + " has been deleted."

def operation_service(form, env) :
	if form["operation"] == "new" :
		return new_service(env)
	if form["operation"] == "edit" :
		return edit_service(form["OLD_SERVER_NAME"], env)
	if form["operation"] == "delete" :
		return delete_service(form["SERVER_NAME"])
	return False, "Wrong operation parameter."

def reload_instance(id) :
	return True, "Instance " + id + " has been reloaded."

def start_instance(id) :
	return True, "Instance " + id + " has been started."

def stop_instance(id) :
	return True, "Instance " + id + " has been stopped."

def restart_instance(id) :
	return True, "Instance " + id + " has been restarted."

def delete_instance(id) :
	return True, "Instance " + id + " has been deleted."

def operation_instance(form) :
	if form["operation"] == "reload" :
		return reload_instance(form["INSTANCE_ID"])
	if form["operation"] == "start" :
		return start_instance(form["INSTANCE_ID"])
	if form["operation"] == "stop" :
		return stop_instance(form["INSTANCE_ID"])
	if form["operation"] == "restart" :
		return restart_instance(form["INSTANCE_ID"])
	if form["operation"] == "delete" :
		return delete_instance(form["INSTANCE_ID"])
	return False, "Wrong operation parameter."
