from datetime import datetime


def log(what, level, msg):
    when = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{when} - {what} - {level} - {msg}", flush=True)
