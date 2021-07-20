from Job import Job

class ExitNodes(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "exit-nodes"
		data = ["https://iplists.firehol.org/files/tor_exits.ipset"]
		filename = "tor-exit-nodes.list"
		type = "line"
		regex = r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, regex=regex, copy_cache=copy_cache)
