import abc, requests, redis, os, datetime, traceback

class Job(abc.ABC) :

	def __init__(self, name, data, filename, redis_host=None, type="line", regex=r"^.+$", copy_cache=False) :
		self.__name = name
		self.__data = data
		self.__filename = filename
		self.__redis = None
		if redis_host != None :
			self.__redis = redis.Redis(host=redis_host, port=6379, db=0)
			try :
				self.__redis.echo("test")
			except :
				self.__log("can't connect to redis host " + redis_host)
		self.__type = type
		self.__regex = regex
		self.__copy_cache = copy_cache

	def __log(self, data) :
		when = datetime.datetime.today().strftime("[%Y-%m-%d %H:%M:%S]")
		what = self.__name + " - " + data + "\n"
		with open("/var/log/nginx/jobs.log", "a") as f :
			f.write(when + " " + what)

	def run(self) :
		try :
			if self.__type == "line" or self.__type == "file" :
				if self.__copy_cache and self.__from_cache() :
					return True
				self.__external()
				self.__to_cache()
			elif self.__type == "exec" :
				self.__exec()
		except Exception as e :
			self.__log("exception while running job : " + traceback.format_exc())
			return False
		return True

	def __external(self) :
		if self.__redis == None :
			if os.path.isfile("/tmp/" + self.__filename) :
				os.remove("/tmp/" + self.__filename)
			file = open("/tmp/" + self.__filename, "a")

		elif self.__redis != None :
			pipe = self.__redis.pipeline()

		count = 0
		for url in self.__data :
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
			raise Exception("can't download data at " + url)
		if self.__type == "line" :
			return r.iter_lines()
		return r.iter_content(chunk_size=8192)

	def __exec(self) :
		proc = subprocess.run(self.__data, capture_output=True)
		stdout = proc.stdout.decode("ascii")
		stderr = proc.stderr.decode("err")
		if len(stdout) > 1 :
			self.__log("stdout = " + stdout)
		if len(stderr) > 1 :
			self.__log("stderr = " + stderr)
		if proc.returncode != 0 :
			raise Exception("error code " + str(proc.returncode))

	def __from_cache(self) :
		if not os.path.isfile("/opt/bunkerized-nginx/cache/" + self.__filename) :
			return False
		if self.__redis == None or self.__type == "file" :
			shutil.copyfile("/opt/bunkerized-nginx/cache/" + self.__filename, "/etc/nginx/" + self.__filename)
		elif self.__redis != None and self.__type == "line" :
			self.__redis.del(self.__redis.keys(self.__name + "_*"))
			with open("/opt/bunkerized-nginx/cache/" + self.__filename) as f :
				pipe = self.__redis.pipeline()
				while True :
					line = f.readline()
					if not line :
						break
					line = line.strip()
					pipe.set(self.__name + "_" + line, "1")
				pipe.execute()
		return True

	def __to_cache(self) :
		if self.__redis == None or self.__type == "file" :
			shutil.copyfile("/etc/nginx/" + self.__filename, "/opt/bunkerized-nginx/cache/" + self.__filename)
		elif self.__redis != None and self.__type == "line" :
			if os.path.isfile("/opt/bunkerized-nginx/cache/" + self.__filename) :
				os.remove("/opt/bunkerized-nginx/cache/" + self.__filename)
			with open("/opt/bunkerized-nginx/cache/" + self.__filename, "a") as f :
				for key in self.__redis.keys(self.__name + "_*") :
					f.write(self.__redis.get(key) + "\n")
