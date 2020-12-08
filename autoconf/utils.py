#!/usr/bin/python3

import datetime

def log(event) :
	print("[" + str(datetime.datetime.now().replace(microsecond=0)) + "] AUTOCONF - " + event, flush=True)

def replace_in_file(file, old_str, new_str) :
	with open(file) as f :
		data = f.read()
	data = data[::-1].replace(old_str[::-1], new_str[::-1], 1)[::-1]
	with open(file, "w") as f :
		f.write(data)
