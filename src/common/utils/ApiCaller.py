from io import BytesIO
from os import environ, getenv
from sys import path as sys_path
from tarfile import open as taropen
from typing import Optional

if "/usr/share/bunkerweb/utils" not in sys_path:
    sys_path.append("/usr/share/bunkerweb/utils")

from logger import setup_logger
from API import API

if "/usr/share/bunkerweb/deps/python" not in sys_path:
    sys_path.append("/usr/share/bunkerweb/deps/python")

from kubernetes import client as kube_client, config
from docker import DockerClient


class ApiCaller:
    def __init__(self, apis=[]):
        self.__apis = apis
        self.__logger = setup_logger("Api", environ.get("LOG_LEVEL", "INFO"))

    def auto_setup(self, bw_integration: Optional[str] = None):
        if bw_integration is None:
            if getenv("KUBERNETES_MODE", "no") == "yes":
                bw_integration = "Kubernetes"
            elif getenv("SWARM_MODE", "no") == "yes":
                bw_integration = "Swarm"

        if bw_integration == "Kubernetes":
            config.load_incluster_config()
            corev1 = kube_client.CoreV1Api()
            for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                if (
                    pod.metadata.annotations != None
                    and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                ):
                    api_http_port = None
                    api_server_name = None

                    for pod_env in pod.spec.containers[0].env:
                        if pod_env.name == "API_HTTP_PORT":
                            api_http_port = pod_env.value or "5000"
                        elif pod_env.name == "API_SERVER_NAME":
                            api_server_name = pod_env.value or "bwapi"

                    self.__apis.append(
                        API(
                            f"http://{pod.status.pod_ip}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                            host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                        )
                    )
        else:
            docker_client = DockerClient(
                base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
            )

            if bw_integration == "Swarm":
                for instance in docker_client.services.list(
                    filters={"label": "bunkerweb.INSTANCE"}
                ):
                    api_http_port = None
                    api_server_name = None

                    for var in instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"][
                        "Env"
                    ]:
                        if var.startswith("API_HTTP_PORT="):
                            api_http_port = var.replace("API_HTTP_PORT=", "", 1)
                        elif var.startswith("API_SERVER_NAME="):
                            api_server_name = var.replace("API_SERVER_NAME=", "", 1)

                    for task in instance.tasks():
                        self.__apis.append(
                            API(
                                f"http://{instance.name}.{task['NodeID']}.{task['ID']}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                                host=api_server_name
                                or getenv("API_SERVER_NAME", "bwapi"),
                            )
                        )
                return

            for instance in docker_client.containers.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                api_http_port = None
                api_server_name = None

                for var in instance.attrs["Config"]["Env"]:
                    if var.startswith("API_HTTP_PORT="):
                        api_http_port = var.replace("API_HTTP_PORT=", "", 1)
                    elif var.startswith("API_SERVER_NAME="):
                        api_server_name = var.replace("API_SERVER_NAME=", "", 1)

                self.__apis.append(
                    API(
                        f"http://{instance.name}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                        host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                    )
                )

    def _set_apis(self, apis):
        self.__apis = apis

    def _get_apis(self):
        return self.__apis

    def _send_to_apis(self, method, url, files=None, data=None, response=False):
        ret = True
        for api in self.__apis:
            if files is not None:
                for buffer in files.values():
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent:
                ret = False
                self.__logger.error(
                    f"Can't send API request to {api.get_endpoint()}{url} : {err}",
                )
            else:
                if status != 200:
                    ret = False
                    self.__logger.error(
                        f"Error while sending API request to {api.get_endpoint()}{url} : status = {resp['status']}, msg = {resp['msg']}",
                    )
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {api.get_endpoint()}{url}",
                    )

        if response:
            if isinstance(resp, dict):
                return ret, resp
            return ret, resp.json()
        return ret

    def _send_files(self, path, url):
        ret = True
        with BytesIO() as tgz:
            with taropen(mode="w:gz", fileobj=tgz, dereference=True) as tf:
                tf.add(path, arcname=".")
            tgz.seek(0, 0)
            files = {"archive.tar.gz": tgz}
            if not self._send_to_apis("POST", url, files=files):
                ret = False
        return ret
