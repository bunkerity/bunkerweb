from os import sep
from os.path import join
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

wsgi_app = "main:app"
accesslog = "/var/log/bunkerweb/ui-access.log"
errorlog = "/var/log/bunkerweb/ui.log"
loglevel = "info"
proc_name = "bunkerweb-ui"
preload_app = True
reuse_port = True
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "ui")
worker_class = "gthread"
graceful_timeout = 0
secure_scheme_headers = {}
