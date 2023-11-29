# -*- coding: utf-8 -*-
from os import cpu_count, getenv, sep
from os.path import join

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("LOG_LEVEL", "info")
REVERSE_PROXY_IPS = getenv("REVERSE_PROXY_IPS", "127.0.0.1")

wsgi_app = "app.main:app"
proc_name = "bunkerweb-core"
accesslog = join(sep, "var", "log", "bunkerweb", "core-access.log")
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
errorlog = join(sep, "var", "log", "bunkerweb", "core.log")
loglevel = LOG_LEVEL
preload_app = True
reuse_port = True
pidfile = join(sep, "var", "run", "bunkerweb", "core.pid")
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "core")
secure_scheme_headers = {}
forwarded_allow_ips = REVERSE_PROXY_IPS
pythonpath = join(sep, "usr", "share", "bunkerweb", "deps", "python")
proxy_allow_ips = REVERSE_PROXY_IPS
workers = MAX_WORKERS
worker_class = "uvicorn_worker.BwUvicornWorker"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 5


def on_exit(server):
    from pathlib import Path

    Path(sep, "var", "tmp", "bunkerweb", "core.healthy").unlink(missing_ok=True)
    pass
