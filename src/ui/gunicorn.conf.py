from os import cpu_count, getenv, getpid, sep
from os.path import join
from pathlib import Path
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)


TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
RUN_DIR = Path(sep, "var", "run", "bunkerweb")

MAX_WORKERS = int(getenv("MAX_WORKERS", max((cpu_count() or 1) - 1, 1)))
LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "info"))

wsgi_app = "main:app"
proc_name = "bunkerweb-ui"
accesslog = "/var/log/bunkerweb/ui-access.log"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
errorlog = "/var/log/bunkerweb/ui.log"
preload_app = True
reuse_port = True
worker_tmp_dir = join(sep, "dev", "shm")
tmp_upload_dir = join(sep, "var", "tmp", "bunkerweb", "ui")
secure_scheme_headers = {}
workers = MAX_WORKERS
worker_class = "gthread"
threads = int(getenv("MAX_THREADS", MAX_WORKERS * 2))
max_requests_jitter = min(8, MAX_WORKERS)
graceful_timeout = 30

DEBUG = getenv("DEBUG", False)

loglevel = "debug" if DEBUG else LOG_LEVEL.lower()

if DEBUG:
    reload = True
    reload_extra_files = [file.as_posix() for file in Path(sep, "usr", "share", "bunkerweb", "ui", "templates").iterdir()]


def when_ready(server):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.joinpath("ui.pid").write_text(str(getpid()), encoding="utf-8")
    TMP_DIR.joinpath("ui.healthy").write_text("ok", encoding="utf-8")


def on_exit(server):
    RUN_DIR.joinpath("ui.pid").unlink(missing_ok=True)
    TMP_DIR.joinpath("ui.healthy").unlink(missing_ok=True)
    TMP_DIR.joinpath(".flask_secret").unlink(missing_ok=True)
