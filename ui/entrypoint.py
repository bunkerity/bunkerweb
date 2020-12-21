#!/usr/bin/python3

from flask import Flask, render_template, current_app

import wrappers, utils
import os

app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")
ABSOLUTE_URI = ""
if "ABSOLUTE_URI" in os.environ :
	ABSOLUTE_URI = os.environ["ABSOLUTE_URI"]
app.config["ABSOLUTE_URI"] = ABSOLUTE_URI
app.jinja_env.globals.update(env_to_summary_class=utils.env_to_summary_class)

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

@app.route('/instances')
def instances():
	check, instances = wrappers.get_instances()
	if not check :
		return render_template("error.html", title="Error", error=instances)
	return render_template("instances.html", title="Instances", instances=instances)

@app.route('/services')
def services():
	check, services = wrappers.get_services()
	print(services, flush=True)
	if not check :
		return render_template("error.html", title="Error", error=services)
	return render_template("services.html", title="Services", services=services)
