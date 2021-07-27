from kubernetes import client, config, watch
from threading import Thread, Lock

class IngressController :

	def __init__(self) :
		config.load_kube_config()
		self.__api = client.CoreV1Api()
		self.__extensions_api = client.ExtensionsV1beta1Api()
		self.__lock = Lock()
		self.__last_conf = {}

	def __annotations_to_env(self, annotations, service=False) :
		env = {}
		prefix = ""
		if service :
			if not "bunkerized-nginx.SERVER_NAME" in annotations :
				raise Exception("Missing bunkerized-nginx.SERVER_NAME annotation in Service.")
			prefix = annotations["bunkerized-nginx.SERVER_NAME"].split(" ")[0] + "_"
		for annotation in annotations :
			if annotation.startswith("bunkerized-nginx.") and annotation.split(".")[1] != "" and annotation.split(".")[1] != "AUTOCONF" :
				env[prefix + annotation.split(".")[1]] = annotations[annotation]
		return env

	def gen_conf(self) :
		ingresses = self.get_ingresses()
		services = self.get_services()
		env = {}
		for ingress in ingresses :
			if ingress.metadata.annotations == None :
				continue
			if "bunkerized-nginx.AUTOCONF" in ingress.metadata.annotations :
				env.update(self.__annotations_to_env(ingress.metadata.annotations))
		for service in services :
			if service.metadata.annotations == None :
				continue
			if "bunkerized-nginx.AUTOCONF" in service.metadata.annotations :
				env.update(self.__annotations_to_env(service.metadata.annotations, service=True))
		if self.__last_conf != env :
			self.__last_conf = env
			print("*** NEW CONF ***")
			for k, v in env.items() :
				print(k + " = " + v)

	def get_ingresses(self) :
		return self.__extensions_api.list_ingress_for_all_namespaces(watch=False).items

	def get_services(self) :
		return self.__api.list_service_for_all_namespaces(watch=False).items

	def watch_ingress(self) :
		w = watch.Watch()
		for event in w.stream(self.__extensions_api.list_ingress_for_all_namespaces) :
			self.__lock.acquire()
#			print("*** NEW INGRESS EVENT ***", flush=True)
#			for k, v in event.items() :
#				print(k + " :", flush=True)
#				print(v, flush=True)
			self.gen_conf()
			self.__lock.release()

	def watch_service(self) :
		w = watch.Watch()
		for event in w.stream(self.__api.list_service_for_all_namespaces) :
			self.__lock.acquire()
			self.gen_conf()
#			print("*** NEW SERVICE EVENT ***", flush=True)
#			for k, v in event.items() :
#				print(k + " :", flush=True)
#				print(v, flush=True)
			self.__lock.release()

ic = IngressController()

print("*** INGRESSES ***")
print(ic.get_ingresses())

print("*** SERVICES ***")
print(ic.get_services())

print("*** LISTENING FOR EVENTS ***")
t_ingress = Thread(target=ic.watch_service)
t_service = Thread(target=ic.watch_service)
t_ingress.start()
t_service.start()
t_ingress.join()
t_service.join()
