#!/usr/bin/python3

import utils
import subprocess, shutil, os, traceback, requests, time

class Config :

	def __init__(self, swarm, api) :
		self.__swarm = swarm
		self.__api = api

	def __jobs(self, type) :
		utils.log("[*] Starting jobs (type = " + type + ") ...")
		proc = subprocess.run(["/bin/su", "-c", "/opt/bunkerized-nginx/entrypoint/" + type + "-jobs.sh", "nginx"], capture_output=True)
		stdout = proc.stdout.decode("ascii")
		stderr = proc.stderr.decode("ascii")
		if len(stdout) > 1 :
			utils.log("[*] Jobs stdout :")
			utils.log(stdout)
		if stderr != "" :
			utils.log("[!] Jobs stderr :")
			utils.log(stderr)
		if proc.returncode != 0 :
			utils.log("[!] Jobs error : return code != 0")
			return False
		return True

	def swarm_wait(self, instances) :
		try :
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
				return True
			else :
				utils.log("[!] bunkerized-nginx tasks are not started")
		except Exception as e :
			utils.log("[!] Error while waiting for Swarm tasks : " + str(e))
		return False

	def generate(self, env) :
		try :
			# Write environment variables to a file
			with open("/tmp/variables.env", "w") as f :
				for k, v in env.items() :
					f.write(k + "=" + v + "\n")

			# Call the generator
			proc = subprocess.run(["/bin/su", "-c", "/opt/bunkerized-nginx/gen/main.py --settings /opt/bunkerized-nginx/settings.json --templates /opt/bunkerized-nginx/confs --output /etc/nginx --variables /tmp/variables.env", "nginx"], capture_output=True)

			# Print stdout/stderr
			stdout = proc.stdout.decode("ascii")
			stderr = proc.stderr.decode("ascii")
			if len(stdout) > 1 :
				utils.log("[*] Generator output :")
				utils.log(stdout)
			if stderr != "" :
				utils.log("[*] Generator error :")
				utils.log(error)

			# We're done
			if proc.returncode == 0 :
				if self.__swarm :
					return self.__jobs("pre")
				return True
			utils.log("[!] Error while generating site config for " + env["SERVER_NAME"] + " : return code = " + str(proc.returncode))

		except Exception as e :
			utils.log("[!] Exception while generating site config : " + str(e))
		return False

	def reload(self, instances) :
		if self.__api_call(instances, "/reload") :
			if self.__swarm :
				return self.__jobs("post")
			return True
		return False

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
					if req and req.status_code == 200 and req.text == "ok" :
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
