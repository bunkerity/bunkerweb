from pathlib import Path
from dotenv import dotenv_values
from docker import DockerClient
from kubernetes import client, config

from ApiCaller import ApiCaller
from API import API


def format_remaining_time(seconds):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if days > 0:
        time_parts.append(f"{int(days)} day{'' if days == 1 else 's'}")
    if hours > 0:
        time_parts.append(f"{int(hours)} hour{'' if hours == 1 else 's'}")
    if minutes > 0:
        time_parts.append(f"{int(minutes)} minute{'' if minutes == 1 else 's'}")
    if seconds > 0:
        time_parts.append(f"{seconds:.2f} second{'' if seconds == 1 else 's'}")

    if len(time_parts) > 1:
        time_parts[-1] = f"and {time_parts[-1]}"

    return " ".join(time_parts)


class CLI(ApiCaller):
    def __init__(self):
        self.__variables = dotenv_values("/etc/nginx/variables.env")
        self.__integration = self.__detect_integration()
        super().__init__(self.__get_apis())

    def __detect_integration(self):
        distrib = ""
        if Path("/etc/os-release").is_file():
            with open("/etc/os-release", "r") as f:
                if "Alpine" in f.read():
                    distrib = "alpine"
                else:
                    distrib = "other"
        # Docker case
        if distrib == "alpine" and Path("/usr/sbin/nginx").is_file():
            return "docker"
        # Linux case
        if distrib == "other":
            return "linux"
        # Swarm case
        if self.__variables["SWARM_MODE"] == "yes":
            return "swarm"
        # Kubernetes case
        if self.__variables["KUBERNETES_MODE"] == "yes":
            return "kubernetes"
        # Autoconf case
        if distrib == "alpine":
            return "autoconf"

        raise Exception("Can't detect integration")

    def __get_apis(self):
        # Docker case
        if self.__integration in ("docker", "linux"):
            return [
                API(
                    f"http://127.0.0.1:{self.__variables['API_HTTP_PORT']}",
                    host=self.__variables["API_SERVER_NAME"],
                )
            ]

        # Autoconf case
        if self.__integration == "autoconf":
            docker_client = DockerClient()
            apis = []
            for container in self.__client.containers.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                port = "5000"
                host = "bwapi"
                for env in container.attrs["Config"]["Env"]:
                    if env.startswith("API_HTTP_PORT="):
                        port = env.split("=")[1]
                    elif env.startswith("API_SERVER_NAME="):
                        host = env.split("=")[1]
                apis.append(API(f"http://{container.name}:{port}", host=host))
            return apis

        # Swarm case
        if self.__integration == "swarm":
            docker_client = DockerClient()
            apis = []
            for service in self.__client.services.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                port = "5000"
                host = "bwapi"
                for env in service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"][
                    "Env"
                ]:
                    if env.startswith("API_HTTP_PORT="):
                        port = env.split("=")[1]
                    elif env.startswith("API_SERVER_NAME="):
                        host = env.split("=")[1]
                for task in service.tasks():
                    apis.append(
                        API(
                            f"http://{service.name}.{task['NodeID']}.{task['ID']}:{port}",
                            host=host,
                        )
                    )
            return apis

        # Kubernetes case
        if self.__integration == "kubernetes":
            config.load_incluster_config()
            corev1 = client.CoreV1Api()
            apis = []
            for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                if (
                    pod.metadata.annotations != None
                    and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                    and pod.status.pod_ip
                ):
                    port = "5000"
                    host = "bwapi"
                    for env in pod.spec.containers[0].env:
                        if env.name == "API_HTTP_PORT":
                            port = env.value
                        elif env.name == "API_SERVER_NAME":
                            host = env.value
                    apis.append(API(f"http://{pod.status.pod_ip}:{port}", host=host))
            return apis

    def unban(self, ip):
        if self._send_to_apis("POST", "/unban", data={"ip": ip}):
            return True, f"IP {ip} has been unbanned"
        return False, "error"

    def ban(self, ip, exp):
        if self._send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp}):
            return True, f"IP {ip} has been banned"
        return False, "error"

    def bans(self):
        ret, resp = self._send_to_apis("GET", "/bans", response=True)
        if ret:
            bans = resp.get("data", [])

            if len(bans) == 0:
                return True, "No ban found"

            cli_str = "List of bans :\n"
            for ban in bans:
                cli_str += f"- {ban['ip']} for {format_remaining_time(ban['exp'])} : {ban.get('reason', 'no reason given')}\n"
            return True, cli_str
        return False, "error"
