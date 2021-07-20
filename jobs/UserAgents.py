from Job import Job

class UserAgents(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "user-agents"
		data = ["https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list", "https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt"]
		filename = "user-agents.list"
		type = "line"
		regex = r"^.+$"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, regex=regex, copy_cache=copy_cache)
