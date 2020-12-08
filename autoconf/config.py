#!/usr/bin/python3

import utils
import subprocess, shutil

def generate(vars) :
	vars_defaults = vars.copy()
	vars_defaults.update(os.environ)
	vars_defaults.update(vars)
	subprocess.run(["/opt/entrypoint/site-config.sh", vars["SERVER_NAME"]], env=vars_defaults)
	utils.log("Generated config for " + vars["SERVER_NAME"])

def activate(vars) :
	replace_in_file("/etc/nginx/nginx.conf", "}", "include /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf;\n}")
	subprocess.run(["/usr/sbin/nginx", "-s", "reload"])
	utils.log("Activated config for " + vars["SERVER_NAME"])

def deactivate(vars) :
	replace_in_file("/etc/nginx/nginx.conf", "include /etc/nginx/" + vars["SERVER_NAME"] + "/server.conf;\n", "")
	subprocess.run(["/usr/sbin/nginx", "-s", "reload"])
	utils.log("Deactivated config for " + vars["SERVER_NAME"])

def remove(vars) :
	shutil.rmtree("/etc/nginx/" + vars["SERVER_NAME"])
	utils.log("Removed config for " + vars["SERVER_NAME"])
