from os import cpu_count, getenv, sep
from os.path import join
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from gevent import monkey

monkey.patch_all()

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))

wsgi_app = "main:app"
accesslog = "/var/log/bunkerweb/ui-access.log"
errorlog = "/var/log/bunkerweb/ui.log"
loglevel = "info"
proc_name = "bunkerweb-ui"
preload_app = True
reuse_port = True
pidfile = join(sep, "var", "run", "bunkerweb", "ui.pid")
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "ui")
workers = MAX_WORKERS
worker_class = "gevent"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
graceful_timeout = 0
secure_scheme_headers = {}
