from kubernetes import client, config, watch

import asyncio

class IngressController :

	def __init__(self) :
		config.load_kube_config()
		self.__api = client.CoreV1Api()
		self.__extensions_api = client.ExtensionsV1beta1Api()

	def get_ingresses(self) :
		return self.__extensions_api.list_ingress_for_all_namespaces(watch=False)

	def get_services(self) :
		return self.__api.list_service_for_all_namespaces(watch=False)

	async def watch_ingress(self) :
		print("ok ingress", flush=True)
		w = watch.Watch()
		for event in w.stream(self.__extensions_api.list_ingress_for_all_namespaces) :
			print("*** NEW INGRESS EVENT ***", flush=True)
			for k, v in event.items() :
				print(k + " :", flush=True)
				print(v, flush=True)
			await asyncio.sleep(0)

	async def watch_service(self) :
		print("ok service", flush=True)
		w = watch.Watch()
		for event in w.stream(self.__api.list_service_for_all_namespaces) :
			print("*** NEW SERVICE EVENT ***", flush=True)
			for k, v in event.items() :
				print(k + " :", flush=True)
				print(v, flush=True)
			await asyncio.sleep(0)

ic = IngressController()

print("*** INGRESSES ***")
print(ic.get_ingresses())

print("*** SERVICES ***")
print(ic.get_services())

print("*** LISTENING FOR EVENTS ***")

ioloop = asyncio.get_event_loop()
print("ok1")
ioloop.create_task(ic.watch_ingress())
print("ok2")
ioloop.create_task(ic.watch_service())
print("ok3")
ioloop.run_forever()
