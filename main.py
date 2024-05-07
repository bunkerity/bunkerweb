from flask import Flask, render_template, request
from json import loads

from forms import settings_to_form, compute_form

app = Flask(__name__)

@app.route("/global", methods=['GET', 'POST'])
def global_settings():
	# with open("settings.json") as f:
	# 	settings = loads(f.read())
	with open("limit.json") as f:
		settings = loads(f.read())["settings"]
	form = settings_to_form(settings)(request.form)
	if request.method == "POST":
		form = compute_form(form, request.form, settings)
		if not form.validate():
			print("error validate")
		for field in form:
			print(f"field {field.id} = {field.data}")
	print(form.errors)
	return render_template("global.html", form=form)

app.debug = True
app.run(host='0.0.0.0')