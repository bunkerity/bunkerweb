from kubernetes import client, config, watch
from threading import Thread, Lock
import time

import Controller

from logger import log

class IngressController(Controller.Controller) :

	def __init__(self, api_uri, http_port) :
		super().__init__(Controller.Type.KUBERNETES, api_uri=api_uri, lock=Lock(), http_port=http_port)
		config.load_incluster_config()
		self.__api = client.CoreV1Api()
		self.__extensions_api = client.ExtensionsV1beta1Api()
		self.__old_env = {}

	def __get_pods(self) :
		return self.__api.list_pod_for_all_namespaces(watch=False, label_selector="bunkerized-nginx").items

	def __get_ingresses(self) :
		return self.__extensions_api.list_ingress_for_all_namespaces(watch=False, label_selector="bunkerized-nginx").items

	def __get_services(self, autoconf=False) :
		services = self.__api.list_service_for_all_namespaces(watch=False, label_selector="bunkerized-nginx").items
		if not autoconf :
			return services
		services_autoconf = []
		for service in services :
			if service.metadata.annotations != None and "bunkerized-nginx.AUTOCONF" in service.metadata.annotations :
				services_autoconf.append(service)
		return services_autoconf

	def __pod_to_env(self, pod_env) :
		env = {}
		for env_var in pod_env :
			env[env_var.name] = env_var.value
			if env_var.value == None :
				env[env_var.name] = ""
		return env

	def __annotations_to_env(self, annotations) :
		env = {}
		prefix = annotations["bunkerized-nginx.SERVER_NAME"].split(" ")[0] + "_"
		for annotation in annotations :
			if annotation.startswith("bunkerized-nginx.") and annotation.replace("bunkerized-nginx.", "", 1) != "" and annotation.replace("bunkerized-nginx.", "", 1) != "AUTOCONF" :
				env[prefix + annotation.replace("bunkerized-nginx.", "", 1)] = annotations[annotation]
		return env

	def __rules_to_env(self, rules, namespace="default") :
		env = {}
		first_servers = []
		for rule in rules :
			rule = rule.to_dict()
			prefix = ""
			if "host" in rule :
				prefix = rule["host"] + "_"
				first_servers.append(rule["host"])
			if not "http" in rule or not "paths" in rule["http"] :
				continue
			for path in rule["http"]["paths"] :
				env[prefix + "USE_REVERSE_PROXY"] = "yes"
				env[prefix + "REVERSE_PROXY_URL"] = path["path"]
				env[prefix + "REVERSE_PROXY_HOST"] = "http://" + path["backend"]["service_name"] + "." + namespace + ".svc.cluster.local:" + str(path["backend"]["service_port"])
		env["SERVER_NAME"] = " ".join(first_servers)
		return env

	def get_env(self) :
		pods = self.__get_pods()
		ingresses = self.__get_ingresses()
		services = self.__get_services()
		env = {}
		first_servers = []
		for pod in pods :
			env.update(self.__pod_to_env(pod.spec.containers[0].env))
			if "SERVER_NAME" in env and env["SERVER_NAME"] != "" :
				first_servers.extend(env["SERVER_NAME"].split(" "))
		for ingress in ingresses :
			env.update(self.__rules_to_env(ingress.spec.rules, namespace=ingress.metadata.namespace))
			if ingress.spec.tls :
				for tls_entry in ingress.spec.tls :
					for host in tls_entry.hosts :
						env[host + "_AUTO_LETS_ENCRYPT"] = "yes"
			if "SERVER_NAME" in env and env["SERVER_NAME"] != "" :
				first_servers.extend(env["SERVER_NAME"].split(" "))
		for service in services :
			if service.metadata.annotations != None and "bunkerized-nginx.SERVER_NAME" in service.metadata.annotations :
				env.update(self.__annotations_to_env(service.metadata.annotations))
				first_servers.append(service.metadata.annotations["bunkerized-nginx.SERVER_NAME"])
		first_servers = list(dict.fromkeys(first_servers))
		if len(first_servers) == 0 :
			env["SERVER_NAME"] = ""
		else :
			env["SERVER_NAME"] = " ".join(first_servers)
		return self._fix_env(env)

	def process_events(self, current_env) :
		self.__old_env = current_env
		t_pod = Thread(target=self.__watch_pod)
		t_ingress = Thread(target=self.__watch_ingress)
		t_service = Thread(target=self.__watch_service)
		t_pod.start()
		t_ingress.start()
		t_service.start()
		t_pod.join()
		t_ingress.join()
		t_service.join()

	def __watch_pod(self) :
		w = watch.Watch()
		for event in w.stream(self.__api.list_pod_for_all_namespaces, label_selector="bunkerized-nginx") :
			self.lock.acquire()
			new_env = self.get_env()
			if new_env != self.__old_env :
				try :
					if self.gen_conf(new_env) :
						self.__old_env = new_env.copy()
						log("CONTROLLER", "INFO", "successfully generated new configuration")
						if self.reload() :
							log("controller", "INFO", "successful reload")
						else :
							log("controller", "ERROR", "failed reload")
				except :
					log("controller", "ERROR", "exception while receiving event")
			self.lock.release()

	def __watch_ingress(self) :
		w = watch.Watch()
		for event in w.stream(self.__extensions_api.list_ingress_for_all_namespaces, label_selector="bunkerized-nginx") :
			self.lock.acquire()
			new_env = self.get_env()
			if new_env != self.__old_env :
				try :
					if self.gen_conf(new_env) :
						self.__old_env = new_env.copy()
						log("CONTROLLER", "INFO", "successfully generated new configuration")
						if self.reload() :
							log("controller", "INFO", "successful reload")
						else :
							log("controller", "ERROR", "failed reload")
				except :
					log("controller", "ERROR", "exception while receiving event")
			self.lock.release()

	def __watch_service(self) :
		w = watch.Watch()
		for event in w.stream(self.__api.list_service_for_all_namespaces, label_selector="bunkerized-nginx") :
			self.lock.acquire()
			new_env = self.get_env()
			if new_env != self.__old_env :
				try :
					if self.gen_conf(new_env) :
						self.__old_env = new_env.copy()
						log("CONTROLLER", "INFO", "successfully generated new configuration")
						if self.reload() :
							log("controller", "INFO", "successful reload")
						else :
							log("controller", "ERROR", "failed reload")
				except :
					log("controller", "ERROR", "exception while receiving event")
			self.lock.release()

	def reload(self) :
		return self._reload(self.__get_services(autoconf=True))

	def wait(self) :
		self.lock.acquire()
		try :
			# Wait for at least one bunkerized-nginx pod
			pods = self.__get_pods()
			while len(pods) == 0 :
				time.sleep(1)
				pods = self.__get_pods()

			# Wait for at least one bunkerized-nginx service
			services = self.__get_services(autoconf=True)
			while len(services) == 0 :
				time.sleep(1)
				services = self.__get_services(autoconf=True)

			# Generate first config
			env = self.get_env()
			if not self.gen_conf(env) :
				self.lock.release()
				return False, env

			# Wait for bunkerized-nginx
			self.lock.release()
			return self._config.wait(services), env
		except :
			pass
		self.lock.release()
		return False, {}
