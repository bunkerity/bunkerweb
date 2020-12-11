#!/usr/bin/python3

from flask import Flask, render_template

import wrappers

app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")

@app.route('/')
def home():
	check, instances = wrappers.get_instances()
	if not check :
		return render_template("error.html", title="Error", error=instances)
	check, services = wrappers.get_services()
	if not check :
		return render_template("error.html", title="Error", error=services)
	return render_template("home.html", title="Home", instances_number=len(instances), services_number=len(services))

@app.route('/instances')
def home():
	check, instances = wrappers.get_instances()
	if not check :
		return render_template("error.html", title="Error", error=instances)
	return render_template("instances.html", title="Instances", instances=instances)

@app.route('/services')
def home():
	check, services = wrappers.get_services()
	if not check :
		return render_template("error.html", title="Error", error=services)
	return render_template("services.html", title="Services", services=services)
