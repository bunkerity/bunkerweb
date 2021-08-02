from Job import Job

class UserAgents(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "user-agents"
		data = ["https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list", "https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt"]
		filename = "user-agents.list"
		type = "line"
		regex = r"^.+$"
		redis_ex = 86400
		super().__init__(name, data, filename, redis_host=redis_host, redis_ex=redis_ex, type=type, regex=regex, copy_cache=copy_cache)

	def _edit(self, chunk) :
		return [chunk.replace(b"\\ ", b" ").replace(b"\\.", b"%.").replace(b"\\\\", b"\\").replace(b"-", b"%-")]
