from Job import Job

import re, ipaddress

class Proxies(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "proxies"
		data = ["https://iplists.firehol.org/files/firehol_proxies.netset"]
		filename = "proxies.list"
		type = "line"
		regex = r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, regex=regex, copy_cache=copy_cache)

	def _edit(self, chunk) :
		if self._redis != None :
			network = chunk.decode("utf-8")
			if re.match(network, r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\/?[0-9]+$") :
				ips = []
				for ip in ipaddress.IPv4Network(network) :
					ips.append(str(ip).encode("utf-8"))
		return [chunk]
