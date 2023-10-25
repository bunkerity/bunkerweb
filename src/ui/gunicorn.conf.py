from os import cpu_count, getenv, sep
from os.path import join

MAX_WORKERS = cpu_count() or 1
MAX_WORKERS = MAX_WORKERS - 1 if MAX_WORKERS > 1 else 1

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
worker_class = "uvicorn_worker.BwUiUvicornWorker"
workers = MAX_WORKERS
threads = MAX_WORKERS * 2
graceful_timeout = 0
secure_scheme_headers = {}
strip_header_spaces = True
