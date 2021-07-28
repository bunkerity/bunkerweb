import abc, requests, redis, os, datetime, traceback, re, shutil, enum, filecmp, subprocess

from logger import log

class JobRet(enum.Enum) :
	KO		= 0
	OK_RELOAD	= 1
	OK_NO_RELOAD	= 2

class ReloadRet(enum.Enum) :
	KO		= 0
	OK		= 1
	NO		= 2

class JobManagement() :

	def __init__(self) :
		self.__local_nginx = False
		if os.path.isfile("/usr/sbin/nginx") and os.path.isfile("/tmp/nginx.pid") :
			self.__local_nginx = True
		self.__autoconf_socket = None
		if os.path.exists("/tmp/autoconf.sock") and stat.S_ISSOCK(os.stat("/tmp/autoconf.sock")) :
			self.__autoconf_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			self.__autoconf_socket.connect()

	def __autoconf_order(self, order) :
		self.__autoconf_socket.sendall(order)
		data = self.__autoconf_socket.recv(512)
		if not data or data != b"ok" :
			return False
		return True

	def lock(self) :
		if self.__autoconf_socket != None :
			return self.__autoconf_order(b"lock")
		# TODO : local lock
		return True

	def unlock(self) :
		if self.__autoconf_socket != None :
			return self.__autoconf_order(b"unlock")
		# TODO : local unlock
		return True

	def reload(self) :
		if self.__autoconf_socket != None :
			if self.__autoconf_order(b"reload") :
				return ReloadRet.OK
			return ReloadRet.KO
		elif self.__local_nginx :
			proc = subprocess.run(["/usr/sbin/nginx", "-s", "reload"], capture_output=True)
			if proc.returncode != 0 :
				log("reload", "ERROR", "can't reload nginx (status code = " + str(proc.returncode) + ")")
				if len(proc.stdout.decode("ascii")) > 1 :
					log("reload", "ERROR", proc.stdout.decode("ascii"))
				if len(proc.stderr.decode("ascii")) > 1 :
					log("reload", "ERROR", proc.stderr.decode("ascii"))
				return ReloadRet.KO
			return ReloadRet.OK
		return ReloadRet.NO

class Job(abc.ABC) :

	def __init__(self, name, data, filename=None, redis_host=None, type="line", regex=r"^.+$", copy_cache=False) :
		self._name = name
		self._data = data
		self._filename = filename
		self._redis = None
		if redis_host != None :
			self._redis = redis.Redis(host=redis_host, port=6379, db=0)
			try :
				self._redis.echo("test")
			except :
				log(self._name, "ERROR", "can't connect to redis host " + redis_host)
		self._type = type
		self._regex = regex
		self._copy_cache = copy_cache

	def run(self) :
		ret = JobRet.KO
		try :
			if self._type == "line" or self._type == "file" :
				if self._copy_cache :
					ret = self.__from_cache()
					if ret != JobRet.KO :
						return ret
				ret = self.__external()
				self.__to_cache()
			elif self._type == "exec" :
				return self.__exec()
		except Exception as e :
			log(self._name, "ERROR", "exception while running job : " + traceback.format_exc())
			return JobRet.KO
		return ret

	def __external(self) :
		if self._redis == None :
			if os.path.isfile("/tmp/" + self._filename) :
				os.remove("/tmp/" + self._filename)
			file = open("/tmp/" + self._filename, "ab")

		elif self._redis != None :
			pipe = self._redis.pipeline()

		count = 0
		for url in self._data :
			data = self.__download_data(url)
			for chunk in data :
				if self._type == "line" :
					if not re.match(self._regex, chunk.decode("utf-8")) :
						continue
					chunks = self._edit(chunk)
				if self._redis == None :
					if self._type == "line" :
						for chunk in chunks :
							file.write(chunk + b"\n")
					else :
						file.write(chunk)
				else :
					if self._type == "line" :
						for chunk in chunks :
							pipe.set(self._name + "_" + chunk, "1")
					else :
						pipe.set(self._name + "_" + chunk, "1")
				count += 1

		if self._redis == None :
			file.close()
			if count > 0 :
				shutil.copyfile("/tmp/" + self._filename, "/etc/nginx/" + self._filename)
			os.remove("/tmp/" + self._filename)
			return JobRet.OK_RELOAD

		elif self._redis != None and count > 0 :
			self._redis.delete(self._redis.keys(self._name + "_*"))
			pipe.execute()
			return JobRet.OK_RELOAD

		return JobRet.KO

	def __download_data(self, url) :
		r = requests.get(url, stream=True)
		if not r or r.status_code != 200 :
			raise Exception("can't download data at " + url)
		if self._type == "line" :
			return r.iter_lines()
		return r.iter_content(chunk_size=8192)

	def __exec(self) :
		proc = subprocess.run(self._data, capture_output=True)
		stdout = proc.stdout.decode("ascii")
		stderr = proc.stderr.decode("ascii")
		if proc.returncode != 0 :
			if len(stdout) > 1 :
				log(self._name, "ERROR", "stdout = " + stdout)
			if len(stderr) > 1 :
				log(self._name, "ERROR", "stderr = " + stderr)
			self._callback(False)
			return JobRet.KO
		# TODO : check if reload is needed ?
		self._callback(True)
		return JobRet.OK_RELOAD

	def _edit(self, chunk) :
		return [chunk]

	def _callback(self, success) :
		pass

	def __from_cache(self) :
		if not os.path.isfile("/opt/bunkerized-nginx/cache/" + self._filename) :
			return JobRet.KO

		if self._redis == None or self._type == "file" :
			if not os.path.isfile("/etc/nginx/" + self._filename) or not filecmp.cmp("/opt/bunkerized-nginx/cache/" + self._filename, "/etc/nginx/" + self._filename, shallow=False) :
				shutil.copyfile("/opt/bunkerized-nginx/cache/" + self._filename, "/etc/nginx/" + self._filename)
				return JobRet.OK_RELOAD
			return JobRet.OK_NO_RELOAD

		if self._redis != None and self._type == "line" :
			self._redis.delete(self._redis.keys(self._name + "_*"))
			with open("/opt/bunkerized-nginx/cache/" + self._filename) as f :
				pipe = self._redis.pipeline()
				while True :
					line = f.readline()
					if not line :
						break
					line = line.strip()
					pipe.set(self._name + "_" + line, "1")
				pipe.execute()
				return JobRet.OK_NO_RELOAD

		return JobRet.KO

	def __to_cache(self) :
		if self._redis == None or self._type == "file" :
			shutil.copyfile("/etc/nginx/" + self._filename, "/opt/bunkerized-nginx/cache/" + self._filename)
		elif self._redis != None and self._type == "line" :
			if os.path.isfile("/opt/bunkerized-nginx/cache/" + self._filename) :
				os.remove("/opt/bunkerized-nginx/cache/" + self._filename)
			with open("/opt/bunkerized-nginx/cache/" + self._filename, "a") as f :
				for key in self._redis.keys(self._name + "_*") :
					f.write(self._redis.get(key) + "\n")
