from flask import Flask, render_template, request
from json import loads

from forms import settings_to_form

app = Flask(__name__)

@app.route("/global", methods=['GET', 'POST'])
def login():
	with open("settings.json") as f:
		settings = loads(f.read())
	form = settings_to_form(settings)(request.form)
	if request.method == "POST" and form.validate():
		for field in form:
			print(f"field {field.id} = {field.data}")
	print(form.errors)
	return render_template("global.html", form=form)

app.debug = True
app.run(host='0.0.0.0')