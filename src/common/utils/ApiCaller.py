#!/usr/bin/python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger

from docker import DockerClient
from kubernetes import client as kube_client, config


class ApiCaller:
    def __init__(self, apis: Optional[List[API]] = None):
        self.__apis = apis or []
        self.__logger = setup_logger("Api", getenv("LOG_LEVEL", "INFO"))

    @property
    def apis(self) -> List[API]:
        return self.__apis

    @apis.setter
    def apis(self, apis: List[API]):
        self.__apis = apis

    def auto_setup(self, bw_integration: Optional[str] = None):
        self.__apis.clear()
        if bw_integration is None:
            if getenv("KUBERNETES_MODE", "no") == "yes":
                bw_integration = "Kubernetes"
            elif getenv("SWARM_MODE", "no") == "yes":
                bw_integration = "Swarm"

        if bw_integration == "Kubernetes":
            config.load_incluster_config()
            corev1 = kube_client.CoreV1Api()
            for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                if pod.metadata.annotations is not None and "bunkerweb.io/INSTANCE" in pod.metadata.annotations:
                    api_http_port = None
                    api_server_name = None

                    for pod_env in pod.spec.containers[0].env:
                        if pod_env.name == "API_HTTP_PORT":
                            api_http_port = pod_env.value or "5000"
                        elif pod_env.name == "API_SERVER_NAME":
                            api_server_name = pod_env.value or "bwapi"

                    self.__apis.append(
                        API(
                            f"http://{getenv("API_HTTP_HOST", pod.status.pod_ip)}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                            host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                        )
                    )
        else:
            docker_client = DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))

            if bw_integration == "Swarm":
                for instance in docker_client.services.list(filters={"label": "bunkerweb.INSTANCE"}):
                    api_http_port = None
                    api_server_name = None

                    for var in instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]:
                        if var.startswith("API_HTTP_PORT="):
                            api_http_port = var.replace("API_HTTP_PORT=", "", 1)
                        elif var.startswith("API_SERVER_NAME="):
                            api_server_name = var.replace("API_SERVER_NAME=", "", 1)

                    for task in instance.tasks():
                        self.__apis.append(
                            API(
                                f"http://{getenv("API_HTTP_HOST", ".".join([ instance.name, task['NodeID'], task['ID'] ]))}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                                host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                            )
                        )
                return

            for instance in docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"}):
                api_http_port = None
                api_server_name = None

                for var in instance.attrs["Config"]["Env"]:
                    if var.startswith("API_HTTP_PORT="):
                        api_http_port = var.replace("API_HTTP_PORT=", "", 1)
                    elif var.startswith("API_SERVER_NAME="):
                        api_server_name = var.replace("API_SERVER_NAME=", "", 1)

                self.__apis.append(
                    API(
                        f"http://{getenv("API_HTTP_HOST", instance.name)}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                        host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                    )
                )

    def send_to_apis(
        self,
        method: Union[Literal["POST"], Literal["GET"]],
        url: str,
        files: Optional[Dict[str, BytesIO]] = None,
        data: Optional[Dict[str, Any]] = None,
        response: bool = False,
    ) -> Tuple[bool, Tuple[bool, Optional[Dict[str, Any]]]]:
        ret = True
        url = url if not url.startswith("/") else url[1:]
        responses = {}
        for api in self.__apis:
            if files is not None:
                for buffer in files.values():
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent:
                ret = False
                self.__logger.error(
                    f"Can't send API request to {api.endpoint}{url} : {err}",
                )
            else:
                if status != 200:
                    ret = False
                    self.__logger.error(
                        f"Error while sending API request to {api.endpoint}{url} : status = {resp['status']}, msg = {resp['msg']}",
                    )
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {api.endpoint}{url}",
                    )

                    if response:
                        instance = api.endpoint.replace("http://", "").split(":")[0]
                        if isinstance(resp, dict):
                            responses[instance] = resp
                        else:
                            responses[instance] = resp.json()

        if response and responses:
            return ret, responses
        return ret

    def send_files(self, path: str, url: str) -> bool:
        ret = True
        with BytesIO() as tgz:
            with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                tf.add(path, arcname=".")
            tgz.seek(0, 0)
            files = {"archive.tar.gz": tgz}
            if not self.send_to_apis("POST", url, files=files):
                ret = False
        return ret
