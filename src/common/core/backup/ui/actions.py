from datetime import datetime
from json import loads
from traceback import format_exc


def pre_render(app, *args, **kwargs):
    try:
        data = loads(app.config["DB"].get_job_cache_file("backup-data", "backup.json") or "{}")

        if data.get("date", None):
            data["date"] = datetime.fromisoformat(data["date"]).strftime("%Y-%m-%d %H:%M:%S")

        return data
    except BaseException:
        print(format_exc(), flush=True)
        return {"date": None, "files": [], "error": format_exc()}


def backup(**kwargs):
    pass
