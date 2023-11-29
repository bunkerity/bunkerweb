# -*- coding: utf-8 -*-
from os import cpu_count, getenv, sep
from os.path import join
from utils import create_action_format

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
MODE = getenv("MODE")
LOG_LEVEL = getenv("LOG_LEVEL", "info")

reload = True if MODE == "dev" else False
wsgi_app = "main:app"
proc_name = "bunkerweb-ui"
accesslog = join(sep, "var", "log", "bunkerweb", "ui-access.log")
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
errorlog = join(sep, "var", "log", "bunkerweb", "ui.log")
loglevel = LOG_LEVEL
preload_app = True
reuse_port = True
pidfile = join(sep, "var", "run", "bunkerweb", "ui.pid")
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "ui")
secure_scheme_headers = {}
forwarded_allow_ips = "*"
pythonpath = join(sep, "usr", "share", "bunkerweb", "deps", "python")
proxy_allow_ips = "*"
workers = MAX_WORKERS
worker_class = "gevent"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 0


def on_exit(server):
    create_action_format("info", "", "", "Server stop", ["ui", "exception"], False)
    pass
