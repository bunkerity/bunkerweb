from kubernetes import client, config, watch
from threading import Thread, Lock

import Controller

from logger import log

class IngressController(Controller.Controller) :

	def __init__(self, api_uri) :
		super().__init__(Controller.Type.KUBERNETES, api_uri=api_uri, lock=Lock())
		config.load_incluster_config()
		self.__api = client.CoreV1Api()
		self.__extensions_api = client.ExtensionsV1beta1Api()
		self.__old_env = {}

	def __get_ingresses(self) :
		return self.__extensions_api.list_ingress_for_all_namespaces(watch=False).items

	def __get_services(self) :
		return self.__api.list_service_for_all_namespaces(watch=False).items

	def __annotations_to_env(self, annotations, service=False) :
		env = {}
		prefix = ""
		if service :
			if not "bunkerized-nginx.SERVER_NAME" in annotations :
				raise Exception("Missing bunkerized-nginx.SERVER_NAME annotation in Service.")
			prefix = annotations["bunkerized-nginx.SERVER_NAME"].split(" ")[0] + "_"
		for annotation in annotations :
			if annotation.startswith("bunkerized-nginx.") and annotation.replace("bunkerized-nginx.", "", 1) != "" and annotation.replace("bunkerized-nginx.", "", 1) != "AUTOCONF" :
				env[prefix + annotation.replace("bunkerized-nginx.", "", 1)] = annotations[annotation]
		return env

	def __rules_to_env(self, rules) :
		env = {}
		for rule in rules :
			prefix = ""
			if "host" in rule :
				prefix = rule["host"] + "_"
			if not "http" in rule or not "paths" in rule["http"] :
				continue
			for path in rule["http"]["paths"] :
				env[prefix + "USE_REVERSE_PROXY"] = "yes"
				env[prefix + "REVERSE_PROXY_URL"] = path["path"]
				env[prefix + "REVERSE_PROXY_HOST"] = "http://" + path["backend"]["serviceName"] + ":" + str(path["backend"]["servicePort"])
		return env

	def get_env(self) :
		ingresses = self.__get_ingresses()
		services = self.__get_services()
		env = {}
		for ingress in ingresses :
			if ingress.metadata.annotations == None :
				continue
			if "bunkerized-nginx.AUTOCONF" in ingress.metadata.annotations :
				env.update(self.__annotations_to_env(ingress.metadata.annotations))
				env.update(self.__rules_to_env(ingress.spec.rules))
		for service in services :
			if service.metadata.annotations == None :
				continue
			if "bunkerized-nginx.AUTOCONF" in service.metadata.annotations :
				env.update(self.__annotations_to_env(service.metadata.annotations, service=True))
		return self._fix_env(env)

	def process_events(self, current_env) :
		self.__old_env = current_env
		t_ingress = Thread(target=self.__watch_ingress)
		t_service = Thread(target=self.__watch_service)
		t_ingress.start()
		t_service.start()
		t_ingress.join()
		t_service.join()

	def __watch_ingress(self) :
		w = watch.Watch()
		for event in w.stream(self.__extensions_api.list_ingress_for_all_namespaces) :
			new_env = self.get_env()
			if new_env != self.__old_env() :
				if self.gen_conf(new_env, lock=False) :
					self.__old_env = new_env.copy()
					log("CONTROLLER", "INFO", "successfully generated new configuration")

	def __watch_service(self) :
		w = watch.Watch()
		for event in w.stream(self.__api.list_service_for_all_namespaces) :
			new_env = self.get_env()
			if new_env != self.__old_env() :
				if self.gen_conf(new_env, lock=False) :
					self.__old_env = new_env.copy()
					log("CONTROLLER", "INFO", "successfully generated new configuration")

	def reload(self) :
		return self._reload(self.__get_ingresses())

	def wait(self) :
		return self._config.wait(self.__get_ingresses())
