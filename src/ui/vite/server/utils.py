import requests
import json

def set_res(req, method, message = ""):
    return {
        "type" : "success" if req.status_code == requests.codes.ok else "error",
        "status" : str(req.status_code),
        "message" : message,
        "data": req.text if method.upper() == "GET" else "{}"
    }

def exception_res(status_code, path, detail):
    return {
        "type" : "error",
        "status" : status_code,
        "message" : f'{path} {detail}',
        "data": "{}"
    }