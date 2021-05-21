import jinja2, glob, os, pathlib, copy

class Templator :

	def __init__(self, config, input_path) :
		self.__config = config
		self.__input_path = input_path
		self.__template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=input_path))

	def render_global(self, output_path) :
		return self.__render("global", output_path)

	def render_site(self, output_path, server_name) :
		return self.__render("site", output_path, server_name)

	def __render(self, type, output_path, server_name=None) :
		real_config = copy.deepcopy(self.__config)
		if server_name != None :
			real_config["SERVER_NAME"] = server_name
		for filename in glob.iglob(self.__input_path + "/" + type + "**/**", recursive=True) :
			if os.path.isfile(filename) :
				relative_filename = filename.replace(self.__input_path, "").replace(type + "/", "")
				template = self.__template_env.get_template(type + "/" + relative_filename)
				template.globals["has_value"] = Templator.has_value
				output = template.render(real_config, all=real_config)
				if "/" in relative_filename :
					directory = relative_filename.replace(relative_filename.split("/")[-1], "")
					pathlib.Path(output_path + "/" + directory).mkdir(parents=True, exist_ok=True)
				with open(output_path + "/" + relative_filename, "w") as f :
					f.write(output)

	@jinja2.contextfunction
	def has_value(context, name, value) :
		for k, v in context.items() :
			if (k == name or k.endswith("_" + name)) and v == value :
				return True
		return False
