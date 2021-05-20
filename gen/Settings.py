import json, re

class Settings :

	def __init__(self) :
		self.settings	= {}
		self.variables	= {}

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
					self.settings[real_param["env"]] = real_param
					self.settings[real_param["env"]]["category"] = cat

	def load_variables(self, vars, multisite_only=False) :
		for var, value in vars.items() :
			if self.__check_var(var, value) :
				self.variables[var] = value
			else :
				print("Problem with " + var + "=" + value)

	def __check_var(self, var, value, multisite_only=False) :
		real_var = ""
		if var in self.settings :
			real_var = var
		elif var[len(var.split("_")[0])+1:] in self.settings :
			real_var = var[len(var.split("_")[0])+1:]
		return real_var != "" and re.search(self.settings[real_var]["regex"], value) and (not multisite_only or self.settings[real_var]["context"] == "multisite")
