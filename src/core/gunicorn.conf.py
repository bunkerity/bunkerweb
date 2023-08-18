from os import cpu_count, sep
from os.path import join

cpu_num = cpu_count() or 1

wsgi_app = "app.main:app"
proc_name = "bunkerweb-core"
accesslog = "-"
errorlog = "-"
preload_app = True
pidfile = join(sep, "var", "run", "bunkerweb", "api.pid")
workers = 4 if cpu_num > 4 else cpu_num
worker_class = "uvicorn_worker.BwUvicornWorker"
graceful_timeout = 0
