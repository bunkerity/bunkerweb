#!/usr/bin/python3

import utils
import subprocess, shutil, os, traceback, requests, time

class Config :

	def __init__(self, swarm, api) :
		self.__swarm = swarm
		self.__api = api

	def initconf(self, instances) :
		try :
			for instance_id, instance in instances.items() :
				env = instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]
				break
			vars = {}
			for var_value in env :
				var = var_value.split("=")[0]
				value = var_value.replace(var + "=", "", 1)
				vars[var] = value

			utils.log("[*] Generating global config ...")
			if not self.globalconf(instances) :
				utils.log("[!] Can't generate global config")
				return False
			utils.log("[*] Generated global config")

			if "SERVER_NAME" in vars and vars["SERVER_NAME"] != "" :
				for server in vars["SERVER_NAME"].split(" ") :
					vars_site = vars.copy()
					vars_site["SERVER_NAME"] = server
					utils.log("[*] Generating config for " + vars["SERVER_NAME"] + " ...")
					if not self.generate(instances, vars_site) or not self.activate(instances, vars_site, reload=False) :
						utils.log("[!] Can't generate/activate site config for " + server)
						return False
					utils.log("[*] Generated config for " + vars["SERVER_NAME"])
			with open("/etc/nginx/autoconf", "w") as f :
				f.write("ok")

			utils.log("[*] Waiting for bunkerized-nginx tasks ...")
			i = 1
			started = False
			while i <= 10 :
				time.sleep(i)
				if self.__ping(instances) :
					started = True
					break
				i = i + 1
				utils.log("[!] Waiting " + str(i) + " seconds before retrying to contact bunkerized-nginx tasks")
			if started :
				utils.log("[*] bunkerized-nginx tasks started")
				proc = subprocess.run(["/bin/su", "-s", "/opt/entrypoint/jobs.sh", "nginx"], env=vars, capture_output=True)
				return proc.returncode == 0
			else :
				utils.log("[!] bunkerized-nginx tasks are not started")
		except Exception as e :
			utils.log("[!] Error while initializing config : " + str(e))
		return False

	def generate(self, env) :
		try :
			# Write environment variables to a file
			with open("/tmp/variables.env", "w") as f :
				for k, v in env.items() :
					f.write(k + "=" + v + "\n")

			# Call the generator
			proc = subprocess.run(["/bin/su", "-c", "/opt/gen/main.py --settings /opt/settings.json --templates /opt/confs --output /etc/nginx --variables /tmp/variables.env", "nginx"], capture_output=True)

			# Print stdout/stderr
			stdout = proc.stdout.decode("ascii")
			stderr = proc.stderr.decode("ascii")
			if proc.stdout != "":
				utils.log("[*] Generator output : " + stdout)
			if proc.stderr != "" :
				utils.log("[*] Generator error : " + stderr)

			# We're done
			if proc.returncode == 0 :
				return True
			utils.log("[!] Error while generating site config for " + vars["SERVER_NAME"] + "  : return code = " + str(proc.returncode))

		except Exception as e :
			utils.log("[!] Exception while generating site config : " + str(e))
		return False

	def reload(self, instances) :
		return self.__api_call(instances, "/reload")

	def __ping(self, instances) :
		return self.__api_call(instances, "/ping")

	def __api_call(self, instances, path) :
		ret = True
		for instance_id, instance in instances.items() :
			# Reload the instance object just in case
			instance.reload()
			# Reload via API
			if self.__swarm :
				# Send POST request on http://serviceName.NodeID.TaskID:8000/action
				name = instance.name
				for task in instance.tasks() :
					if task["Status"]["State"] != "running" :
						continue
					nodeID = task["NodeID"]
					taskID = task["ID"]
					fqdn = name + "." + nodeID + "." + taskID
					req = False
					try :
						req = requests.post("http://" + fqdn + ":8080" + self.__api + path)
					except :
						pass
					if req and req.status_code == 200 :
						utils.log("[*] Sent API order " + path + " to instance " + fqdn + " (service.node.task)")
					else :
						utils.log("[!] Can't send API order " + path + " to instance " + fqdn + " (service.node.task)")
						ret = False
			# Send SIGHUP to running instance
			elif instance.status == "running" :
				try :
					instance.kill("SIGHUP")
					utils.log("[*] Sent SIGHUP signal to bunkerized-nginx instance " + instance.name + " / " + instance.id)
				except docker.errors.APIError as e :
					utils.log("[!] Docker error while sending SIGHUP signal : " + str(e))
					ret = False
		return ret
