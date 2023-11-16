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

    use_greylist = getenv("USE_GREYLIST", "yes") == "yes"
    _global = getenv("GLOBAL", "0") == "1"

    greylist_ip = getenv("GREYLIST_IP", "")
    greylist_ip_urls = getenv("GREYLIST_IP_URLS", "")
    greylist_rdns_global = getenv("GREYLIST_RDNS_GLOBAL", "yes") == "yes"
    greylist_rdns = getenv("GREYLIST_RDNS", "")
    greylist_rdns_urls = getenv("GREYLIST_RDNS_URLS", "")
    greylist_asn = getenv("GREYLIST_ASN", "")
    greylist_asn_urls = getenv("GREYLIST_ASN_URLS", "")
    greylist_user_agent = getenv("GREYLIST_USER_AGENT", "")
    greylist_user_agent_urls = getenv("GREYLIST_USER_AGENT_URLS", "")
    greylist_uri = getenv("GREYLIST_URI", "")
    greylist_uri_urls = getenv("GREYLIST_URI_URLS", "")

    print("ℹ️ Sending a request to http://www.example.com ...", flush=True)
    status_code = get(
        "http://www.example.com",
        headers={"Host": "www.example.com"} | ({"X-Forwarded-For": "1.0.0.3"} if getenv("TEST_TYPE", "docker") == "linux" and _global else {}),
    ).status_code

    print(f"ℹ️ Status code: {status_code}", flush=True)

    sleep(2)

    if status_code == 403:
        if not use_greylist:
            print("❌ Request was rejected, even though greylist is supposed to be disabled, exiting ...")
            exit(1)
        elif (greylist_ip or greylist_ip_urls) and not _global:
            print("❌ Request was rejected, even though IP is supposed to be in the greylist, exiting ...")
            exit(1)
        elif (greylist_rdns or greylist_rdns_urls) and not greylist_rdns_global and not _global:
            print("❌ Request was rejected, even though RDNS is supposed to be in the greylist, exiting ...")
            exit(1)
        elif (greylist_asn or greylist_asn_urls) and _global:
            print("❌ Request was rejected, even though ASN is supposed to be in the greylist, exiting ...")
            exit(1)
        elif greylist_user_agent or greylist_user_agent_urls:
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
                print("❌ Request was rejected, even though User Agent is supposed to be in the greylist ...")
                exit(1)

            sleep(2)

            print("✅ Request was not rejected, User Agent is in the greylist ...")
            print(
                "ℹ️ Sending a request to http://www.example.com/?id=/etc/passwd with User-Agent BunkerBot ...",
                flush=True,
            )

            status_code = get(
                "http://www.example.com/?id=/etc/passwd",
                headers={"Host": "www.example.com", "User-Agent": "BunkerBot"},
            ).status_code

            print(f"ℹ️ Status code: {status_code}", flush=True)

            if status_code != 403:
                print("❌ Request was not rejected, exiting ...", flush=True)
                exit(1)
        elif greylist_uri or greylist_uri_urls:
            print(
                "ℹ️ Sending a request to http://www.example.com/admin ...",
                flush=True,
            )
            status_code = get("http://www.example.com/admin", headers={"Host": "www.example.com"}).status_code

            print(f"ℹ️ Status code: {status_code}", flush=True)

            if status_code == 403:
                print("❌ Request was rejected, even though URI is supposed to be in the greylist ...")
                exit(1)

            sleep(2)

            print("✅ Request was not rejected, URI is in the greylist ...")
            print(
                "ℹ️ Sending a request to http://www.example.com/admin/?id=/etc/passwd ...",
                flush=True,
            )

            status_code = get(
                "http://www.example.com/admin/?id=/etc/passwd",
                headers={"Host": "www.example.com"},
            ).status_code

            print(f"ℹ️ Status code: {status_code}", flush=True)

            if status_code != 403:
                print("❌ Request was not rejected, exiting ...", flush=True)
                exit(1)
    else:
        if (greylist_ip or greylist_ip_urls) and _global:
            print("❌ Request was not rejected, but IP is not in the greylist, exiting ...")
            exit(1)
        elif (greylist_rdns or greylist_rdns_urls) and _global:
            print("❌ Request was not rejected, but RDNS is not in the greylist, exiting ...")
            exit(1)
        elif (greylist_asn or greylist_asn_urls) and not _global:
            print("❌ Request was rejected, but ASN is not in the greylist, exiting ...")
            exit(1)
        elif greylist_user_agent or greylist_user_agent_urls:
            print("❌ Request was rejected, but User Agent is not in the greylist ...")
            exit(1)
        elif greylist_uri or greylist_uri_urls:
            print("❌ Request was rejected, but URI is not in the greylist ...")
            exit(1)

        print(
            "ℹ️ Sending a request to http://www.example.com/?id=/etc/passwd ...",
            flush=True,
        )

        status_code = get(
            "http://www.example.com/?id=/etc/passwd",
            headers={"Host": "www.example.com"},
        ).status_code

        print(f"ℹ️ Status code: {status_code}", flush=True)

        if status_code != 403:
            print("❌ Request was not rejected, exiting ...", flush=True)
            exit(1)

    print("✅ Greylist is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
