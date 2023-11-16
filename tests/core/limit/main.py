from asyncio import Semaphore, gather, run
from httpx import AsyncClient, Client
from os import getenv
from time import time
from traceback import format_exc
from contextlib import suppress
from requests.exceptions import RequestException
from time import sleep
from requests import get

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get("http://www.example.com/ready", headers={"Host": "www.example.com"})
            status_code = resp.status_code
            text = resp.text

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400 or status_code == 403 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    use_limit_request = getenv("USE_LIMIT_REQ", "yes") == "yes"
    limit_req_url = getenv("LIMIT_REQ_URL", "/")
    limit_req_rate = getenv("LIMIT_REQ_RATE", "2r/s")
    limit_req_url_1 = getenv("LIMIT_REQ_URL_1")
    limit_req_rate_1 = getenv("LIMIT_REQ_RATE_1")

    use_limit_conn = getenv("USE_LIMIT_CONN", "yes") == "yes"
    limit_conn_http1 = getenv("LIMIT_CONN_MAX_HTTP1", "1")

    if not limit_conn_http1.isdigit():
        print("❌ LIMIT_CONN_MAX_HTTP1 is not a number, exiting ...", flush=True)
        exit(1)

    limit_conn_http1 = int(limit_conn_http1)

    async def fetch(domain, semaphore):
        async with semaphore:
            async with AsyncClient() as client:
                return await client.get(f"http://{domain}", headers={"Host": domain})

    async def main(limit) -> list:
        domains = ["www.example.com"] * limit
        semaphore = Semaphore(limit)
        tasks = [fetch(domain, semaphore) for domain in domains]
        return await gather(*tasks)

    if use_limit_conn:
        print(
            f"ℹ️ Making requests to the service with HTTP/1.1 with the limit_conn_http1 directive set to {limit_conn_http1} ...",
        )

        responses = run(main(5))

        if any(response.status_code >= 500 for response in responses):
            print("❌ An error occurred with the server, exiting ...", flush=True)
            exit(1)
        elif not any(response.status_code == 429 for response in responses) and limit_conn_http1 == 1:
            print(
                f"❌ The limit_conn for HTTP1 directive is not working correctly, the limit was set to {limit_conn_http1} and the limit was not reached with 5 simultaneous connections, exiting ...",
                flush=True,
            )
            exit(1)
        elif any(response.status_code == 429 for response in responses) and limit_conn_http1 > 1:
            print(
                f"❌ The limit_conn for HTTP1 directive is not working correctly, the limit was set to {limit_conn_http1} and the limit was reached with 5 simultaneous connections, exiting ...",
                flush=True,
            )
            exit(1)

        print(
            f"✅ The limit_conn for HTTP1 directive is working correctly, the limit was set to {limit_conn_http1} and the limit was reached with 5 simultaneous connections",
            flush=True,
        )
        exit(0)

    start = time()
    status_code = 200
    request_number = 0
    stopped = False

    print("ℹ️ Sending requests to the service until it reaches the limit ...", flush=True)

    while status_code != 429:
        with Client() as client:
            status_code = client.get(
                f"http://www.example.com{limit_req_url}",
                headers={"Host": "www.example.com"},
            ).status_code

        if status_code >= 500:
            print("❌ An error occurred with the server, exiting ...", flush=True)
            exit(1)

        request_number += 1

        if request_number >= 20:
            stopped = True
            break
    total = time() - start
    rate = int(limit_req_rate[:-3])

    if use_limit_request and stopped:
        print(
            f"❌ The limit_req directive is not working correctly, the limit was not reached in 20 requests in {total:.2f}s, exiting ...",
            flush=True,
        )
        exit(1)
    elif not use_limit_request and not stopped:
        print(
            f"❌ The limit_req directive is not working correctly, {request_number} requests were made in {total:.2f}s to reach the limit, exiting ...",
            flush=True,
        )
        exit(1)
    elif not use_limit_request and stopped:
        print(
            f"✅ The limit_req directive was successfully disabled, {request_number} requests were made in {total:.2f}s and the limit was not reached",
            flush=True,
        )
        exit(0)
    elif request_number != rate + 1:
        print(
            f"❌ The limit_req directive is not working correctly, {request_number} requests were made in {total:.2f}s while the limit was set to {limit_req_rate}, exiting ...",
            flush=True,
        )
        exit(1)

    print(
        f"✅ The limit_req directive is working correctly, {request_number} requests were made in {total:.2f}s to reach the limit",
        flush=True,
    )

    if limit_req_url_1:
        start = time()
        status_code = 200
        request_number = 0
        stopped = False

        print(
            f"ℹ️ Sending requests to the url {limit_req_url_1} until it reaches the limit ...",
            flush=True,
        )

        while status_code != 429:
            with Client() as client:
                status_code = client.get(
                    f"http://www.example.com{limit_req_url_1}",
                    headers={"Host": "www.example.com"},
                ).status_code

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            request_number += 1

            if request_number >= 20:
                stopped = True
                break
        total = time() - start
        rate = int(limit_req_rate_1[:-3])

        if request_number != rate + 1:
            if stopped:
                print(
                    f"❌ The limit_req_1 directive is not working correctly, the limit was not reached in 20 requests in {total:.2f}s, exiting ...",
                    flush=True,
                )
                exit(1)

            print(
                f"❌ The limit_req_1 directive is not working correctly, {request_number} requests were made in {total:.2f}s while the limit was set to {limit_req_rate_1}, exiting ...",
                flush=True,
            )
            exit(1)

        print(
            f"✅ The limit_req_1 directive is working correctly, {request_number} requests were made in {total:.2f}s to reach the limit",
            flush=True,
        )
        exit(0)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
