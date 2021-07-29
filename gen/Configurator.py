import json, re

class Configurator :

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
			check, reason = self.__check_var(var, value)
			if check :
				self.__variables[var] = value
			else :
				print("ignoring " + var + "=" + value + " (" + reason + ")", file=sys.stderr)

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
		elif re.search("\\_\d+$", var) and ("_".join(var.split("_")[:-1]) in self.__settings or "_".join(var.split("_")[:-1][1:]) in self.__settings) :
			if "_".join(var.split("_")[:-1]) in self.__settings :
				real_var = "_".join(var.split("_")[:-1])
			else :
				real_var = "_".join(var.split("_")[:-1][1:])
		if real_var == "" :
			return False, "doesn't exist"
		elif not re.search(self.__settings[real_var]["regex"], value) :
			return False, "doesn't match regex : " + self.__settings[real_var]["regex"]
		elif multisite_only and self.__settings[real_var]["context"] != "multisite" :
			return False, "not at multisite context"
		return True, ""
