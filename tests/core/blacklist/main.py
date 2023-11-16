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

    GLOBAL = getenv("GLOBAL", "no") == "yes"
    use_blacklist = getenv("USE_BLACKLIST", "yes") == "yes"

    blacklist_ip = getenv("BLACKLIST_IP", "")
    blacklist_ip_urls = getenv("BLACKLIST_IP_URLS", "")
    blacklist_rdns_global = getenv("BLACKLIST_RDNS_GLOBAL", "yes") == "yes"
    blacklist_rdns = getenv("BLACKLIST_RDNS", "")
    blacklist_rdns_urls = getenv("BLACKLIST_RDNS_URLS", "")
    blacklist_asn = getenv("BLACKLIST_ASN", "")
    blacklist_asn_urls = getenv("BLACKLIST_ASN_URLS", "")
    blacklist_user_agent = getenv("BLACKLIST_USER_AGENT", "")
    blacklist_user_agent_urls = getenv("BLACKLIST_USER_AGENT_URLS", "")
    blacklist_uri = getenv("BLACKLIST_URI", "")
    blacklist_uri_urls = getenv("BLACKLIST_URI_URLS", "")

    blacklist_ignore_ip = getenv("BLACKLIST_IGNORE_IP", "")
    blacklist_ignore_ip_urls = getenv("BLACKLIST_IGNORE_IP_URLS", "")
    blacklist_ignore_rdns = getenv("BLACKLIST_IGNORE_RDNS", "")
    blacklist_ignore_rdns_urls = getenv("BLACKLIST_IGNORE_RDNS_URLS", "")
    blacklist_ignore_asn = getenv("BLACKLIST_IGNORE_ASN", "")
    blacklist_ignore_asn_urls = getenv("BLACKLIST_IGNORE_ASN_URLS", "")
    blacklist_ignore_user_agent = getenv("BLACKLIST_IGNORE_USER_AGENT", "")
    blacklist_ignore_user_agent_urls = getenv("BLACKLIST_IGNORE_USER_AGENT_URLS", "")
    blacklist_ignore_uri = getenv("BLACKLIST_IGNORE_URI", "")
    blacklist_ignore_uri_urls = getenv("BLACKLIST_IGNORE_URI_URLS", "")

    print(
        "ℹ️ Sending a request to http://www.example.com/admin with User-Agent: BunkerBot ...",
        flush=True,
    )

    status_code = get(
        "http://www.example.com/admin",
        headers={"Host": "www.example.com", "User-Agent": "BunkerBot"} | ({"X-Forwarded-For": "1.0.0.3"} if GLOBAL else {}),
    ).status_code

    if status_code == 403:
        if not use_blacklist:
            print("❌ The request was rejected, but the blacklist is disabled, exiting ...")
            exit(1)
        elif blacklist_rdns_global and (blacklist_rdns != "" or blacklist_rdns_urls != ""):
            print(
                "❌ Blacklist's RDNS global didn't work as expected, exiting ...",
            )
            exit(1)
        elif blacklist_ignore_ip != "":
            print("❌ Blacklist's ignore IP didn't work as expected, exiting ...")
            exit(1)
        elif blacklist_ignore_ip_urls != "":
            print(
                "❌ Blacklist's ignore IP urls didn't work as expected, exiting ...",
                flush=True,
            )
            exit(1)
        elif blacklist_ignore_rdns != "":
            print("❌ Blacklist's ignore RDNS didn't work as expected, exiting ...")
            exit(1)
        elif blacklist_ignore_rdns_urls != "":
            print(
                "❌ Blacklist's ignore RDNS urls didn't work as expected, exiting ...",
                flush=True,
            )
            exit(1)
        elif blacklist_ignore_asn != "":
            print("❌ Blacklist's ignore ASN didn't work as expected, exiting ...")
            exit(1)
        elif blacklist_ignore_asn_urls != "":
            print(
                "❌ Blacklist's ignore ASN urls didn't work as expected, exiting ...",
                flush=True,
            )
            exit(1)
        elif blacklist_ignore_user_agent != "":
            print(
                "❌ Blacklist's ignore user agent didn't work as expected, exiting ...",
                flush=True,
            )
            exit(1)
        elif blacklist_ignore_user_agent_urls != "":
            print(
                "❌ Blacklist's ignore user agent urls didn't work as expected, exiting ...",
                flush=True,
            )
            exit(1)
        elif blacklist_ignore_uri != "":
            print("❌ Blacklist's ignore URI didn't work as expected, exiting ...")
            exit(1)
        elif blacklist_ignore_uri_urls != "":
            print(
                "❌ Blacklist's ignore URI urls didn't work as expected, exiting ...",
                flush=True,
            )
            exit(1)
    elif blacklist_ip != "" and not any([blacklist_ignore_ip, blacklist_ignore_ip_urls, not use_blacklist]):
        print("❌ Blacklist's IP didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_ip_urls != "":
        print("❌ Blacklist's IP urls didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_rdns != "" and not any(
        [
            blacklist_ignore_rdns,
            blacklist_ignore_rdns_urls,
            blacklist_rdns_global,
        ]
    ):
        print("❌ Blacklist's RDNS didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_rdns_urls != "" and blacklist_rdns_global:
        print("❌ Blacklist's RDNS urls didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_asn != "" and not any([blacklist_ignore_asn, blacklist_ignore_asn_urls]):
        print("❌ Blacklist's ASN didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_asn_urls != "":
        print("❌ Blacklist's ASN urls didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_user_agent != "" and not any([blacklist_ignore_user_agent, blacklist_ignore_user_agent_urls]):
        print("❌ Blacklist's User Agent didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_user_agent_urls != "":
        print(
            "❌ Blacklist's User Agent urls didn't work as expected, exiting ...",
            flush=True,
        )
        exit(1)
    elif blacklist_uri != "" and not any([blacklist_ignore_uri, blacklist_ignore_uri_urls]):
        print("❌ Blacklist's URI didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif blacklist_uri_urls != "":
        print("❌ Blacklist's URI urls didn't work as expected, exiting ...", flush=True)
        exit(1)
    elif use_blacklist and not any(
        [
            blacklist_ip,
            blacklist_ip_urls,
            blacklist_rdns,
            blacklist_rdns_urls,
            blacklist_asn,
            blacklist_asn_urls,
            blacklist_user_agent,
            blacklist_user_agent_urls,
            blacklist_uri,
            blacklist_uri_urls,
            blacklist_ignore_ip,
            blacklist_ignore_ip_urls,
            blacklist_ignore_rdns,
            blacklist_ignore_rdns_urls,
            blacklist_ignore_asn,
            blacklist_ignore_asn_urls,
            blacklist_ignore_user_agent,
            blacklist_ignore_user_agent_urls,
            blacklist_ignore_uri,
            blacklist_ignore_uri_urls,
        ]
    ):
        print("❌ Blacklist is disabled, it shouldn't be ...", flush=True)
        exit(1)

    print("✅ Blacklist is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
