import jinja2, glob, os, pathlib, copy, crypt, random, string

class Templator :

	def __init__(self, config, input_path, output_path, target_path) :
		self.__config_global = copy.deepcopy(config)
		if config["MULTISITE"] == "yes" and config["SERVER_NAME"] != "" :
			self.__config_sites = {}
			for server_name in config["SERVER_NAME"].split(" ") :
				self.__config_sites[server_name] = {}
				for k, v in config.items() :
					if k.startswith(server_name + "_") :
						self.__config_sites[server_name][k.replace(server_name + "_", "", 1)] = v
						del self.__config_global[k]
		self.__input_path = input_path
		self.__output_path = output_path
		self.__target_path = target_path
		if not self.__target_path.endswith("/") :
			self.__target_path += "/"
		self.__template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=self.__input_path), lstrip_blocks=True, trim_blocks=True)

	def render_global(self) :
		return self.__render("global")

	def render_site(self, server_name=None, first_server=None) :
		if server_name is None :
			server_name = self.__config_global["SERVER_NAME"]
		if first_server is None :
			first_server = self.__config_global["SERVER_NAME"].split(" ")[0]
		return self.__render("site", server_name, first_server)

	def __prepare_config(self, type, server_name=None, first_server=None) :
		real_config = copy.deepcopy(self.__config_global)
		if type == "site" and self.__config_global["MULTISITE"] == "yes" :
			site_config = copy.deepcopy(self.__config_sites[first_server])
			real_config.update(site_config)
		elif type == "global" and self.__config_global["MULTISITE"] == "yes" and self.__config_global["SERVER_NAME"] != "" :
			for k, v in self.__config_sites.items() :
				for k2, v2 in v.items() :
					real_config[k + "_" + k2] = v2
		if not server_name is None :
			real_config["SERVER_NAME"] = server_name
		if not first_server is None :
			real_config["FIRST_SERVER"] = first_server
		real_config["NGINX_PREFIX"] = self.__target_path
		if self.__config_global["MULTISITE"] == "yes" and type == "site" :
			real_config["NGINX_PREFIX"] += first_server + "/"
			if not real_config["ROOT_FOLDER"].endswith("/" + first_server) :
				real_config["ROOT_FOLDER"] += "/" + first_server
		if real_config["ROOT_SITE_SUBFOLDER"] != "" :
			real_config["ROOT_FOLDER"] += "/" + real_config["ROOT_SITE_SUBFOLDER"]
		return real_config

	def __filter_var(self, variable) :
		filters = ["FIRST_SERVER", "NGINX_PREFIX"]
		for filter in filters :
			if variable == filter or variable.endswith("_" + filter) :
				return True
		return False

	def __save_config(self, type, config) :
		first_servers = config["SERVER_NAME"].split(" ")
		data = ""
		for variable, value in config.items() :
			if self.__filter_var(variable) :
				continue
			add = True
			if type == "global" :
				for first_server in first_servers :
					if variable.startswith(first_server + "_") :
						add = False
						break
			if add :
				data += variable + "=" + value + "\n"
		file = self.__output_path
		if type == "global" :
			file += "/global.env"
		elif config["MULTISITE"] == "yes" :
			file += "/" + config["FIRST_SERVER"] + "/site.env"
		else :
			file += "/site.env"
		with open(file, "w") as f :
			f.write(data)

	def __render(self, type, server_name=None, first_server=None) :
		real_config = self.__prepare_config(type, server_name, first_server)
		for filename in glob.iglob(self.__input_path + "/" + type + "**/**", recursive=True) :
			if not os.path.isfile(filename) :
				continue
			relative_filename = filename.replace(self.__input_path, "").replace(type + "/", "")
			template = self.__template_env.get_template(type + "/" + relative_filename)
			template.globals["has_value"] = Templator.has_value
			template.globals["sha512_crypt"] = Templator.sha512_crypt
			template.globals["is_custom_conf"] = Templator.is_custom_conf
			template.globals["random"] = Templator.random
			output = template.render(real_config, all=real_config)
			if real_config["MULTISITE"] == "yes" and type == "site" :
				relative_filename = real_config["FIRST_SERVER"] + "/" + relative_filename
			if "/" in relative_filename :
				directory = relative_filename.replace(relative_filename.split("/")[-1], "")
				pathlib.Path(self.__output_path + "/" + directory).mkdir(parents=True, exist_ok=True)
			with open(self.__output_path + "/" + relative_filename, "w") as f :
				f.write(output)
		self.__save_config(type, real_config)

	@jinja2.pass_context
	def has_value(context, name, value) :
		for k, v in context.items() :
			if (k == name or k.endswith("_" + name)) and v == value :
				return True
		return False

	def sha512_crypt(password) :
		return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))

	def is_custom_conf(folder) :
		for filename in glob.iglob(folder + "/*.conf") :
			return True
		return False

	def random(number) :
		return "".join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=number))
