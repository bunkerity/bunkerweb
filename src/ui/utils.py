# -*- coding: utf-8 -*-
import requests, traceback, json  # noqa: E401
from starlette.exceptions import HTTPException as StarletteHTTPException


def get_core_format_res(path, method, data, message):
    req = None
    # Request core api and store response
    try:
        if method.upper() == "GET":
            req = requests.get(path)

        if method.upper() == "POST":
            req = requests.post(path, data=data)

        if method.upper() == "DELETE":
            req = requests.delete(path, data=data)

        if method.upper() == "PATCH":
            req = requests.patch(path, data=data)

        if method.upper() == "PUT":
            req = requests.put(path, data=data)
    # Case no response from core
    except:
        raise StarletteHTTPException(status_code=500, detail="Impossible to connect to CORE API")

    # Case response from core, format response for client
    try:
        data = req.text

        obj = json.loads(req.text)
        if isinstance(obj, dict):
            data = obj.get("message", obj)
            if isinstance(data, dict):
                data = data.get("data", data)

            data = json.dumps(data, skipkeys=True, allow_nan=True, indent=6)

        print(req.status_code)
        print(req.status_code == requests.codes.ok)

        return {"type": "success" if req.status_code == requests.codes.ok else "error", "status": str(req.status_code), "message": message, "data": data}
    # Case impossible to format
    except:
        print(traceback.format_exc())
        raise StarletteHTTPException(status_code=500, detail="Impossible to proceed CORE API response")


def exception_res(status_code, path, detail):
    return {"type": "error", "status": status_code, "message": f"{path} {detail}", "data": "{}"}
