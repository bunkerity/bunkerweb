from datetime import datetime
from json import loads


def pre_render(app, *args, **kwargs):
    try:
        data = loads(app.config["DB"].get_job_cache_file("backup-data", "backup.json") or "{}")

        if data.get("date", None):
            data["date"] = datetime.fromisoformat(data["date"]).strftime("%Y-%m-%d %H:%M:%S")

        return data
    except:
        return {"date": None, "files": []}


def backup(**kwargs):
    pass
