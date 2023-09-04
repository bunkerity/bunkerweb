import requests

def set_res_from_req(req, method, message = ""):
        return {
        "type" : "success" if req.status_code == requests.codes.ok else "error",
        "status" : str(req.status_code),
        "message" : message,
        "data": req.text if method.upper() == "GET" else {}
    }
