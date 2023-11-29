# -*- coding: utf-8 -*-
from os import cpu_count, getenv, sep
from os.path import join
from pathlib import Path

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("LOG_LEVEL", "info")
REVERSE_PROXY_IPS = getenv("REVERSE_PROXY_IPS", "127.0.0.1")
USE_PROXY_PROTOCOL = getenv("CORE_USE_PROXY_PROTOCOL", "no")

integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
os_release_path = Path(sep, "etc", "os-release")
integration = "Linux"
if integration_path.is_file():
    integration = integration_path.read_text(encoding="utf-8").strip()
elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
    integration = "Docker"


wsgi_app = "app.main:app"
proc_name = "bunkerweb-core"
accesslog = join(sep, "var", "log", "bunkerweb", "core-access.log")
errorlog = join(sep, "var", "log", "bunkerweb", "core.log")
loglevel = LOG_LEVEL
capture_output = integration == "Linux"
preload_app = True
reuse_port = True
pidfile = join(sep, "var", "run", "bunkerweb", "core.pid")
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "core")
secure_scheme_headers = {}
forwarded_allow_ips = REVERSE_PROXY_IPS
pythonpath = join(sep, "usr", "share", "bunkerweb", "deps", "python")
proxy_protocol = USE_PROXY_PROTOCOL == "yes"
proxy_allow_ips = REVERSE_PROXY_IPS
workers = MAX_WORKERS
worker_class = "uvicorn_worker.BwUvicornWorker"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 5


def on_exit(server):
    Path(sep, "var", "tmp", "bunkerweb", "core.healthy").unlink(missing_ok=True)
    pass
