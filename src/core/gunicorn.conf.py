# -*- coding: utf-8 -*-
from os import cpu_count, getenv, sep
from os.path import join

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("LOG_LEVEL", "info")

wsgi_app = "app.main:app"
proc_name = "bunkerweb-core"
accesslog = join(sep, "var", "log", "bunkerweb", "core-access.log")
errorlog = join(sep, "var", "log", "bunkerweb", "core.log")
loglevel = LOG_LEVEL
preload_app = True
pidfile = join(sep, "var", "run", "bunkerweb", "core.pid")
workers = MAX_WORKERS
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
worker_class = "uvicorn_worker.BwUvicornWorker"
graceful_timeout = 5
max_requests_jitter = min(8, MAX_WORKERS)


def on_exit(server):
    from pathlib import Path

    Path(sep, "var", "tmp", "bunkerweb", "core.healthy").unlink(missing_ok=True)
    pass
