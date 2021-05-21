import json, re

class Settings :

	def __init__(self) :
		self.__settings = {}
		self.__variables = {}

	def load_settings(self, path) :
		with open(path, "r") as f :
			data = json.loads(f.read())
		for cat in data :
			for param in data[cat]["params"] :
				if param["type"] == "multiple" :
					real_params = param["params"]
				else :
					real_params = [param]
				for real_param in real_params :
					self.__settings[real_param["env"]] = real_param
					self.__settings[real_param["env"]]["category"] = cat

	def load_variables(self, vars, multisite_only=False) :
		for var, value in vars.items() :
			if self.__check_var(var, value) :
				self.__variables[var] = value
			else :
				print("Problem with " + var + "=" + value)

	def get_config(self) :
		config = {}
		for setting in self.__settings :
			config[setting] = self.__settings[setting]["default"]
		for variable, value in self.__variables.items() :
			config[variable] = value
		return config

	def __check_var(self, var, value, multisite_only=False) :
		real_var = ""
		if var in self.__settings :
			real_var = var
		elif var[len(var.split("_")[0])+1:] in self.__settings :
			real_var = var[len(var.split("_")[0])+1:]
		return real_var != "" and re.search(self.__settings[real_var]["regex"], value) and (not multisite_only or self.__settings[real_var]["context"] == "multisite")
