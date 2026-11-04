"""Fixtures for the scheduler tests: import ``src/scheduler/main.py`` and ``JobScheduler.py`` safely.

``main.py`` no longer touches the filesystem or the signal table at import (``ensure_runtime_dirs()`` and
``install_signal_handlers()`` run from ``main()``), so it is loaded under a private module name. ``src/common/gen``
also ships a ``main.py``; the unique name keeps the two apart.
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]
# BW_SCHEDULER_SRC points the tests at a scratch copy of src/scheduler (a deliberately broken one, to watch them fail).
SCHEDULER_SRC = Path(os.environ.get("BW_SCHEDULER_SRC", REPO / "src" / "scheduler"))
if "BW_SCHEDULER_SRC" in os.environ:
    sys.path.insert(0, str(SCHEDULER_SRC))
for _path in (SCHEDULER_SRC, REPO / "src" / "common" / "gen"):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))


@pytest.fixture(scope="session")
def sched_main():
    """The scheduler's ``main`` module, imported once. Tests patch its attributes with monkeypatch."""
    spec = importlib.util.spec_from_file_location("bw_scheduler_main_under_test", SCHEDULER_SRC / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def job_scheduler_module():
    import JobScheduler as module

    return module


@pytest.fixture
def sched_logger():
    """A stdlib logger that propagates, so ``caplog`` sees what the scheduler logs."""
    logger = logging.getLogger("bw-scheduler-unit")
    logger.setLevel(logging.DEBUG)
    logger.propagate = True
    return logger


@pytest.fixture
def fake_api(sched_main, monkeypatch):
    """Replace ``API`` inside main.py: ``from_instance`` hands out FakeApi clients, ``build_endpoint`` stays real."""
    from scheduler_fakes import FakeApi

    real = sched_main.API
    answers = {}
    built = []

    def from_instance(db_instance):
        api = FakeApi(
            real.build_endpoint(
                db_instance["hostname"],
                port=db_instance.get("port"),
                listen_https=bool(db_instance.get("listen_https")),
                https_port=db_instance.get("https_port"),
            )
            + "/"
        )
        if db_instance["hostname"] in answers:
            api.answer = answers[db_instance["hostname"]]
        built.append(api)
        return api

    monkeypatch.setattr(sched_main, "API", SimpleNamespace(from_instance=from_instance, build_endpoint=real.build_endpoint))
    return SimpleNamespace(answers=answers, built=built)


@pytest.fixture
def fake_sched(sched_main, monkeypatch):
    """A FakeScheduler installed as ``main.SCHEDULER`` (the module global every helper reads)."""
    from scheduler_fakes import FakeScheduler

    sched = FakeScheduler()
    monkeypatch.setattr(sched_main, "SCHEDULER", sched)
    return sched


@pytest.fixture
def sandbox(sched_main, monkeypatch, tmp_path):
    """Point every path constant of main.py at tmp_path, and ``sep`` so inline ``Path(sep, "var", ...)`` follow."""
    root = tmp_path / "root"
    paths = {
        "CACHE_PATH": root / "var" / "cache" / "bunkerweb",
        "CUSTOM_CONFIGS_PATH": root / "etc" / "bunkerweb" / "configs",
        "EXTERNAL_PLUGINS_PATH": root / "etc" / "bunkerweb" / "plugins",
        "PRO_PLUGINS_PATH": root / "etc" / "bunkerweb" / "pro" / "plugins",
        "CONFIG_PATH": root / "etc" / "nginx",
        "TMP_PATH": root / "var" / "tmp" / "bunkerweb",
    }
    paths["NGINX_VARIABLES_PATH"] = paths["CONFIG_PATH"] / "variables.env"
    paths["NGINX_TMP_VARIABLES_PATH"] = paths["TMP_PATH"] / "variables.env"
    paths["FAILOVER_PATH"] = paths["TMP_PATH"] / "failover"
    paths["HEALTHY_PATH"] = paths["TMP_PATH"] / "scheduler.healthy"
    paths["DB_LOCK_FILE"] = root / "var" / "lib" / "bunkerweb" / "db.lock"
    for name, path in paths.items():
        monkeypatch.setattr(sched_main, name, path)
    monkeypatch.setattr(sched_main, "sep", str(root))
    for name in ("CACHE_PATH", "CUSTOM_CONFIGS_PATH", "EXTERNAL_PLUGINS_PATH", "PRO_PLUGINS_PATH", "CONFIG_PATH", "TMP_PATH", "FAILOVER_PATH"):
        paths[name].mkdir(parents=True, exist_ok=True)
    (root / "var" / "run" / "bunkerweb").mkdir(parents=True)
    return SimpleNamespace(root=root, **paths)
