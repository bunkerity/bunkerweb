from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from sys import modules
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = spec_from_file_location("bw_api_celery_app", ROOT / "src" / "api" / "app" / "celery_app.py")
CELERY_APP = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CELERY_APP)


class _Celery:
    def __init__(self, *_args, **_kwargs):
        self.conf = {}


def test_api_producer_bounds_blackholed_broker_connections(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://broker.invalid:6379/0")
    CELERY_APP.celery_app = None
    celery = ModuleType("celery")
    celery.Celery = _Celery

    with patch.dict(modules, {"celery": celery}):
        app = CELERY_APP.get_celery_app()
    options = app.conf["broker_transport_options"]

    assert options["socket_connect_timeout"] > 0
    assert options["socket_timeout"] > options.get("polling_interval", 1)
