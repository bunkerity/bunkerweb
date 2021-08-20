#!/usr/bin/python3

import json

with open("settings.json") as f :
	data = json.loads(f.read())

with open("docs/environment_variables.md") as f :
	docs = f.read()

output = ""
for cat in data :
	for param in data[cat]["params"] :
		if param["type"] == "multiple" :
			params = param["params"]
		else :
			params = [param]
		for true_param in params :
			if not true_param["env"] in docs :
				print("Missing variable in category " + cat + " : " + true_param["env"] + "=" + true_param["default"])
