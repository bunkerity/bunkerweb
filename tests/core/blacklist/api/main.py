from os import getenv
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


app = FastAPI()


@app.get("/ip")
async def ip():
    return PlainTextResponse("192.168.0.3\n10.0.0.0/8\n127.0.0.0/24")


@app.get("/rdns")
async def rdns():
    return PlainTextResponse(".example.com\n.example.org\n.bw-services")


@app.get("/asn")
async def asn():
    return PlainTextResponse(f"1234\n{getenv('AS_NUMBER', '13335')}\n5678")


@app.get("/user_agent")
async def user_agent():
    return PlainTextResponse("BunkerBot\nCensysInspect\nShodanInspect\nZmEu\nmasscan")


@app.get("/uri")
async def uri():
    return PlainTextResponse("/admin\n/login")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
