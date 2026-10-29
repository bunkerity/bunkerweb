from datetime import datetime
from functools import cache
from logging import Logger
from math import ceil
from typing import Dict, List, Literal

from kubernetes.client import CoreV1Api
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.config import load_kube_config
from kubernetes.stream import stream

POD_INFO: Dict[Literal["bunkerweb", "scheduler", "database"], Dict[Literal["namespace", "annotation"], str]] = {
    "bunkerweb": {
        "namespace": "bunkerweb",
        "annotation": "bunkerweb.io/INSTANCE",
    },
    "controller": {
        "namespace": "bunkerweb",
        "annotation": "bunkerweb.io/CONTROLLER",
    },
    "scheduler": {
        "namespace": "bunkerweb",
        "annotation": "bunkerweb.io/SCHEDULER",
    },
    "database": {
        "namespace": "bunkerweb-db",
        "annotation": "bunkerweb.io/DB",
    },
}


@cache
def get_corev1() -> CoreV1Api:
    load_kube_config()
    return CoreV1Api()


@cache
def get_pod(logger: Logger, _type: Literal["bunkerweb", "controller", "scheduler", "database"]) -> V1Pod:
    corev1 = get_corev1()

    info = POD_INFO.get(_type)
    if not info:
        raise ValueError(f"Invalid pod type: {_type}")

    bw_pods = [
        pod
        for pod in corev1.list_namespaced_pod(info["namespace"], watch=False).items
        if pod.metadata.annotations and info["annotation"] in pod.metadata.annotations
    ]

    if not bw_pods:
        logger.error(f"No {_type.title()} pod found")
        exit(1)

    return bw_pods[0]


def get_logs(logger: Logger, _type: Literal["bunkerweb", "controller", "scheduler", "database"], since: float) -> str:
    pod = get_pod(logger, _type)
    corev1 = get_corev1()

    kwargs = {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "container": pod.spec.containers[0].name,
        "timestamps": True,
    }
    if since:
        kwargs["since_seconds"] = ceil((datetime.now(tz=since.tzinfo) - since).total_seconds())

    return corev1.read_namespaced_pod_log(**kwargs).strip().split("\n")


def run_command(logger: Logger, _type: Literal["bunkerweb", "controller", "scheduler", "database"], command: List[str]) -> str:
    pod = get_pod(logger, _type)
    corev1 = get_corev1()

    return stream(
        corev1.connect_get_namespaced_pod_exec,
        name=pod.metadata.name,
        namespace=pod.metadata.namespace,
        command=command,
        container=pod.spec.containers[0].name,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    ).strip()
