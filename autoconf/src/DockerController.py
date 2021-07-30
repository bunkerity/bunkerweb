import docker
import Controller

from logger import log

class DockerController(Controller.Controller) :

	def __init__(self) :
		super().__init__(Controller.Type.DOCKER)
		# TODO : honor env vars like DOCKER_HOST
		self.__client = docker.DockerClient(base_url='unix:///var/run/docker.sock')

	def __get_instances(self) :
		return self.__client.containers.list(filters={"label" : "bunkerized-nginx.AUTOCONF"})

	def __get_containers(self) :
		return self.__client.containers.list(filters={"label" : "bunkerized-nginx.SERVER_NAME"})

	def get_env(self) :
		env = {}
		for instance in self.__get_instances() :
			for variable in instance.attrs["Config"]["Env"] :
				env[variable.split("=")[0]] = variable.replace(variable.split("=")[0] + "=", "", 1)
		first_servers = []
		if "SERVER_NAME" in env and env["SERVER_NAME"] != "" :
			first_servers = env["SERVER_NAME"].split(" ")
		for container in self.__get_containers() :
			first_server = container.labels["bunkerized-nginx.SERVER_NAME"].split(" ")[0]
			first_servers.append(first_server)
			for variable, value in container.labels.items() :
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
		#for event in self.__client.events(decode=True, filters={"type": "container", "label": ["bunkerized-nginx.AUTOCONF", "bunkerized-nginx.SERVER_NAME"]}) :
		for event in self.__client.events(decode=True, filters={"type": "container"}) :
			new_env = self.get_env()
			if new_env != old_env :
				log("controller", "INFO", "generating new configuration")
				if self.gen_conf(new_env) :
					old_env = new_env.copy()
					log("controller", "INFO", "successfully generated new configuration")
					if self.reload() :
						log("controller", "INFO", "successful reload")
					else :
						log("controller", "ERROR", "failed reload")
				else :
					log("controller", "ERROR", "can't generate new configuration")

	def reload(self) :
		return self._reload(self.__get_instances())


	def wait(self) :
		# TODO : healthcheck ?
		return True
