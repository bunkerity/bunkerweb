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

def form_service_gen(form, server, id, label, type, value) :
	if form == "edit" :
		new_id = "form-edit-" + server + "-" + id
	elif form == "new" :
		new_id = "form-new-" + id
	if type == "text" :
		input = '<input type="%s" class="form-control" id="%s" value="%s">' % (type, new_id, value)
		pt = ""
	elif type == "checkbox" :
		checked = ""
		if value == "yes" :
			checked = "checked"
		input = '<div class="form-check form-switch"><input type="%s" class="form-check-input" id="%s" %s></div>' % (type, new_id, checked)
		pt = "pt-0"
	return '<div class="row mb-3"><label for="%s" class="col-4 col-form-label %s">%s</label><div class="col-8">%s</div></div>' % (new_id, pt, label, input)
