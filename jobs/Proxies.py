from Job import Job

class Proxies(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "proxies"
		data = ["https://iplists.firehol.org/files/firehol_proxies.netset"]
		filename = "proxies.list"
		type = "line"
		regex = r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, regex=regex, copy_cache=copy_cache)
