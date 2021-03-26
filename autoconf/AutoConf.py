from Config import Config
import utils
import os

class AutoConf :

	def __init__(self, swarm, api) :
		self.__swarm = swarm
		self.__servers = {}
		self.__instances = {}
		self.__sites = {}
		self.__config = Config(self.__swarm, api)

	def get_server(self, id) :
		if id in self.__servers :
			return self.__servers[id]
		return False

	def reload(self) :
		return self.__config.reload(self.__instances)

	def pre_process(self, objs) :
		for instance in objs :
			(id, name, labels) = self.__get_infos(instance)
			if "bunkerized-nginx.AUTOCONF" in labels :
				if self.__swarm :
					self.__process_instance(instance, "create", id, name, labels)
				else :
					if instance.status in ("restarting", "running", "created", "exited") :
						self.__process_instance(instance, "create", id, name, labels)
					if instance.status == "running" :
						self.__process_instance(instance, "start", id, name, labels)

		for server in objs :
			(id, name, labels) = self.__get_infos(server)
			if "bunkerized-nginx.SERVER_NAME" in labels :
				if self.__swarm :
					self.__process_server(server, "create", id, name, labels)
				else :
					if server.status in ("restarting", "running", "created", "exited") :
						self.__process_server(server, "create", id, name, labels)
					if server.status == "running" :
						self.__process_server(server, "start", id, name, labels)

	def process(self, obj, event) :
		utils.log("process - " + event)
		(id, name, labels) = self.__get_infos(obj)
		if "bunkerized-nginx.AUTOCONF" in labels :
			self.__process_instance(obj, event, id, name, labels)
		elif "bunkerized-nginx.SERVER_NAME" in labels :
			self.__process_server(obj, event, id, name, labels)

	def __get_infos(self, obj) :
		if self.__swarm :
			id = obj.id
			name = obj.name
			labels = obj.attrs["Spec"]["Labels"]
		else :
			id = obj.id
			name = obj.name
			labels = obj.labels
		return (id, name, labels)

	def __process_instance(self, instance, event, id, name, labels) :
		if event == "create" :
			self.__instances[id] = instance
			if self.__swarm and len(self.__instances) == 1 :
				if self.__config.initconf(self.__instances) :
					utils.log("[*] Initial config succeeded")
				else :
					utils.log("[!] Initial config failed")
			utils.log("[*] bunkerized-nginx instance created : " + name + " / " + id)
		elif event == "start" :
			self.__instances[id].reload()
			utils.log("[*] bunkerized-nginx instance started : " + name + " / " + id)
		elif event == "die" :
			self.__instances[id].reload()
			utils.log("[*] bunkerized-nginx instance stopped : " + name + " / " + id)
		elif event == "destroy" or event == "remove" :
			del self.__instances[id]
			if self.__swarm and len(self.__instances) == 0 :
				with open("/etc/crontabs/nginx", "w") as f :
					f.write("")
				if os.path.exists("/etc/nginx/autoconf") :
					os.remove("/etc/nginx/autoconf")
			utils.log("[*] bunkerized-nginx instance removed : " + name + " / " + id)

	def __process_server(self, instance, event, id, name, labels) :
		vars = { k.replace("bunkerized-nginx.", "", 1) : v for k, v in labels.items() if k.startswith("bunkerized-nginx.")}
		if event == "create" :
			utils.log("[*] Generating config for " + vars["SERVER_NAME"] + " ...")
			if self.__config.generate(self.__instances, vars) :
				utils.log("[*] Generated config for " + vars["SERVER_NAME"])
				self.__servers[id] = instance
				if self.__swarm :
					if self.__config.activate(self.__instances, vars) :
						utils.log("[*] Activated config for " + vars["SERVER_NAME"])
					else :
						utils.log("[!] Can't activate config for " + vars["SERVER_NAME"])
			else :
				utils.log("[!] Can't generate config for " + vars["SERVER_NAME"])
		elif event == "start" :
			if id in self.__servers :
				self.__servers[id].reload()
				utils.log("[*] Activating config for " + vars["SERVER_NAME"] + " ...")
				if self.__config.activate(self.__instances, vars) :
					utils.log("[*] Activated config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't activate config for " + vars["SERVER_NAME"])
		elif event == "die" :
			if id in self.__servers :
				self.__servers[id].reload()
				utils.log("[*] Deactivating config for " + vars["SERVER_NAME"])
				if self.__config.deactivate(self.__instances, vars) :
					utils.log("[*] Deactivated config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't deactivate config for " + vars["SERVER_NAME"])
		elif event == "destroy" or event == "remove" :
			utils.log(event)
			if id in self.__servers :
				if self.__swarm :
					utils.log("[*] Deactivating config for " + vars["SERVER_NAME"])
					if self.__config.deactivate(self.__instances, vars) :
						utils.log("[*] Deactivated config for " + vars["SERVER_NAME"])
					else :
						utils.log("[!] Can't deactivate config for " + vars["SERVER_NAME"])
				del self.__servers[id]
				utils.log("[*] Removing config for " + vars["SERVER_NAME"])
				if self.__config.remove(vars) :
					utils.log("[*] Removed config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't remove config for " + vars["SERVER_NAME"])
