import docker

class Docker :

	def __init__(self) :
		self.__client = docker.DockerClient(base_url='unix:///var/run/docker.sock')

	def get_instances(self) :
		return self.__client.containers.list(all=True, filters={"label" : "bunkerized-nginx.UI"})

	def reload_instances(self) :
		for instance in self.get_instances() :
			instance.kill(signal="SIGHUP")
		return True

	def get_instance(self, id) :
		return self.__client.containers.get(id)

	def reload_instance(self, id) :
		return self.get_instance(id).kill(signal="SIGHUP")

	def start_instance(self, id) :
		return self.get_instance(id).start()

	def stop_instance(self, id) :
		return self.get_instance(id).stop()

	def restart_instance(self, id) :
		return self.get_instance(id).restart()

	def remove_instance(self, id) :
		return self.get_instance(id).remove(v=True, force=True)
