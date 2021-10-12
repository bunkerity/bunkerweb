import traceback
from abc import ABC, abstractmethod
from enum import Enum

from Config import Config

class Type(Enum) :
	DOCKER = 1
	SWARM = 2
	KUBERNETES = 3

class Controller(ABC) :

	def __init__(self, type, api_uri=None, lock=None, http_port="8080") :
		self._config = Config(type, api_uri, http_port=http_port)
		self.lock = lock

	@abstractmethod
	def get_env(self) :
		pass

	def _fix_env(self, env) :
		fixed_env = env.copy()
		blacklist = ["NGINX_VERSION", "NJS_VERSION", "PATH", "PKG_RELEASE"]
		for key in blacklist :
			if key in fixed_env :
				del fixed_env[key]
		return fixed_env

	def gen_conf(self, env) :
		try :
			ret = self._config.gen(env)
		except :
			ret = False
		return ret

	@abstractmethod
	def wait(self) :
		pass

	@abstractmethod
	def process_events(self, current_env) :
		pass

	@abstractmethod
	def reload(self) :
		pass

	def _reload(self, instances) :
		try :
			ret = self._config.reload(instances)
		except :
			ret = False
		return ret

	def _send(self, instances, files="all") :
		try :
			ret = self._config.send(instances, files=files)
		except Exception as e :
			ret = False
		return ret

	def _stop_temp(self, instances) :
		try :
			ret = self._config.stop_temp(instances)
		except Exception as e :
			ret = False
		return ret
