#!/usr/bin/python3

from flask import Flask, render_template, current_app, request

import wrappers, utils
import os, json, re

app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")
ABSOLUTE_URI = ""
if "ABSOLUTE_URI" in os.environ :
	ABSOLUTE_URI = os.environ["ABSOLUTE_URI"]
app.config["ABSOLUTE_URI"] = ABSOLUTE_URI
with open("/opt/entrypoint/config.json", "r") as f :
	app.config["CONFIG"] = json.loads(f.read())
app.jinja_env.globals.update(env_to_summary_class=utils.env_to_summary_class)
app.jinja_env.globals.update(form_service_gen=utils.form_service_gen)
app.jinja_env.globals.update(form_service_gen_multiple=utils.form_service_gen_multiple)
app.jinja_env.globals.update(form_service_gen_multiple_values=utils.form_service_gen_multiple_values)

@app.route('/')
@app.route('/home')
def home():
	check, instances = wrappers.get_instances()
	if not check :
		return render_template("error.html", title="Error", error=instances)
	check, services = wrappers.get_services()
	if not check :
		return render_template("error.html", title="Error", error=services)
	return render_template("home.html", title="Home", instances_number=len(instances), services_number=len(services))

@app.route('/instances', methods=["GET", "POST"])
def instances():

	# Manage instances
	operation = ""
	if request.method == "POST" :

		# Check operation
		if not "operation" in request.form or not request.form["operation"] in ["reload", "start", "stop", "restart", "delete"] :
			return render_template("error.html", title="Error", error="Missing operation parameter on /instances.")

		# Check that all fields are present
		if not "INSTANCE_ID" in request.form :
			return render_template("error.html", title="Error", error="Missing INSTANCE_ID parameter.")

		# Do the operation
		check, operation = wrappers.operation_instance(request.form)
		if not check :
			return render_template("error.html", title="Error", error=operation)

	# Display instances
	check, instances = wrappers.get_instances()
	if not check :
		return render_template("error.html", title="Error", error=instances)
	return render_template("instances.html", title="Instances", instances=instances, operation=operation)

@app.route('/services', methods=["GET", "POST"])
def services():

	# Manage services
	operation = ""
	if request.method == "POST" :

		print(request.form, flush=True)

		# Check operation
		if not "operation" in request.form or not request.form["operation"] in ["new", "edit", "delete"] :
			return render_template("error.html", title="Error", error="Missing operation parameter on /services.")

		# Check that all fields are present and they match the corresponding regex
		env = {}
		if request.form["operation"] in ["new", "edit"] :
			for category in current_app.config["CONFIG"] :
				for param in current_app.config["CONFIG"][category]["params"] :
					if not param["env"] in request.form :
						return render_template("error.html", title="Error", error="Missing " + param["env"] + " parameter.")
					if not re.search(param["regex"], request.form[param["env"]]) :
						return render_template("error.html", title="Error", error="Parameter " + param["env"] + " doesn't match regex.")
					env[param["env"]] = request.form[param["env"]]
			if request.form["operation"] == "edit" :
				if not "OLD_SERVER_NAME" in request.form :
					return render_template("error.html", title="Error", error="Missing OLD_SERVER_NAME parameter.")
				if not re.search("^([a-z\-0-9]+\.?)+$", request.form["OLD_SERVER_NAME"]) :
					return render_template("error.html", title="Error", error="Parameter OLD_SERVER_NAME doesn't match regex.")
		elif request.form["operation"] == "delete" :
			if not "SERVER_NAME" in request.form :
				return render_template("error.html", title="Error", error="Missing SERVER_NAME parameter.")
			if not re.search("^([a-z\-0-9]+\.?)+$", request.form["SERVER_NAME"]) :
				return render_template("error.html", title="Error", error="Parameter SERVER_NAME doesn't match regex.")

		# Do the operation
		check, operation = wrappers.operation_service(request.form, env)
		if not check :
			render_template("error.html", title="Error", error=operation)

	# Display services
	check, services = wrappers.get_services()
	if not check :
		return render_template("error.html", title="Error", error=services)
	return render_template("services.html", title="Services", services=services, operation=operation)
