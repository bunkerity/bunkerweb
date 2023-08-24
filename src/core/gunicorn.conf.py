from os import cpu_count, sep
from os.path import join

MAX_WORKERS = cpu_count() or 1
MAX_WORKERS = MAX_WORKERS - 1 if MAX_WORKERS > 1 else 1

wsgi_app = "app.main:app"
proc_name = "bunkerweb-core"
accesslog = "-"
errorlog = "-"
preload_app = True
pidfile = join(sep, "var", "run", "bunkerweb", "core.pid")
workers = MAX_WORKERS
threads = MAX_WORKERS * 2
worker_class = "uvicorn_worker.BwUvicornWorker"
graceful_timeout = 5
max_requests_jitter = min(8, MAX_WORKERS)
