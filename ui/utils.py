#!/usr/bin/python3

import datetime, re

def log(event) :
	print("[" + str(datetime.datetime.now().replace(microsecond=0)) + "] " + event, flush=True)

def replace_in_file(file, old_str, new_str) :
	with open(file) as f :
		data = f.read()
	data = data[::-1].replace(old_str[::-1], new_str[::-1], 1)[::-1]
	with open(file, "w") as f :
		f.write(data)

def env_to_summary_class(var, value) :
	if type(var) is list and type(value) is list :
		for i in range(0, len(var)) :
			if re.search(value[i], var[i]) :
				return "check text-success"
		return "times text-danger"
	if not isinstance(var, str) :
		return "times text-danger"
	if re.search(value, var) :
		return "check text-success"
	return "times text-danger"
