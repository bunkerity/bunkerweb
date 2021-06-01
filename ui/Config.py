import json, uuid, glob, copy

class Config :

    def __init__(self) :
        with open("/opt/settings.json", "r") as f :
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
        for service in services_conf :
            first_server = service["SERVER_NAME"].split(" ")[0]
            for k, v in service.items() :
                conf[first_server + "_" + k] = v
        env_file = "/tmp/" + str(uuid.uuid4()) + ".env"
        self.__dict_to_env(env_file, conf)
        proc = subprocess.run(["/bin/su", "-c", "/opt/gen/main.py --settings /opt/settings.json --templates /opt/confs --output /etc/nginx --variables " + env_file, "nginx"], capture_output=True)
        stderr = proc.stderr.decode("ascii")
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
                    if type != "multiple" :
                        real_params = [param]
                    else :
                        real_params = param
                    for real_param in real_params :
                        if k == real_param["env"] and real_param["context"] == "multisite" and re.search(real_param["regex"], v) :
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

    def edit_service(self, old_server_name, variables) :
        self.delete_service(old_server_name)
        self.new_service(variables)


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
        self.__gen_conf(global_env, new_services)

