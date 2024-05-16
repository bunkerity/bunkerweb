from flask import Flask, render_template

app = Flask(__name__)

# I want to setup templates and static files
app = Flask(__name__, template_folder="templates", static_url_path="", static_folder="static")

@app.route("/", methods=['GET', 'POST'])
def render_index():
	# redirect to test
	return render_template("home.html", flask_data="Title from Flask !")


app.debug = True
app.run(host='0.0.0.0')