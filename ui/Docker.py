import docker

class Docker :

	def __init__(self, docker_host) :
		self.__client = docker.DockerClient(base_url=docker_host)

	def get_instances(self) :
		return self.__client.containers.list(all=True, filters={"label" : "bunkerized-nginx.UI"})

	def reload_instances(self) :
		for instance in self.get_instances() :
			instance.kill(signal="SIGHUP")
		return True

	def get_instance(self, id) :
		return self.__client.containers.get(id)

	def reload_instance(self, id) :
		if self.get_instance(id).status == "running" :
			self.get_instance(id).kill(signal="SIGHUP")
			return "Instance " + id + " has been reloaded."
		return "Instance " + id + " is not running, skipping reload."

	def start_instance(self, id) :
		self.get_instance(id).start()
		return "Instance " + id + " has been started."

	def stop_instance(self, id) :
		self.get_instance(id).stop()
		return "Instance " + id + " has been stopped."

	def restart_instance(self, id) :
		self.get_instance(id).restart()
		return "Instance " + id + " has been restarted."

	def delete_instance(self, id) :
		self.get_instance(id).remove(v=True, force=True)
		return "Instance " + id + " has been deleted."
