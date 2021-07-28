from abc import ABC, abstractmethod
from Config import Config

class ControllerType(Enum) :
	DOCKER = 1
	SWARM = 2
	KUBERNETES = 3

class Controller(ABC) :

	def __init__(self, type) :
		self.__config = Config.from_controller_type(type)

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
	def process_events(self) :
		pass
