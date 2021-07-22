import abc, requests, redis, os, datetime, traceback, re, shutil, enum, filecmp

class JobRet(enum.Enum) :
	KO		= 0
	OK_RELOAD	= 1
	OK_NO_RELOAD	= 2

class Job(abc.ABC) :

	def __init__(self, name, data, filename=None, redis_host=None, type="line", regex=r"^.+$", copy_cache=False) :
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
		ret = JobRet.KO
		try :
			if self.__type == "line" or self.__type == "file" :
				if self.__copy_cache :
					ret = self.__from_cache()
					if ret != JobRet.KO :
						return ret
				ret = self.__external()
				self.__to_cache()
			elif self.__type == "exec" :
				return self.__exec()
		except Exception as e :
			self.__log("exception while running job : " + traceback.format_exc())
			return JobRet.KO
		return ret

	def __external(self) :
		if self.__redis == None :
			if os.path.isfile("/tmp/" + self.__filename) :
				os.remove("/tmp/" + self.__filename)
			file = open("/tmp/" + self.__filename, "ab")

		elif self.__redis != None :
			pipe = self.__redis.pipeline()

		count = 0
		for url in self.__data :
			data = self.__download_data(url)
			for chunk in data :
				if self.__type == "line" :
					if not re.match(self.__regex, chunk.decode("utf-8")) :
						continue
					chunks = self.__edit(chunk)
				if self.__redis == None :
					if self.__type == "line" :
						chunk += b"\n"
					file.write(chunk)
				else :
					if self.__type == "line" :
						for chunk in chunks :
							pipe.set(self.__name + "_" + chunk, "1")
					else :
						pipe.set(self.__name + "_" + chunk, "1")
				count += 1

		if self.__redis == None :
			file.close()
			if count > 0 :
				shutil.copyfile("/tmp/" + self.__filename, "/etc/nginx/" + self.__filename)
			os.remove("/tmp/" + self.__filename)
			return JobRet.OK_RELOAD

		elif self.__redis != None and count > 0 :
			self.__redis.delete(self.__redis.keys(self.__name + "_*"))
			pipe.execute()
			return JobRet.OK_RELOAD

		return JobRet.KO

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
			return JobRet.KO
		# TODO : check if reload is needed ?
		return JobRet.OK_RELOAD

	def __edit(self, chunk) :
		return [chunk]

	def __from_cache(self) :
		if not os.path.isfile("/opt/bunkerized-nginx/cache/" + self.__filename) :
			return JobRet.KO

		if self.__redis == None or self.__type == "file" :
			if not os.path.isfile("/etc/nginx/" + self.__filename) or not filecmp.cmp("/opt/bunkerized-nginx/cache/" + self.__filename, "/etc/nginx/" + self.__filename, shallow=False) :
				shutil.copyfile("/opt/bunkerized-nginx/cache/" + self.__filename, "/etc/nginx/" + self.__filename)
				return JobRet.OK_RELOAD
			return JobRet.OK_NO_RELOAD

		if self.__redis != None and self.__type == "line" :
			self.__redis.delete(self.__redis.keys(self.__name + "_*"))
			with open("/opt/bunkerized-nginx/cache/" + self.__filename) as f :
				pipe = self.__redis.pipeline()
				while True :
					line = f.readline()
					if not line :
						break
					line = line.strip()
					pipe.set(self.__name + "_" + line, "1")
				pipe.execute()
				return JobRet.OK_NO_RELOAD

		return JobRet.KO

	def __to_cache(self) :
		if self.__redis == None or self.__type == "file" :
			shutil.copyfile("/etc/nginx/" + self.__filename, "/opt/bunkerized-nginx/cache/" + self.__filename)
		elif self.__redis != None and self.__type == "line" :
			if os.path.isfile("/opt/bunkerized-nginx/cache/" + self.__filename) :
				os.remove("/opt/bunkerized-nginx/cache/" + self.__filename)
			with open("/opt/bunkerized-nginx/cache/" + self.__filename, "a") as f :
				for key in self.__redis.keys(self.__name + "_*") :
					f.write(self.__redis.get(key) + "\n")
