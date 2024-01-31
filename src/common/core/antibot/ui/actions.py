import json


def antibot():
    return json.dumps({"message": "ok", "data": {"info": "test", "count": 24}})
