from Job import Job

class RemoteApiDatabase(Job) :

	def __init__(self, server="", version="", id="", redis_host=None, copy_cache=False) :
		name = "remote-api-database"
		data = [server + "/db"]
		filename = "remote-api.db"
		type = "json"
		regex = r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$"
		json_data = {"version": version, "id": id}
		super().__init__(name, data, filename, type=type, redis_host=redis_host, redis_ex=redis_ex, regex=regex, copy_cache=copy_cache, json_data=json_data, method=method)

	def _json(self, data) :
		return data["data"]
