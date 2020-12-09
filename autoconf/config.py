#!/usr/bin/python3

import utils
import subprocess, shutil, os

def generate(instances, vars) :
	try :
		# Get env vars from bunkerized-nginx instances
		vars_instances = {}
		for instance_id, instance in instances :
			for var_value in instance.attrs["Config"]["Env"] :
				var = var_value.split("=")[0]
				value = var_value.replace(var + "=", "", 1)
				vars_instances[var] = value
		vars_defaults = vars.copy()
		vars_defaults.update(vars_instances)
		vars_defaults.update(vars)
		# Call site-config.sh to generate the config
		proc = subprocess.run(["/opt/site-config.sh", vars["SERVER_NAME"]], env=vars_defaults, capture_output=True)
		if proc.returncode == 0 :
			return True
	except Exception as e :
		utils.log("[!] Error while generating config : " + str(e))
	return False

def activate(instances, vars) :
	try :
		# Check if file exists
		if not os.path.isfile("/etc/nginx/" + vars["SERVER_NAME"] + "/server.conf") :
			utils.log("[!] /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf doesn't exist")
			return False

		# Include the server conf
		utils.replace_in_file("/etc/nginx/nginx.conf", "}", "include /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf;\n}")

		# Send SIGHUP to all running instances
		for instance_id, instance in instances :
			if instance.status == "running" :
				try :
					instance.kill("SIGHUP")
					utils.log("[*] Sent SIGHUP signal to bunkerized-nginx instance " + instance.name + " / " + instance.id
				except docker.errors.APIError as e :
					utils.log("[!] Docker error while sending SIGHUP signal : " + str(e))
		return True
	except Exception as e :
		utils.log("[!] Error while activating config : " + str(e))
	return False

def deactivate(instances, vars) :
	try :
		# Check if file exists
		if not os.path.isfile("/etc/nginx/" + vars["SERVER_NAME"] + "/server.conf") :
			utils.log("[!] /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf doesn't exist")
			return False

		# Remove the include
		utils.replace_in_file("/etc/nginx/nginx.conf", "include /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf;\n", "")

		# Send SIGHUP to all running instances
		for instance_id, instance in instances :
			if instance.status == "running" :
				try :
					instance.kill("SIGHUP")
					utils.log("[*] Sent SIGHUP signal to bunkerized-nginx instance " + instance.name + " / " + instance.id
				except docker.errors.APIError as e :
					utils.log("[!] Docker error while sending SIGHUP signal : " + str(e))
		return True
	except Exception as e :
		utils.log("[!] Error while deactivating config : " + str(e))
	return False

def remove(instances, vars) :
	try :
		# Check if file exists
		if not os.path.isfile("/etc/nginx/" + vars["SERVER_NAME"] + "/server.conf") :
			utils.log("[!] /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf doesn't exist")
			return False

		# Remove the folder
		shutil.rmtree("/etc/nginx/" + vars["SERVER_NAME"])
		return True
	except Exception as e :
		utils.log("[!] Error while deactivating config : " + str(e))
	return False
