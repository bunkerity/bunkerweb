#!/usr/bin/python3

from flask import Flask, render_template, current_app, request

from Docker import Docker
import Docker, wrappers, utils
import os, json, re

app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")
ABSOLUTE_URI = ""
if "ABSOLUTE_URI" in os.environ :
	ABSOLUTE_URI = os.environ["ABSOLUTE_URI"]
app.config["ABSOLUTE_URI"] = ABSOLUTE_URI
with open("/opt/settings.json", "r") as f :
	app.config["CONFIG"] = json.loads(f.read())
app.config["DOCKER"] = Docker()
app.jinja_env.globals.update(env_to_summary_class=utils.env_to_summary_class)
app.jinja_env.globals.update(form_service_gen=utils.form_service_gen)
app.jinja_env.globals.update(form_service_gen_multiple=utils.form_service_gen_multiple)
app.jinja_env.globals.update(form_service_gen_multiple_values=utils.form_service_gen_multiple_values)

@app.route('/')
@app.route('/home')
def home() :
	try :
		instances_number = len(app.config["DOCKER"].get_instances())
		services_number = 0 # TODO
		return render_template("home.html", title="Home", instances_number=instances_number, services_number=services_number)
	except Exception as e :
		return render_template("error.html", title="Error", error=e)

@app.route('/instances', methods=["GET", "POST"])
def instances() :
	try :
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
			if request.form["operation"] == "reload" :
				app.config["DOCKER"].reload(request_form["INSTANCE_ID"])
			elif request.form["operation"] == "start" :
				app.config["DOCKER"].start(request_form["INSTANCE_ID"])
			elif request.form["operation"] == "stop" :
				app.config["DOCKER"].stop(request_form["INSTANCE_ID"])
			elif request.form["operation"] == "restart" :
				app.config["DOCKER"].restart(request_form["INSTANCE_ID"])
			elif request.form["operation"] == "delete" :
				app.config["DOCKER"].remove(request_form["INSTANCE_ID"])

		# Display instances
		instances = app.config["DOCKER"].get_instances()
		return render_template("instances.html", title="Instances", instances=instances, operation="todo")

	except Exception as e :
		return render_template("error.html", title="Error", error=e)


@app.route('/services', methods=["GET", "POST"])
def services():

	# Get the client
	check, client = wrappers.get_client()
	if not check :
		return render_template("error.html", title="Error", error=client)

	# Manage services
	operation = ""
	if request.method == "POST" :

		# Check operation
		if not "operation" in request.form or not request.form["operation"] in ["new", "edit", "delete"] :
			return render_template("error.html", title="Error", error="Missing operation parameter on /services.")

		# Check that all fields are present and they match the corresponding regex
		env = {}
		env["MULTISITE"] = "yes"
		if request.form["operation"] in ["new", "edit"] :
			for category in current_app.config["CONFIG"] :
				for param in current_app.config["CONFIG"][category]["params"] :
					if param["type"] == "multiple" :
						for param_user in request.form :
							if param_user.startswith(param["params"][0]["env"]) :
								suffix = param_user.replace(param["params"][0]["env"], "")
								for param_multiple in param["params"] :
									if not param_multiple["env"] + suffix in request.form :
										return render_template("error.html", title="Error", error="Missing " + param["env"] + " parameter.")
									if not re.search(param_multiple["regex"], request.form[param_multiple["env"] + suffix]) :
										return render_template("error.html", title="Error", error="Parameter " + param["env"] + " doesn't match regex.")
									env[param_multiple["env"] + suffix] = request.form[param_multiple["env"] + suffix]
					else :
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
		check, operation = wrappers.operation_service(client, request.form, env)
		if not check :
			render_template("error.html", title="Error", error=operation)

	# Display services
	check, services = wrappers.get_services()
	if not check :
		return render_template("error.html", title="Error", error=services)
	return render_template("services.html", title="Services", services=services, operation=operation)
