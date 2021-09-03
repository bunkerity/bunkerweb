import docker, time
from threading import Lock

from logger import log

import Controller

class SwarmController(Controller.Controller) :

	def __init__(self, docker_host, api_uri, http_port) :
		super().__init__(Controller.Type.SWARM, api_uri=api_uri, lock=Lock(), http_port=http_port)
		self.__client = docker.DockerClient(base_url=docker_host)

	def __get_instances(self) :
		return self.__client.services.list(filters={"label" : "bunkerized-nginx.AUTOCONF"})

	def __get_services(self) :
		return self.__client.services.list(filters={"label" : "bunkerized-nginx.SERVER_NAME"})

	def get_env(self) :
		env = {}
		for instance in self.__get_instances() :
			for variable in instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"] :
				env[variable.split("=")[0]] = variable.replace(variable.split("=")[0] + "=", "", 1)
		first_servers = []
		if "SERVER_NAME" in env and env["SERVER_NAME"] != "" :
			first_servers = env["SERVER_NAME"].split(" ")
		for service in self.__get_services() :
			first_server = service.attrs["Spec"]["Labels"]["bunkerized-nginx.SERVER_NAME"].split(" ")[0]
			first_servers.append(first_server)
			for variable, value in service.attrs["Spec"]["Labels"].items() :
				if variable.startswith("bunkerized-nginx.") and variable != "bunkerized-nginx.AUTOCONF" :
					env[first_server + "_" + variable.replace("bunkerized-nginx.", "", 1)] = value
		if len(first_servers) == 0 :
			env["SERVER_NAME"] = ""
		else :
			env["SERVER_NAME"] = " ".join(first_servers)
		return self._fix_env(env)

	def process_events(self, current_env) :
		old_env = current_env
		# TODO : check why filter isn't working as expected
		#for event in self.__client.events(decode=True, filters={"type": "service", "label": ["bunkerized-nginx.AUTOCONF", "bunkerized-nginx.SERVER_NAME"]}) :
		for event in self.__client.events(decode=True, filters={"type": "service"}) :
			new_env = self.get_env()
			if new_env != old_env :
				self.lock.acquire()
				try :
					if not self.gen_conf(new_env) :
						raise Exception("can't generate configuration")
					if not self.send() :
						raise Exception("can't send configuration")
					if not self.reload() :
						raise Exception("can't reload configuration")
					self.__old_env = new_env.copy()
					log("CONTROLLER", "INFO", "successfully loaded new configuration")
				except Exception as e :
					log("controller", "ERROR", "error while computing new event : " + str(e))
				self.lock.release()

	def reload(self) :
		return self._reload(self.__get_instances())

	def send(self) :
		return self._send(self.__get_instances())

	def wait(self) :
		self.lock.acquire()
		try :
			# Wait for a service
			instances = self.__get_instances()
			while len(instances) == 0 :
				time.sleep(1)
				instances = self.__get_instances()
			# Generate first config
			env = self.get_env()
			if not self.gen_conf(env) :
				self.lock.release()
				return False, env
			# Wait for nginx
			self.lock.release()
			return self._config.wait(instances), env
		except :
			pass
		self.lock.release()
		return False, {}
