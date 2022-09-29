import os
from typing import Any, Union
from subprocess import run

from API import API
from ApiCaller import ApiCaller


class Instance:
    _id: str
    name: str
    hostname: str
    _type: str
    health: bool
    env: Any
    apiCaller: ApiCaller

    def __init__(
        self,
        _id: str,
        name: str,
        hostname: str,
        _type: str,
        status: str,
        data: Any = None,
        apiCaller: ApiCaller = ApiCaller(),
    ) -> None:
        self._id = _id
        self.name = name
        self.hostname = hostname
        self._type = _type
        self.health = status == "up" and (
            (
                data.attrs["State"]["Health"]["Status"] == "healthy"
                if "Health" in data.attrs["State"]
                else False
            )
            if data
            else True
        )
        self.env = data
        self.apiCaller = apiCaller

    def get_id(self) -> str:
        return self._id

    def run_jobs(self) -> bool:
        return self.apiCaller._send_to_apis("POST", "/jobs")

    def reload(self) -> bool:
        return self.apiCaller._send_to_apis("POST", "/reload")

    def start(self) -> bool:
        return self.apiCaller._send_to_apis("POST", "/start")

    def stop(self) -> bool:
        return self.apiCaller._send_to_apis("POST", "/stop")

    def restart(self) -> bool:
        return self.apiCaller._send_to_apis("POST", "/restart")


class Instances:
    def __init__(self, docker_client):
        self.__docker = docker_client

    def __instance_from_id(self, _id) -> Instance:
        instances: list[Instance] = self.get_instances()
        for instance in instances:
            if instance._id == _id:
                return instance

        raise Exception(f"Can't find instance with id {_id}")

    def get_instances(self) -> list[Instance]:
        instances = []
        # Docker instances (containers or services)
        if self.__docker is not None:
            for instance in self.__docker.containers.list(
                all=True, filters={"label": "bunkerweb.UI"}
            ):
                env_variables = {
                    x[0]: x[1]
                    for x in [env.split("=") for env in instance.attrs["Config"]["Env"]]
                }

                apiCaller = ApiCaller()
                apiCaller._set_apis(
                    [
                        API(
                            f"http://{instance.name}:{env_variables.get('API_HTTP_PORT', '5000')}",
                            env_variables.get("API_SERVER_NAME", "bwapi"),
                        )
                    ]
                )

                instances.append(
                    Instance(
                        instance.id,
                        instance.name,
                        instance.name,
                        "container",
                        "up" if instance.status == "running" else "down",
                        instance,
                        apiCaller,
                    )
                )

        instances = sorted(
            instances,
            key=lambda x: x.name,
        )

        # Local instance
        if os.path.exists("/usr/sbin/nginx"):
            instances.insert(
                0,
                Instance(
                    "local",
                    "local",
                    "127.0.0.1",
                    "local",
                    "up" if os.path.exists("/opt/bunkerweb/tmp/nginx.pid") else "down",
                ),
            )

        return instances

    def reload_instances(self) -> Union[list[str], str]:
        not_reloaded: list[str] = []
        for instance in self.get_instances():
            if instance.health is False:
                not_reloaded.append(instance.name)
                continue

            if self.reload_instance(instance=instance).startswith("Can't reload"):
                not_reloaded.append(instance.name)

        return not_reloaded or "Successfully reloaded instances"

    def reload_instance(self, id: int = None, instance: Instance = None) -> str:
        if instance is None:
            instance = self.__instance_from_id(id)

        result = True
        if instance._type == "local":
            result = (
                run(
                    ["sudo", "systemctl", "restart", "bunkerweb"], capture_output=True
                ).returncode
                != 0
            )
        elif instance._type == "container":
            result = instance.run_jobs()
            result = result & instance.reload()

        if result:
            return f"Instance {instance.name} has been reloaded."

        return f"Can't reload {instance.name}"

    def start_instance(self, id) -> str:
        instance = self.__instance_from_id(id)
        result = True

        if instance._type == "local":
            proc = run(
                ["sudo", "/opt/bunkerweb/ui/linux.sh", "start"],
                capture_output=True,
            )
            result = proc.returncode == 0
        elif instance._type == "container":
            result = instance.start()

        if result:
            return f"Instance {instance.name} has been started."

        return f"Can't start {instance.name}"

    def stop_instance(self, id) -> str:
        instance = self.__instance_from_id(id)
        result = True

        if instance._type == "local":
            proc = run(
                ["sudo", "/opt/bunkerweb/ui/linux.sh", "stop"],
                capture_output=True,
            )
            result = proc.returncode == 0
        elif instance._type == "container":
            result = instance.stop()

        if result:
            return f"Instance {instance.name} has been stopped."

        return f"Can't stop {instance.name}"

    def restart_instance(self, id) -> str:
        instance = self.__instance_from_id(id)
        result = True

        if instance._type == "local":
            proc = run(
                ["sudo", "/opt/bunkerweb/ui/linux.sh", "restart"],
                capture_output=True,
            )
            result = proc.returncode == 0
        elif instance._type == "container":
            result = instance.restart()

        if result:
            return f"Instance {instance.name} has been restarted."

        return f"Can't restart {instance.name}"
