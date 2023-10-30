from contextlib import suppress
from os import getenv
from requests import get
from requests.exceptions import RequestException
from time import sleep
from traceback import format_exc

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

    use_whitelist = getenv("USE_WHITELIST", "yes") == "yes"
    _global = getenv("GLOBAL", "0") == "1"

    whitelist_ip = getenv("WHITELIST_IP", "")
    whitelist_ip_urls = getenv("WHITELIST_IP_URLS", "")
    whitelist_rdns_global = getenv("WHITELIST_RDNS_GLOBAL", "yes") == "yes"
    whitelist_rdns = getenv("WHITELIST_RDNS", "")
    whitelist_rdns_urls = getenv("WHITELIST_RDNS_URLS", "")
    whitelist_asn = getenv("WHITELIST_ASN", "")
    whitelist_asn_urls = getenv("WHITELIST_ASN_URLS", "")
    whitelist_user_agent = getenv("WHITELIST_USER_AGENT", "")
    whitelist_user_agent_urls = getenv("WHITELIST_USER_AGENT_URLS", "")
    whitelist_uri = getenv("WHITELIST_URI", "")
    whitelist_uri_urls = getenv("WHITELIST_URI_URLS", "")

    print("ℹ️ Sending a request to http://www.example.com ...", flush=True)
    status_code = get(
        "http://www.example.com",
        headers={"Host": "www.example.com"} | ({"X-Forwarded-For": "1.0.0.3"} if getenv("TEST_TYPE", "docker") == "linux" and _global else {}),
    ).status_code

    print(f"ℹ️ Status code: {status_code}", flush=True)

    if status_code == 403:
        if (whitelist_ip or whitelist_ip_urls) and not _global:
            print("❌ Request was rejected, even though IP is supposed to be in the whitelist, exiting ...")
            exit(1)
        elif (whitelist_rdns or whitelist_rdns_urls) and not whitelist_rdns_global and not _global:
            print("❌ Request was rejected, even though RDNS is supposed to be in the whitelist, exiting ...")
            exit(1)
        elif (whitelist_asn or whitelist_asn_urls) and _global:
            print("❌ Request was rejected, even though ASN is supposed to be in the whitelist, exiting ...")
            exit(1)
        elif whitelist_user_agent or whitelist_user_agent_urls:
            print(
                "ℹ️ Sending a request to http://www.example.com with User-Agent BunkerBot ...",
                flush=True,
            )
            status_code = get(
                "http://www.example.com",
                headers={"Host": "www.example.com", "User-Agent": "BunkerBot"},
            ).status_code

            print(f"ℹ️ Status code: {status_code}", flush=True)

            if status_code == 403:
                print("❌ Request was rejected, even though User Agent is supposed to be in the whitelist ...")
                exit(1)

            print("✅ Request was not rejected, User Agent is in the whitelist ...")
        elif whitelist_uri or whitelist_uri_urls:
            print(
                "ℹ️ Sending a request to http://www.example.com/admin ...",
                flush=True,
            )
            status_code = get("http://www.example.com/admin", headers={"Host": "www.example.com"}).status_code

            print(f"ℹ️ Status code: {status_code}", flush=True)

            if status_code == 403:
                print("❌ Request was rejected, even though URI is supposed to be in the whitelist ...")
                exit(1)

            print("✅ Request was not rejected, URI is in the whitelist ...")
    else:
        if (whitelist_ip or whitelist_ip_urls) and _global:
            print("❌ Request was not rejected, but IP is not in the whitelist, exiting ...")
            exit(1)
        elif (whitelist_rdns or whitelist_rdns_urls) and _global:
            print("❌ Request was not rejected, but RDNS is not in the whitelist, exiting ...")
            exit(1)
        elif (whitelist_asn or whitelist_asn_urls) and not _global:
            print("❌ Request was rejected, but ASN is not in the whitelist, exiting ...")
            exit(1)
        elif whitelist_user_agent or whitelist_user_agent_urls:
            print("❌ Request was rejected, but User Agent is not in the whitelist ...")
            exit(1)
        elif whitelist_uri or whitelist_uri_urls:
            print("❌ Request was rejected, but URI is not in the whitelist ...")
            exit(1)

    print("✅ Whitelist is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
