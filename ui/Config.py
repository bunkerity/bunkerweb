import json, uuid, glob, copy, re, subprocess

class Config :

    def __init__(self) :
        with open("/opt/bunkerized-nginx/settings.json", "r") as f :
            self.__settings = json.loads(f.read())

    def __env_to_dict(self, filename) :
        with open(filename, "r") as f :
            env = f.read()
        data = {}
        for line in env.split("\n") :
            var = line.split("=")[0]
            val = line.replace(var + "=", "", 1)
            data[var] = val
        return data

    def __dict_to_env(self, filename, variables) :
        env = ""
        for k, v in variables.items() :
            env += k + "=" + v + "\n"
        with open(filename, "w") as f :
            f.write(env)

    def __gen_conf(self, global_conf, services_conf) :
        conf = copy.deepcopy(global_conf)
        servers = conf["SERVER_NAME"].split(" ")
        if conf["SERVER_NAME"] == "" :
            servers = []
        for service in services_conf :
            first_server = service["SERVER_NAME"].split(" ")[0]
            if not first_server in servers :
                servers.append(first_server)
            for k, v in service.items() :
                conf[first_server + "_" + k] = v
        conf["SERVER_NAME"] = " ".join(servers)
        env_file = "/tmp/" + str(uuid.uuid4()) + ".env"
        self.__dict_to_env(env_file, conf)
        proc = subprocess.run(["/opt/bunkerized-nginx/gen/main.py", "--settings", "/opt/bunkerized-nginx/settings.json", "--templates", "/opt/bunkerized-nginx/confs", "--output", "/etc/nginx", "--variables",  env_file], capture_output=True)
        stderr = proc.stderr.decode("ascii")
        #stdout = proc.stdout.decode("ascii")
        if stderr != "" or proc.returncode != 0 :
            raise Exception("Error from generator (return code = " + str(proc.returncode) + ") : " + stderr)

    def get_settings(self) :
        return self.__settings

    def get_config(self) :
        return self.__env_to_dict("/etc/nginx/global.env")

    def get_services(self) :
        services = []
        for filename in glob.iglob("/etc/nginx/**/site.env") :
            env = self.__env_to_dict(filename)
            services.append(env)
        return services

    def check_variables(self, variables) :
        for k, v in variables.items() :
            check = False
            for category in self.__settings :
                for param in self.__settings[category]["params"] :
                    multiple = False
                    if param["type"] != "multiple" :
                        real_params = [param]
                    else :
                        real_params = param["params"]
                        multiple = True
                    for real_param in real_params :
                        if (((not multiple and k == real_param["env"]) or
                                (multiple and re.search("^" + real_param["env"] + "_" + "[0-9]+$", k))) and
                                real_param["context"] == "multisite" and
                                re.search(real_param["regex"], v)) :
                            check = True
            if not check :
                raise Exception("Variable " + k + " is not valid.")

    def new_service(self, variables) :
        global_env = self.__env_to_dict("/etc/nginx/global.env")
        services = self.get_services()
        for service in services :
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service["SERVER_NAME"] in variables["SERVER_NAME"].split(" ") :
                raise Exception("Service " + service["SERVER_NAME"] + " already exists.")
        services.append(variables)
        self.__gen_conf(global_env, services)
        return "Configuration for " + variables["SERVER_NAME"] + " has been generated."

    def edit_service(self, old_server_name, variables) :
        self.delete_service(old_server_name)
        self.new_service(variables)
        return "Configuration for " + old_server_name + " has been edited."


    def delete_service(self, server_name) :
        global_env = self.__env_to_dict("/etc/nginx/global.env")
        services = self.get_services()
        new_services = []
        found = False
        for service in services :
            if service["SERVER_NAME"].split(" ")[0] == server_name :
                found = True
            else :
                new_services.append(service)
        if not found :
            raise Exception("Can't delete missing " + server_name + " configuration.")
        new_servers = global_env["SERVER_NAME"].split(" ")
        if server_name in new_servers :
            new_servers.remove(server_name)
        global_env["SERVER_NAME"] = " ".join(new_servers)
        self.__gen_conf(global_env, new_services)
        return "Configuration for " + server_name + " has been deleted."

