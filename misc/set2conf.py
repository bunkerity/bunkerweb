#!/usr/bin/python3

import json

with open("settings.json") as f :
	data = json.loads(f.read())

output = ""
for cat in data :
	output += "# " + cat + "\n"
	for param in data[cat]["params"] :
		if param["type"] == "multiple" :
			params = param["params"]
		else :
			params = [param]
		for true_param in params :
			output += "#" + true_param["env"] + "=" + true_param["default"] + "\n"
	output += "\n"
print(output)
