import docker
from Controller import Controller, ControllerType
import utils

class SwarmController(Controller) :

	def __init__(self) :
		super().__init__(ControllerType.SWARM)
		# TODO : honor env vars like DOCKER_HOST
		self.__client = docker.DockerClient(base_url='unix:///var/run/docker.sock')

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
		if "SERVER_NAME" in env :
			first_servers = env["SERVER_NAME"].split(" ")
		for service in self.__get_services() :
			first_server = service.attrs["Spec"]["Labels"]["bunkerized-nginx.SERVER_NAME"].split(" ")[0]
			first_servers.append(first_server)
			for variable, value in service.attrs["Spec"]["Labels"].items() :
				if variable.startswith("bunkerized-nginx.") :
					env[first_server + "_" + variable.replace("bunkerized-nginx.", "", 1)] = value
		env["SERVER_NAME"] = " ".join(first_servers)
		return self._fix_env(env)

	def process_events(self, current_env) :
		old_env = current_env
		for event in client.events(decode=True, filter={"type": "service", "label": ["bunkerized-nginx.AUTOCONF", "bunkerized-nginx.SERVER_NAME"]}) :
			new_env = self.get_env()
			if new_env != old_env :
				if (self.gen_conf(new_env)) :
					old_env.copy(new_env)
					utils.log("[*] Successfully generated new configuration")
