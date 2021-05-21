#!/usr/bin/python3

from Settings import Settings
from Templates import Templates

if __name__ == "__main__" :

	my_settings = Settings()
	my_settings.load_settings("../settings.json")
	variables = {}
	variables["MULTISITE"] = "yes"
	variables["BLOCK_PROXIES"] = "no"
	variables["omg"] = "lol"
	variables["www.toto.com_BLOCK_PROXIES"] = "yes"
	my_settings.load_variables(variables)
	print(my_settings.get_config())
	my_templates = Templates(my_settings.get_config(), "/tmp/input")
	my_templates.render_global("/tmp/output")
