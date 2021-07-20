from Job import Job

class Abusers(Job) :

	def __init__(self, redis_host=None) :
		name = "abusers"
		data = ["https://iplists.firehol.org/files/firehol_abusers_30d.netset"]
		filename = "abusers.list"
		type = "line"
		regex = r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/?[0-9]*$"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, regex=regex)
