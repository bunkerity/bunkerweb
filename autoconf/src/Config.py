#!/usr/bin/python3

import utils
import subprocess, shutil, os, traceback, requests, time

from Controller import ControllerType

from logger import log

class Config :

	def __init__(type, api_uri) :
		self.__type = type
		self.__api_uri = api_uri

	def gen(env) :
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
				log("CONFIG", "INFO", "generator output : " + stdout)
			if stderr != "" :
				log("CONFIG", "ERROR", "generator error : " + stderr)

			# We're done
			if proc.returncode == 0 :
				if self.__type == ControllerType.SWARM or self.__type == ControllerType.KUBERNETES :
					return self.__jobs()
				return True
			log("CONFIG", "ERROR", "error while generating config (return code = " + str(proc.returncode) + ")")

		except Exception as e :
			log("CONFIG", "ERROR", "exception while generating site config : " + traceback.format_exc())
		return False

	def reload(self, instances) :
		ret = True
		if self.__type == ControllerType.DOCKER :
			for instance in instances :
				try :
					instance.kill("SIGHUP")
				except :
					ret = False
		elif self.__type == ControllerType.SWARM :
			ret = self.__api_call(instances, "/reload")
		elif self.__type == ControllerType.KUBERNETES :
			ret = self.__api_call(instances, "/reload")
		return ret

	def __ping(self, instances) :
		return self.__api_call(instances, "/ping")

	def wait(self, instances) :
		ret = True
		if self.__type == ControllerType.DOCKER :
			ret = self.__wait_docker()
		elif self.__type == ControllerType.SWARM or self.__type == ControllerType.KUBERNETES :
			ret = self.__wait_api()
		return ret

	def __wait_docker(self, instances) :
		all_healthy = False
		i = 0
		while i < 120 :
			one_not_healthy = False
			for instance in instances :
				instance.reload()
				if instance.attrs["State"]["Health"]["Status"] != "healthy" :
					one_not_healthy = True
					break
			if not one_not_healthy :
				all_healthy = True
				break
			time.sleep(1)
			i += 1
		return all_healthy

	def __wait_api(self, instances) :
		try :
			with open("/etc/nginx/autoconf", "w") as f :
				f.write("ok")
			i = 1
			started = False
			while i <= 10 :
				time.sleep(i)
				if self.__ping(instances) :
					started = True
					break
				i = i + 1
				log("CONFIG", "INFO" "waiting " + str(i) + " seconds before retrying to contact bunkerized-nginx instances")
			if started :
				log("CONFIG", "INFO", "bunkerized-nginx instances started")
				return True
			else :
				log("CONFIG", "ERROR", "bunkerized-nginx instances are not started")
		except Exception as e :
			log("CONFIG", "ERROR", "exception while waiting for bunkerized-nginx instances : " + traceback.format_exc())
		return False

	def __api_call(self, instances, path) :
		ret = True
		urls = []
		if self.__type == ControllerType.SWARM :
			for instance in instances :
				name = instance.name
				for task in instance.tasks() :
					nodeID = task["NodeID"]
					taskID = task["ID"]
					url = "http://" + name + "." + nodeID + "." + taskID + ":8080" + self.__api_uri + path
					urls.append(url)
		elif self.__type == ControllerType.KUBERNETES :
			log("CONFIG", "ERROR", "TODO get urls for k8s")

		for url in urls :
			try :
				req = requests.post("http://" + fqdn + ":8080" + self.__api + path)
			except :
				pass
			if req and req.status_code == 200 and req.text == "ok" :
				log("CONFIG", "INFO", "successfully sent API order to " + url)
			else :
				log("CONFIG", "INFO", "failed API order to " + url)
				ret = False
		return ret
