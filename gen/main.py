#!/usr/bin/python3

from Settings import Settings

if __name__ == "__main__" :

	my_settings = Settings()
	my_settings.load_settings("../settings.json")
	variables = {}
	variables["MULTISITE"] = "yes"
	variables["BLOCK_PROXIES"] = "no"
	variables["omg"] = "lol"
	my_settings.load_variables(variables)
