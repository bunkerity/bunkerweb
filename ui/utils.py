#!/usr/bin/python3

import datetime, re, json, os

def get_variables() :
	vars = {}
	vars["DOCKER_HOST"]		= "unix:///var/run/docker.sock"
	vars["API_URI"]			= ""
	vars["ABSOLUTE_URI"]	= ""
	for k in vars :
		if k in os.environ :
			vars[k] = os.environ[k]
	return vars

def log(event) :
	with open("/var/log/nginx/ui.log", "a") as f :
		f.write("[" + str(datetime.datetime.now().replace(microsecond=0)) + "] " + event + "\n")

def env_to_summary_class(var, value) :
	if type(var) is list and type(value) is list :
		for i in range(0, len(var)) :
			if not isinstance(var[i], str) :
				continue
			if re.search(value[i], var[i]) :
				return "check text-success"
		return "times text-danger"
	if not isinstance(var, str) :
		return "times text-danger"
	if re.search(value, var) :
		return "check text-success"
	return "times text-danger"

def form_service_gen(id, label, type, value, name) :
	pt = ""
	if type == "text" :
		input = '<input type="%s" class="form-control" id="%s" value="%s" name="%s">' % (type, id, value, name)
	elif type == "checkbox" :
		checked = ""
		if value == "yes" :
			checked = "checked"
		input = '<div class="form-check form-switch"><input type="%s" class="form-check-input" id="%s" name="%s" %s></div>' % (type, id, name, checked)
		pt = "pt-0"
	return '<label for="%s" class="col-4 col-form-label %s">%s</label><div class="col-8">%s</div>' % (id, pt, label, input)

def form_service_gen_multiple(id, label, params) :
	buttons = '<button class="btn btn-success" type="button" onClick="addMultiple(\'%s\', \'%s\');"><i class="fas fa-plus"></i> Add</button> <button class="btn btn-danger" type="button" onClick="delMultiple(\'%s\', \'%s\')"><i class="fas fa-trash"></i> Del</button>' % (id, json.dumps(params).replace("\"", "&quot;"), id, json.dumps(params).replace("\"", "&quot;"))
	return '<label for="%s" class="col-4 col-form-label mb-3">%s</label><div class="col-8 mb-3" id="%s">%s</div>' % (id + "-btn", label, id + "-btn", buttons)

def form_service_gen_multiple_values(id, params, service) :
	values = []
	for env in service :
		if env.startswith(params[0]["env"]) :
			suffix = env.replace(params[0]["env"], "")
			for param in params :
				value = {}
				value["id"] = param["id"]
				value["env"] = param["env"]
				value["label"] = param["label"]
				value["type"] = param["type"]
				if param["env"] + suffix in service :
					value["default"] = service[param["env"] + suffix]
				else :
					value["default"] = param["default"]
				values.append(value)
	if len(values) > 0 :
		return "addMultiple('%s', '%s'); " % (id, json.dumps(values))
	return ""
