from io import BytesIO
from os import environ, getenv
from os.path import exists
from tarfile import open as taropen

from logger import setup_logger
from API import API


class ApiCaller:
    def __init__(self, apis=[]):
        self.__apis = apis
        self.__logger = setup_logger("Api", environ.get("LOG_LEVEL", "INFO"))

    def auto_setup(self, bw_integration: str = None):
        if bw_integration is None and getenv("KUBERNETES_MODE", "no") == "yes":
            bw_integration = "Kubernetes"

        if bw_integration == "Kubernetes":
            from kubernetes import client as kube_client

            corev1 = kube_client.CoreV1Api()
            for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                if (
                    pod.metadata.annotations != None
                    and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                ):
                    api = None
                    for pod_env in pod.spec.containers[0].env:
                        if pod_env.name == "API_HTTP_PORT":
                            api = API(
                                f"http://{pod.status.pod_ip}:{pod_env.value or '5000'}"
                            )
                            break

                    if api:
                        self.__apis.append(api)
                    else:
                        self.__apis.append(
                            API(
                                f"http://{pod.status.pod_ip}:{getenv('API_HTTP_PORT', '5000')}"
                            )
                        )
        else:
            from docker import DockerClient

            docker_client = DockerClient(
                base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
            )
            for instance in docker_client.containers.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                api = None
                for var in instance.attrs["Config"]["Env"]:
                    if var.startswith("API_HTTP_PORT="):
                        api = API(
                            f"http://{instance.name}:{var.replace('API_HTTP_PORT=', '', 1)}"
                        )
                        break

                if api:
                    self.__apis.append(api)
                else:
                    self.__apis.append(
                        API(f"http://{instance.name}:{getenv('API_HTTP_PORT', '5000')}")
                    )

    def _set_apis(self, apis):
        self.__apis = apis

    def _get_apis(self):
        return self.__apis

    def _send_to_apis(self, method, url, files=None, data=None):
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
        return ret

    def _send_files(self, path, url):
        ret = True
        tgz = BytesIO()
        with taropen(mode="w:gz", fileobj=tgz) as tf:
            tf.add(path, arcname=".")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}
        if not self._send_to_apis("POST", url, files=files):
            ret = False
        tgz.close()
        return ret
