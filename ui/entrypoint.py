#!/usr/bin/python3

from flask import Flask, render_template

app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")

@app.route('/')
def home():
	return render_template("home.html", title="Home")
