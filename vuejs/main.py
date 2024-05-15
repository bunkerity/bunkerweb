from flask import Flask, render_template
from flask import Blueprint
from flask import redirect, url_for

app = Flask(__name__)

# I want to setup templates and static files
app = Flask(__name__, template_folder="templates", static_folder="static")

templates = Blueprint("static", __name__, template_folder="static/templates")
assets = Blueprint("assets", __name__, static_folder="static/assets")
images = Blueprint("images", __name__, static_folder="static/images")
style = Blueprint("style", __name__, static_folder="static/css")
js = Blueprint("js", __name__, static_folder="static/js")
app.register_blueprint(templates)
app.register_blueprint(assets)
app.register_blueprint(images)
app.register_blueprint(style)
app.register_blueprint(js)

@app.route("/", methods=['GET', 'POST'])
def render_index():
	# redirect to test
	return redirect(url_for('render_test'))

@app.route("/test", methods=['GET', 'POST'])
def render_test():
	return render_template("test.html", flask_data="Title from Flask !")

@app.route("/test2", methods=['GET', 'POST'])
def render_test2():
	return render_template("test.html")


app.debug = True
app.run(host='0.0.0.0')