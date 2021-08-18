import docker, os, requests, subprocess

class Instances :

	def __init__(self, docker_host, api_uri) :
		try :
			self.__docker = docker.DockerClient(base_url=docker_host)
		except :
			self.__docker = None
		self.__api_uri = api_uri

	def __instance(self, id, name, type, status, data=None) :
		instance = {}
		instance["id"]		= id
		instance["name"]	= name
		instance["type"]	= type
		instance["status"]	= status
		instance["data"]	= data
		return instance

	def __api_request(self, instance, order) :
		result = True
		hosts = []
		if instance["type"] == "container" :
			hosts.append(instance["name"])
		elif instances["type"] == "service" :
			for task in instance["data"].tasks() :
				host = instance["name"] + "." + task["NodeID"] + "." + task["ID"]
				hosts.append(host)
		for host in hosts :
			try :
				req = requests.post("http://" + host + ":8080" + self.__api_uri + order)
				if not req or req.status_code != 200 or req.text != "ok" :
					result = False
			except :
				result = False
		return result

	def __instance_from_id(self, id) :
		instances = self.get_instances()
		for instance in instances :
			if instance["id"] == id :
				return instance
		raise Exception("Can't find instance with id " + id)

	def get_instances(self) :
		instances = []

		# Docker instances (containers or services)
		if self.__docker != None :
			for instance in self.__docker.containers.list(all=True, filters={"label" : "bunkerized-nginx.UI"}) :
				id = instance.id
				name = instance.name
				type = "container"
				status = "down"
				if instance.status == "running" :
					status = "up"
				instances.append(self.__instance(id, name, type, status, instance))
			is_swarm = True
			try :
				version = self.__docker.swarm.version
			except :
				is_swarm = False
			if is_swarm :
				for instance in self.__docker.services.list(filters={"label" : "bunkerized-nginx.UI"}) :
					id = instance.id
					name = instance.name
					type = "service"
					status = "down"
					desired_tasks = instance.attrs["ServiceStatus"]["DesiredTasks"]
					running_tasks = instance.attrs["ServiceStatus"]["RunningTasks"]
					if desired_tasks > 0 and (desired_tasks == running_tasks) :
						status = "up"
					instances.append(self.__instance(id, name, type, status, instance))

		# Local instance
		if os.path.exists("/usr/sbin/nginx") :
			id = "local"
			name = "local"
			type = "local"
			status = "down"
			if os.path.exists("/tmp/nginx.pid") :
				status = "up"
			instances.append(self.__instance(id, name, type, status))

		return instances

	def reload_instances(self) :
		all_reload = True
		for instance in self.get_instances() :
			if instance["status"] == "down" :
				all_reload = False
				continue
			if instance["type"] == "local" :
				proc = subprocess.run(["/usr/sbin/nginx", "-s", "reload"], capture_output=True)
				if proc.returncode != 0 :
					all_reload = False
			elif instance["type"] == "container" or instance["type"] == "service" :
				all_reload = self.__api_request(instance, "/reload")
		return all_reload

	def reload_instance(self, id) :
		instance = self.__instance_from_id(id)
		result = True
		if instance["type"] == "local" :
			proc = subprocess.run(["/usr/sbin/nginx", "-s", "reload"], capture_output=True)
			result = proc.returncode == 0
		elif instance["type"] == "container" or instance["type"] == "service" :
			result = self.__api_request(instance, "/reload")
		if result :
			return "Instance " + instance["name"] + " has been reloaded."
		return "Can't reload " + instance["name"]

	def start_instance(self, id) :
		instance = self.__instance_from_id(id)
		result = True
		if instance["type"] == "local" :
			proc = subprocess.run(["/usr/sbin/nginx", "-g", "daemon on;"], capture_output=True)
			result = proc.returncode == 0
		elif instance["type"] == "container" or instance["type"] == "service" :
			result = False #self.__api_request(instance, "/start")
		if result :
			return "Instance " + instance["name"] + " has been started."
		return "Can't start " + instance["name"]

	def stop_instance(self, id) :
		instance = self.__instance_from_id(id)
		result = True
		if instance["type"] == "local" :
			proc = subprocess.run(["/usr/sbin/nginx", "-s", "quit"], capture_output=True)
			result = proc.returncode == 0
		elif instance["type"] == "container" or instance["type"] == "service" :
			result = self.__api_request(instance, "/stop")
		if result :
			return "Instance " + instance["name"] + " has been stopped."
		return "Can't stop " + instance["name"]

	def restart_instance(self, id) :
		instance = self.__instance_from_id(id)
		result = True
		if instance["type"] == "local" :
			proc = subprocess.run(["/usr/sbin/nginx", "-s", "quit"], capture_output=True)
			if proc.returncode == 0 :
				proc = subprocess.run(["/usr/sbin/nginx", "-g", "daemon on;"], capture_output=True)
			result = proc.returncode == 0
		elif instance["type"] == "container" or instance["type"] == "service" :
			result = False #self.__api_request(instance, "/restart")
		if result :
			return "Instance " + instance["name"] + " has been restarted."
		return "Can't restart " + instance["name"]
