from os import getenv
from time import sleep
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, PlainTextResponse


app = FastAPI()
asked_auth = False
CONTENT = """<html>
    <body>
        <h1>BunkerWeb Forever!</h1>
    </body>
</html>"""


@app.get("/admin")
async def admin():
    return PlainTextResponse(CONTENT)


@app.post("/headers")
async def headers(request: Request):
    headers = {header.split(" ")[0].lower(): header.split(" ")[1] for header in getenv("REVERSE_PROXY_HEADERS", "").split(";") if header}

    keepalive = getenv("REVERSE_PROXY_KEEPALIVE", "no") == "yes" or getenv("REVERSE_PROXY_WS", "no") == "yes"
    request_headers = request.headers
    http_version = request.scope.get("http_version")

    custom_host = getenv("REVERSE_PROXY_CUSTOM_HOST", "")
    if custom_host:
        headers["host"] = custom_host

    print(f"ℹ️ Headers received: {request_headers}", flush=True)

    if keepalive and http_version != "1.1":
        message = f"❌ The HTTP version is not 1.1 ({http_version})"
        print(message, flush=True)
        return JSONResponse({"error": message}, status_code=505)
    if not keepalive and http_version == "1.1":
        message = "❌ The HTTP version is 1.1 but the keep-alive is disabled"
        print(message, flush=True)
        return JSONResponse({"error": message}, status_code=426)

    print(f"ℹ️ Headers to check: {headers}", flush=True)
    found = 0
    for name, value in request_headers.items():
        if name in headers:
            found += 1
            if value != headers[name]:
                message = f"❌ The header {name} has the wrong value ({value} instead of {headers[name]})"
                print(message, flush=True)
                return JSONResponse({"error": message}, status_code=400)
    if found != len(headers):
        message = "❌ Some headers are missing"
        print(message, flush=True)
        return JSONResponse({"error": message}, status_code=412)
    return JSONResponse({"error": ""})


@app.get("/auth")
async def auth():
    global asked_auth
    asked_auth = True
    return PlainTextResponse(
        """<html>
    <body>
        <h1>This is the authentication page</h1>
    </body>
</html>"""
    )


@app.get("/bad-auth")
async def bad_auth():
    global asked_auth
    if asked_auth:
        return PlainTextResponse(
            """<html>
    <body>
        <h1>This is the login page</h1>
    </body>
</html>"""
        )

    asked_auth = True
    return PlainTextResponse("Unauthorized", status_code=401)


@app.get("/check-auth")
async def check_auth():
    return JSONResponse({"asked_auth": asked_auth})


@app.get("/slow")
async def slow():
    sleep(8)
    return PlainTextResponse(CONTENT)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("BunkerWeb Forever!")
    await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
