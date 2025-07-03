from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


app = FastAPI()
instance_id = None
report_num = 0


@app.get("/ping")
async def ping(_: Request):
    return JSONResponse(status_code=200, content={"result": "ok", "data": "pong"})


@app.post("/register")
async def register(_: Request):
    global instance_id
    instance_id = str(uuid4())
    return JSONResponse(status_code=200, content={"result": "ok", "data": instance_id})


@app.post("/report")
async def report(_: Request):
    global report_num
    report_num += 1
    return JSONResponse(status_code=200, content={"result": "ok", "data": "Report acknowledged."})


@app.get("/db")
async def db(_: Request):
    return JSONResponse(status_code=200, content={"result": "ok", "data": []})


@app.get("/instance_id")
async def get_instance_id(_: Request):
    return JSONResponse(status_code=200, content={"result": "ok", "data": instance_id})


@app.get("/report_num")
async def get_report_num(_: Request):
    return JSONResponse(status_code=200, content={"result": "ok", "data": report_num})


@app.get("/reset")
async def reset(_: Request):
    global instance_id, report_num
    instance_id = None
    report_num = 0
    return JSONResponse(status_code=200, content={"result": "ok", "data": "Reset done."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
