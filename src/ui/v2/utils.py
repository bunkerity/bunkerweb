import requests
import json

def set_res(req, method, message = ""):

    print(req)
    print(method)
    data = req.text

    if type(json.loads(req.text)) is dict :
        req_JSON = json.loads(req.text)
        if "message" in req_JSON and "data" in req_JSON.get('message') :
            req_JSON_Nested = req_JSON["message"]["data"]
        if "message" in req_JSON and not "data" in req_JSON.get('message') :
            req_JSON_Nested = req_JSON["message"]
    
    return {
        "type" : "success" if req.status_code == requests.codes.ok else "error",
        "status" : str(req.status_code),
        "message" : message,
        "data": data
    }

def exception_res(status_code, path, detail):
    return {"type": "error", "status": status_code, "message": f"{path} {detail}", "data": "{}"}
