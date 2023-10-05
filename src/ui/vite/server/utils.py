import requests
import json

def set_res(req, method, message = ""):

    print(req.text)
    data = req.text

    if type(json.loads(req.text)) is dict and "message" in json.loads(req.text).keys() and "data" in json.loads(req.text)["message"].keys():
        data = json.dumps(json.loads(req.text)["message"]["data"])
    
    return {
        "type" : "success" if req.status_code == requests.codes.ok else "error",
        "status" : str(req.status_code),
        "message" : message,
        "data": data
    }

def exception_res(status_code, path, detail):
    return {"type": "error", "status": status_code, "message": f"{path} {detail}", "data": "{}"}
