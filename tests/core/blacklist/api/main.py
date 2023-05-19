from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


app = FastAPI()


@app.get("/ip")
async def ip():
    return PlainTextResponse("192.168.0.3\n10.0.0.0/8\n127.0.0.1/32")


@app.get("/rdns")
async def rdns():
    return PlainTextResponse(".example.com\n.example.org\n.bw-services")


@app.get("/asn")
async def asn():
    return PlainTextResponse("1234\n13335\n5678")


@app.get("/user_agent")
async def user_agent():
    return PlainTextResponse("BunkerBot\nCensysInspect\nShodanInspect\nZmEu\nmasscan")


@app.get("/uri")
async def uri():
    return PlainTextResponse("/admin\n/login")
