from Job import Job

class Referrers(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "referrers"
		data = ["https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list"]
		filename = "referrers.list"
		type = "line"
		regex = r"^.+$"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, regex=regex, copy_cache=copy_cache)
