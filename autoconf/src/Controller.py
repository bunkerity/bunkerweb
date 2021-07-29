from abc import ABC, abstractmethod
from enum import Enum

from Config import Config

class Type(Enum) :
	DOCKER = 1
	SWARM = 2
	KUBERNETES = 3

class Controller(ABC) :

	def __init__(self, type, api_uri=None, lock=None) :
		self.__config = Config(type, api_uri)
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
		return self.__config.gen(env)

	@abstractmethod
	def process_events(self, current_env) :
		pass

	@abstractmethod
	def reload(self) :
		pass

	def _reload(self, instances) :
		return self.__config.reload(instances)
