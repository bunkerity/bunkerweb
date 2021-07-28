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

	def gen_conf(self, env) :
		return self.__config.gen(env)

	@abstractmethod
	def process_events(self) :
		pass
