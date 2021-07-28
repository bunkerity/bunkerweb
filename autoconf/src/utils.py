#!/usr/bin/python3

import datetime

def log(event) :
	print("[" + str(datetime.datetime.now().replace(microsecond=0)) + "] " + event, flush=True)

def replace_in_file(file, old_str, new_str) :
	with open(file) as f :
		data = f.read()
	data = data[::-1].replace(old_str[::-1], new_str[::-1], 1)[::-1]
	with open(file, "w") as f :
		f.write(data)

def install_cron(service, vars, crons) :
	for var in vars :
		if var in crons :
			with open("/etc/crontabs/root", "a+") as f :
				f.write(vars[var] + " /opt/cron/" + crons[var] + ".py " + service["Actor"]["ID"])

def uninstall_cron(service, vars, crons) :
	for var in vars :
		if var in crons :
			replace_in_file("/etc/crontabs/root", vars[var] + " /opt/cron/" + crons[var] + ".py " + service["Actor"]["ID"] + "\n", "")
