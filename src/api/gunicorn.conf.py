from os import sep
from os.path import join

wsgi_app = "main:app"
proc_name = "bunkerweb-api"
accesslog = "-"
errorlog = "-"
preload_app = True
pidfile = join(sep, "var", "run", "bunkerweb", "api.pid")
worker_class = "main.BwUvicornWorker"
graceful_timeout = 0
