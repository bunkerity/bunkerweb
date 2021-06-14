from Config import Config
import utils
import os
class AutoConf :

	def __init__(self, swarm, api) :
		self.__swarm = swarm
		self.__servers = {}
		self.__instances = {}
		self.__env = {}
		self.__config = Config(self.__swarm, api)

	def get_server(self, id) :
		if id in self.__servers :
			return self.__servers[id]
		return False

	def reload(self) :
		return self.__config.reload(self.__instances)

	def __gen_env(self) :
		self.__env.clear()
		# TODO : check actual state (e.g. : running ?)
		for id, instance in self.__instances.items() :
			env = []
			if self.__swarm :
				env = instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]
			else :
				env = instance.attrs["Config"]["Env"]
			for entry in env :
				self.__env[entry.split("=")[0]] = entry.replace(entry.split("=")[0] + "=", "", 1)
			blacklist = ["NGINX_VERSION", "NJS_VERSION", "PATH", "PKG_RELEASE"]
			for entry in blacklist :
				if entry in self.__env :
					del self.__env[entry]
		if not "SERVER_NAME" in self.__env or self.__env["SERVER_NAME"] == "" :
			self.__env["SERVER_NAME"] = []
		else :
			self.__env["SERVER_NAME"] = self.__env["SERVER_NAME"].split(" ")
		for server in self.__servers :
			(id, name, labels) = self.__get_infos(self.__servers[server])
			first_server = labels["bunkerized-nginx.SERVER_NAME"].split(" ")[0]
			for label in labels :
				if label.startswith("bunkerized-nginx.") :
					self.__env[first_server + "_" + label.replace("bunkerized-nginx.", "", 1)] = labels[label]
			for server_name in labels["bunkerized-nginx.SERVER_NAME"].split(" ") :
				if not server_name in self.__env["SERVER_NAME"] :
					self.__env["SERVER_NAME"].append(server_name)
		self.__env["SERVER_NAME"] = " ".join(self.__env["SERVER_NAME"])

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
			self.__gen_env()
			if self.__swarm and len(self.__instances) == 1 :
				if self.__config.generate(self.__env) :
					utils.log("[*] Initial config succeeded")
					if not self.__config.swarm_wait(self.__instances) :
						utils.log("[!] Removing bunkerized-nginx instances from list")
						del self.__instances[id]
				else :
					utils.log("[!] Initial config failed")
			# TODO : wait while unhealthy if not swarm
			utils.log("[*] bunkerized-nginx instance created : " + name + " / " + id)

		elif event == "start" :
			self.__instances[id].reload()
			self.__gen_env()
			utils.log("[*] bunkerized-nginx instance started : " + name + " / " + id)

		elif event == "die" :
			self.__instances[id].reload()
			self.__gen_env()
			utils.log("[*] bunkerized-nginx instance stopped : " + name + " / " + id)

		elif event == "destroy" or event == "remove" :
			del self.__instances[id]
			self.__gen_env()
			utils.log("[*] bunkerized-nginx instance removed : " + name + " / " + id)

	def __process_server(self, instance, event, id, name, labels) :

		vars = { k.replace("bunkerized-nginx.", "", 1) : v for k, v in labels.items() if k.startswith("bunkerized-nginx.")}

		if event == "create" :
			utils.log("[*] Generating config for " + vars["SERVER_NAME"] + " ...")
			self.__servers[id] = instance
			self.__gen_env()
			if self.__config.generate(self.__env) :
				utils.log("[*] Generated config for " + vars["SERVER_NAME"])
				if self.__swarm :
					utils.log("[*] Activating config for " + vars["SERVER_NAME"] + " ...")
					if self.__config.reload(self.__instances) :
						utils.log("[*] Activated config for " + vars["SERVER_NAME"])
					else :
 						utils.log("[!] Can't activate config for " + vars["SERVER_NAME"])
			else :
				utils.log("[!] Can't generate config for " + vars["SERVER_NAME"])
				del self.__servers[id]
				self.__gen_env()
				self.__config.generate(self.__env)

		elif event == "start" :
			if id in self.__servers :
				self.__servers[id].reload()
				utils.log("[*] Activating config for " + vars["SERVER_NAME"] + " ...")
				self.__gen_env()
				if self.__config.reload(self.__instances) :
					utils.log("[*] Activated config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't activate config for " + vars["SERVER_NAME"])

		elif event == "die" :
			if id in self.__servers :
				self.__servers[id].reload()
				utils.log("[*] Deactivating config for " + vars["SERVER_NAME"])
				self.__gen_env()
				if self.__config.reload() :
					utils.log("[*] Deactivated config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't deactivate config for " + vars["SERVER_NAME"])

		elif event == "destroy" or event == "remove" :
			if id in self.__servers :
				utils.log("[*] Removing config for " + vars["SERVER_NAME"])
				del self.__servers[id]
				self.__gen_env()
				if self.__config.generate(self.__env) :
					utils.log("[*] Removed config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't remove config for " + vars["SERVER_NAME"])
				utils.log("[*] Deactivating config for " + vars["SERVER_NAME"])
				if self.__config.reload(self.__instances) :
					utils.log("[*] Deactivated config for " + vars["SERVER_NAME"])
				else :
					utils.log("[!] Can't deactivate config for " + vars["SERVER_NAME"])

