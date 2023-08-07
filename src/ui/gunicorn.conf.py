from os import sep
from os.path import join

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
worker_class = "gevent"
threads = 1
workers = 1
graceful_timeout = 0
secure_scheme_headers = {}