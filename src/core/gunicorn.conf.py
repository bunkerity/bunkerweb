# -*- coding: utf-8 -*-
from os import cpu_count, getenv, sep
from os.path import join
from pathlib import Path

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("LOG_LEVEL", "info")
REVERSE_PROXY_IPS = getenv("REVERSE_PROXY_IPS", "127.0.0.1")
LISTEN_ADDR = getenv("LISTEN_ADDR", "0.0.0.0")
LISTEN_PORT = getenv("LISTEN_PORT", "1337")

wsgi_app = "app.main:app"
proc_name = "bunkerweb-core"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
loglevel = LOG_LEVEL
capture_output = True
preload_app = True
reuse_port = True
pidfile = join(sep, "var", "run", "bunkerweb", "core.pid")
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "core")
secure_scheme_headers = {}
forwarded_allow_ips = REVERSE_PROXY_IPS
pythonpath = join(sep, "usr", "share", "bunkerweb", "deps", "python")
proxy_allow_ips = REVERSE_PROXY_IPS
bind = f"{LISTEN_ADDR}:{LISTEN_PORT}"
workers = MAX_WORKERS
worker_class = "uvicorn_worker.BwUvicornWorker"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 5


def on_exit(server):
    Path(sep, "var", "tmp", "bunkerweb", "core.healthy").unlink(missing_ok=True)
    pass
