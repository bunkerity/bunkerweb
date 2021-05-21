#!/usr/bin/python3

import argparse, os, sys

import utils
from Configurator import Configurator
from Templator import Templator

if __name__ == "__main__" :

	# Parse arguments
	parser = argparse.ArgumentParser(description="bunkerized-nginx config generator v1.0")
	parser.add_argument("--settings", default="/opt/settings.json", type=str, help="path to the files containing the default settings")
	parser.add_argument("--templates", default="/opt/confs", type=str, help="directory containing the templates files")
	parser.add_argument("--output", default="/etc/nginx", type=str, help="where to write the rendered files")
	parser.add_argument("--variables", default="/opt/variables.env", type=str, help="path to the file containing environment variables")
	args = parser.parse_args()

	# Check existences and permissions
	if not os.path.exists(args.settings) :
		print("[!] Missing settings file : " + args.settings)
		sys.exit(1)
	if not os.access(args.settings, os.R_OK) :
		print("[!] Can't read settings file : " + args.settings)
		sys.exit(2)
	if not os.path.isdir(args.templates) :
		print("[!] Missing templates directory : " + args.templates)
		sys.exit(1)
	if not os.access(args.templates, os.R_OK | os.X_OK) :
		print("[!] Can't read the templates directory : " + args.templates)
		sys.exit(2)
	if not os.path.isdir(args.output) :
		print("[!] Missing output directory : " + args.output)
		sys.exit(1)
	if not os.access(args.output, os.W_OK | os.X_OK) :
		print("[!] Can't write to the templates directory : " + args.output)
		sys.exit(2)
	if not os.path.exists(args.variables) :
		print("[!] Missing variables file : " + args.variables)
		sys.exit(1)
	if not os.access(args.variables, os.R_OK) :
		print("[!] Can't read variables file : " + args.variables)
		sys.exit(2)

	# Compute the final config
	configurator = Configurator()
	configurator.load_settings(args.settings)
	variables = utils.load_variables(args.variables)
	configurator.load_variables(variables)
	config = configurator.get_config()
	print(config)

	# Generate the files from templates and config
	templator = Templator(config, args.templates)
	templator.render_global(args.output)
	if config["MULTISITE"] == "no" :
		templator.render_site(args.output, config["SERVER_NAME"])
	else :
		for server_name in config["SERVER_NAME"].split(" ") :
			real_server_name = server_name
			if server_name + "_SERVER_NAME" in variables :
				real_server_name = variables[server_name + "_SERVER_NAME"]
			templator.render_site(args.output, real_server_name)

	# We're done
	print("[*] Generation done !")
	sys.exit(0)
