# -*- coding: utf-8 -*-
from os import cpu_count, getenv, sep
from os.path import join
from utils import create_action_format

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
MODE = getenv("MODE")

reload = True if MODE == "dev" else False
wsgi_app = "main:app"
accesslog = join(sep, "var", "log", "bunkerweb", "ui-access.log")
errorlog = join(sep, "var", "log", "bunkerweb", "ui.log")
proc_name = "bunkerweb-ui"
preload_app = True
reuse_port = True
pidfile = join(sep, "var", "run", "bunkerweb", "ui.pid")
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "ui")
worker_class = "gevent"
workers = MAX_WORKERS
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
graceful_timeout = 0
max_requests_jitter = min(8, MAX_WORKERS)
secure_scheme_headers = {}
strip_header_spaces = True


def on_exit(server):
    create_action_format("info", "", "", "Server stop", ["ui", "exception"], False)
    pass