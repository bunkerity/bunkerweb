from os import sep
from os.path import join

wsgi_app = "main:app"
proc_name = "bunkerweb-ui"
accesslog = "-"
access_log_format = (
    '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
)
errorlog = "-"
preload_app = True
pidfile = join(sep, "var", "run", "bunkerweb", "ui.pid")
user = "nginx"
group = "nginx"
secure_scheme_headers = {
    "X-FORWARDED-PROTOCOL": "https",
    "X-FORWARDED-PROTO": "https",
    "X-FORWARDED-SSL": "on",
}
forwarded_allow_ips = "*"
proxy_allow_ips = "*"
bind = ["127.0.0.1:7000"]
worker_class = "gevent"
graceful_timeout = 0
