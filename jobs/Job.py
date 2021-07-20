import abc, requests, redis, os

class Job(abc.ABC) :

	def __init__(self, name, urls, filename, redis_host=None, type="line", regex=r"^.*$") :
		self.__name = name
		self.__urls = urls
		self.__filename = filename
		self.__redis = None
		if redis_host != None :
			self.__redis = redis.Redis(host=redis_host, port=6379, db=0)
		self.__type = type
		self.__regex = regex

	def run(self) :
		if self.__redis == None :
			if os.path.isfile("/tmp/" + self.__filename) :
				os.remove("/tmp/" + self.__filename)
			file = open("/tmp/" + self.__filename, "a")

		elif self.__redis != None :
			pipe = self.__redis.pipeline()

		count = 0
		for url in self.__urls :
			data = self.__download_data(url)
			for chunk in data :
				if self.__type == "line" and not re.match(self.__regex, chunk) :
					continue
				count += 1
				if self.__redis == None :
					if self.__type == "line" :
						chunk += b"\n"
					file.write(chunk)
				else :
					pipe.set(self.__name + "_" + chunk, "1")

		if self.__redis == None :
			file.close()
			if count > 0 :
				shutil.copyfile("/tmp/" + self.__filename, "/etc/nginx/" + self.__filename)
			os.remove("/tmp/" + self.__filename)

		elif self.__redis != None and count > 0 :
			self.__redis.del(self.__redis.keys(self.__name + "_*"))
			pipe.execute()

	def __download_data(self, url) :
		r = requests.get(url, stream=True)
		if not r or r.status_code != 200 :
			return False
		if self.__type == "line" :
			return r.iter_lines()
		return r.iter_content(chunk_size=8192)
