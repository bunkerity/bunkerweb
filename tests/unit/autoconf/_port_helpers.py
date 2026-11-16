"""Load real autoconf code with only the unavailable Kubernetes transport replaced."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


def load_controllers():
    kubernetes = ModuleType("kubernetes")
    kubernetes.client = ModuleType("kubernetes.client")
    kubernetes.client.Configuration = NS(_default=NS())

    class ApiClient:
        def call_api(self, *args, **kwargs):
            return {"ok": True}

    kubernetes.client.ApiClient = ApiClient
    for name in ("CoreV1Api", "NetworkingV1Api", "CustomObjectsApi"):
        setattr(kubernetes.client, name, Mock(return_value=Mock()))
    kubernetes.config = Mock()
    # A real `Watch` attribute, not a bare Mock: pytest 9's monkeypatch undo deletes the child a Mock auto-created,
    # so a later `monkeypatch.setattr(K8S.watch, "Watch", ...)` raised AttributeError.
    kubernetes.watch = NS(Watch=Mock())
    exceptions = ModuleType("kubernetes.client.exceptions")

    class ApiException(Exception):
        def __init__(self, status=None, reason=None):
            super().__init__(f"{status} {reason}")
            self.status, self.reason = status, reason

    exceptions.ApiException = ApiException
    modules = {
        "kubernetes": kubernetes,
        "kubernetes.client": kubernetes.client,
        "kubernetes.client.exceptions": exceptions,
        "controllers": ModuleType("controllers"),
    }
    loaded = []
    with patch.dict(sys.modules, modules):
        for name, relative in (
            ("api_client", "api_client.py"),
            ("Config", "Config.py"),
            ("controllers.Controller", "controllers/Controller.py"),
            ("controllers.KubernetesController", "controllers/KubernetesController.py"),
            ("controllers.IngressController", "controllers/IngressController.py"),
            ("controllers.GatewayController", "controllers/GatewayController.py"),
        ):
            spec = importlib.util.spec_from_file_location(name, ROOT / "src/autoconf" / relative)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded.append(module)
    return loaded[2:]


BASE, K8S, INGRESS, GATEWAY = load_controllers()


def bare_controller(cls=K8S.KubernetesController):
    controller = object.__new__(cls)
    controller._logger = Mock()
    controller._namespaces = []
    controller._should_ignore_annotation = lambda annotation: annotation == "ignore"
    controller._corev1 = Mock()
    controller._domain_name = "cluster.local"
    controller._use_fqdn = True
    controller._get_controller_services = lambda: []
    return controller
