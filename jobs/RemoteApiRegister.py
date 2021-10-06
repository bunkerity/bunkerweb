from Job import Job

class RemoteApiRegister(Job) :

	def __init__(self, server="", version="") :
		name = "remote-api-register"
		data = [server + "/register"]
		filename = "machine.id"
		type = "json"
		regex = r"^[0-9a-f]{256}$"
		json_data = {"version": version}
		method = "POST"
		super().__init__(name, data, filename, type=type, regex=regex, copy_cache=True, json_data=json_data, method=method)

	def _json(self, data) :
		return data["data"]
