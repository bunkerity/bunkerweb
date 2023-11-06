# -*- coding: utf-8 -*-
import requests, traceback, json  # noqa: E401
from starlette.exceptions import HTTPException as StarletteHTTPException
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

API = UiConfig.CORE_ADDR

def get_core_format_res(path, method, data, message, retry = 1):
    # Retry limit
    if retry == 5 :
            raise StarletteHTTPException(status_code=500, detail="Max retry to core for same request exceeded")

    req = None
    # Try request core
    try :       
        req = req_core(path, method)
        # Case 503, retry request 
        if req.status_code == 503 :
            return get_core_format_res(path, method, data, message, retry + 1)
        # Case error
        if req == "error" :
            raise StarletteHTTPException(status_code=500, detail="Impossible to connect to CORE API")
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

        return {"type": "success" if req.status_code.startswith('2') else "error", "status": str(req.status_code), "message": message, "data": data}
    # Case impossible to format
    except:
        print(traceback.format_exc())


def req_core(path, method):
    # Request core api and store response
    req = None
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
        
        return req
    # Case no response from core
    except:
        return 'error'

def exception_res(status_code, path, detail):
    return {"type": "error", "status": status_code, "message": f"{path} {detail}", "data": "{}"}


def check_core():
    try :
        req = requests.get(f"{API}/ping")

        if req.status_code.startswith("2"):
            return True

        return False
    except:
        return False