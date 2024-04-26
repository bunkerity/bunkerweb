from fastapi import FastAPI
from multiprocessing import Process
from os import getenv
from redis import Redis, Sentinel
from requests import get
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from time import sleep
from traceback import format_exc
from contextlib import suppress
from requests.exceptions import RequestException

from uvicorn import run

fastapi_proc = None

ip_to_check = "1.0.0.253" if getenv("TEST_TYPE", "docker") == "docker" else "127.0.0.1"


def get_all_redis_key_values(redis_client: Redis):
    keys = redis_client.keys()
    key_values = {}

    for key in keys:
        key_values[key.decode()] = redis_client.get(key).decode()

    return key_values


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

    redis_host = getenv("REDIS_HOST", "127.0.0.1")

    if not redis_host:
        print("❌ Redis host is not set, exiting ...", flush=True)
        exit(1)

    redis_port = getenv("REDIS_PORT", "6379")

    if not redis_port.isdigit():
        print("❌ Redis port doesn't seem to be a number, exiting ...", flush=True)
        exit(1)

    redis_port = int(redis_port)

    redis_db = getenv("REDIS_DATABASE", "0")

    if not redis_db.isdigit():
        print("❌ Redis database doesn't seem to be a number, exiting ...", flush=True)
        exit(1)

    redis_db = int(redis_db)

    redis_ssl = getenv("REDIS_SSL", "no") == "yes"
    sentinel_hosts = getenv("REDIS_SENTINEL_HOSTS", [])

    if isinstance(sentinel_hosts, str):
        sentinel_hosts = [host.split(":") if ":" in host else host for host in sentinel_hosts.split(" ") if host]

    if sentinel_hosts:
        sentinel_username = getenv("REDIS_SENTINEL_USERNAME", None) or None
        sentinel_password = getenv("REDIS_SENTINEL_PASSWORD", None) or None
        sentinel_master = getenv("REDIS_SENTINEL_MASTER", "bw-master")

        print(
            f"ℹ️ Trying to connect to Redis Sentinel with the following parameters:\nhosts: {sentinel_hosts}\nmaster: {sentinel_master}\nssl: {redis_ssl}\nusername: {sentinel_username}\npassword: {sentinel_password}",
            flush=True,
        )
        sentinel = Sentinel(sentinel_hosts, username=sentinel_username, password=sentinel_password, sentinel_kwargs=dict(ssl=redis_ssl), socket_timeout=1)  # type: ignore

        print(
            f"ℹ️ Trying to get a Redis Sentinel slave for master {sentinel_master} with the following parameters:\n"
            + f"host: {redis_host}\nport: {redis_port}\ndb: {redis_db}\nssl: {redis_ssl}\nusername: {getenv('REDIS_USERNAME', None) or None}\npassword: {getenv('REDIS_PASSWORD', None) or None}",
            flush=True,
        )
        redis_client = sentinel.slave_for(
            sentinel_master,
            db=redis_db,
            username=getenv("REDIS_USERNAME", None) or None,
            password=getenv("REDIS_PASSWORD", None) or None,
        )
    else:
        print(
            "ℹ️ Trying to connect to Redis with the following parameters:\n"
            + f"host: {redis_host}\nport: {redis_port}\ndb: {redis_db}\nssl: {redis_ssl}\nusername: {getenv('REDIS_USERNAME', None) or None}\npassword: {getenv('REDIS_PASSWORD', None) or None}",
            flush=True,
        )

        redis_client = Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            username=getenv("REDIS_USERNAME", None) or None,
            password=getenv("REDIS_PASSWORD", None) or None,
            ssl=redis_ssl,
            socket_timeout=1,
            ssl_cert_reqs="none",
        )

    if not redis_client.ping():
        print("❌ Redis is not reachable, exiting ...", flush=True)
        exit(1)

    use_reverse_scan = getenv("USE_REVERSE_SCAN", "no") == "yes"

    if use_reverse_scan:
        if ip_to_check == "1.0.0.253":
            print("ℹ️ Testing Reverse Scan, starting FastAPI ...", flush=True)
            app = FastAPI()
            fastapi_proc = Process(target=run, args=(app,), kwargs=dict(host="0.0.0.0", port=8080))
            fastapi_proc.start()

            sleep(2)

            print(
                "ℹ️ FastAPI started, sending a request to http://www.example.com ...",
                flush=True,
            )

        response = get(
            "http://www.example.com",
            headers={"Host": "www.example.com"},
        )

        if response.status_code != 403:
            response.raise_for_status()

            print("❌ The request was not blocked, exiting ...", flush=True)
            exit(1)

        sleep(0.5)

        print("ℹ️ The request was blocked, checking Redis ...", flush=True)

        port_to_check = "8080" if ip_to_check == "1.0.0.253" else "80"

        key_value = redis_client.get(f"plugin_reverse_scan_{ip_to_check}:{port_to_check}")

        if key_value is None:
            print(
                f'❌ The Reverse Scan key ("plugin_reverse_scan_{ip_to_check}:{port_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
                flush=True,
            )
            exit(1)
        elif key_value != b"open":
            print(
                f'❌ The Reverse Scan key ("plugin_reverse_scan_{ip_to_check}:{port_to_check}") was found, but the value is not "open" ({key_value.decode()}), exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
                flush=True,
            )
            exit(1)

        print(
            f"✅ The Reverse Scan key was found, the value is {key_value.decode()}",
            flush=True,
        )

        exit(0)

    use_antibot = getenv("USE_ANTIBOT", "no") != "no"

    if use_antibot:
        print("ℹ️ Testing Antibot ...", flush=True)

        firefox_options = Options()
        firefox_options.add_argument("--headless")

        print("ℹ️ Starting Firefox ...", flush=True)
        with webdriver.Firefox(options=firefox_options) as driver:
            driver.delete_all_cookies()
            driver.maximize_window()

            print("ℹ️ Navigating to http://www.example.com ...", flush=True)
            driver.get("http://www.example.com")

        sleep(0.5)

        print("ℹ️ Checking Redis ...", flush=True)

        keys = redis_client.keys("sessions_:test:*")

        if not keys:
            print(
                f"❌ No Antibot keys were found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}",
                flush=True,
            )
            exit(1)

        key_value = redis_client.get(keys[0])

        if key_value is None:
            print(
                f"❌ The Antibot key ({keys[0].decode()}) was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}",
                flush=True,
            )
            exit(1)

        print(
            f"✅ The Antibot key was found, the value is {key_value.decode()}",
            flush=True,
        )

        exit(0)

    print(
        "ℹ️ Sending a request to http://www.example.com/?id=/etc/passwd ...",
        flush=True,
    )

    response = get(
        "http://www.example.com/?id=/etc/passwd",
        headers={"Host": "www.example.com"},
    )

    if response.status_code != 403:
        response.raise_for_status()

        print("❌ The request was not blocked, exiting ...", flush=True)
        exit(1)

    sleep(0.5)

    print("ℹ️ The request was blocked, checking Redis ...", flush=True)

    key_value = redis_client.get(f"plugin_bad_behavior_{ip_to_check}")

    if not key_value:
        print(
            f'❌ The Bad Behavior key ("plugin_bad_behavior_{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
            flush=True,
        )
        exit(1)

    print(
        f"✅ The Bad Behavior key was found, the value is {key_value.decode()}",
        flush=True,
    )

    print(
        "ℹ️ Sending another request to http://www.example.com/?id=/etc/passwd ...",
        flush=True,
    )

    response = get(
        "http://www.example.com/?id=/etc/passwd",
        headers={"Host": "www.example.com"},
    )

    if response.status_code != 403:
        response.raise_for_status()

        print("❌ The request was not blocked, exiting ...", flush=True)
        exit(1)

    sleep(0.5)

    second_key_value = redis_client.get(f"plugin_bad_behavior_{ip_to_check}")

    if not second_key_value:
        print(
            f'❌ The Bad Behavior key ("plugin_bad_behavior_{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
            flush=True,
        )
        exit(1)

    if second_key_value <= key_value:
        print(
            f'❌ The Bad Behavior key ("plugin_bad_behavior_{ip_to_check}") was not incremented, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
            flush=True,
        )
        exit(1)

    print(
        f"✅ The Bad Behavior key was incremented, the value is {second_key_value.decode()}",
        flush=True,
    )

    print(
        "ℹ️ Sending requests to http://www.example.com until we reach the limit ...",
        flush=True,
    )
    status_code = 0

    while status_code != 429:
        response = get(
            "http://www.example.com",
            headers={"Host": "www.example.com"},
        )

        if response.status_code not in (200, 429):
            response.raise_for_status()

        status_code = response.status_code

    sleep(0.5)

    key_value = redis_client.get(f"plugin_limit_www.example.com{ip_to_check}/")

    if key_value is None:
        print(
            f'❌ The limit key ("plugin_limit_www.example.com{ip_to_check}/") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
            flush=True,
        )
        exit(1)

    print(
        f"✅ The limit key was found, the value is {key_value.decode()}",
        flush=True,
    )

    # print(
    #     "ℹ️ Checking if the country key was created and has the correct value ...",
    #     flush=True,
    # )

    # key_value = redis_client.get(f"plugin_country_www.example.com{ip_to_check}")

    # if key_value is None:
    #     print(
    #         f'❌ The country key ("plugin_country_www.example.com{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #         flush=True,
    #     )
    #     exit(1)

    # print(
    #     f"✅ The country key was found, the value is {key_value.decode()}",
    #     flush=True,
    # )

    # print(
    #     "ℹ️ Checking if the whitelist key was created and has the correct value ...",
    #     flush=True,
    # )

    # key_value = redis_client.get(f"plugin_whitelist_www.example.comip{ip_to_check}")

    # if key_value is None:
    #     print(
    #         f'❌ The whitelist key ("plugin_whitelist_www.example.comip{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #         flush=True,
    #     )
    #     exit(1)
    # if key_value != b"ok":
    #     print(
    #         f'❌ The whitelist key ("plugin_whitelist_www.example.comip{ip_to_check}") was found, but the value is not "ok" ({key_value.decode()}), exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #     )

    # print(
    #     f"✅ The whitelist key was found, the value is {key_value.decode()}",
    #     flush=True,
    # )

    # print(
    #     "ℹ️ Checking if the blacklist key was created and has the correct value ...",
    #     flush=True,
    # )

    # key_value = redis_client.get(f"plugin_blacklist_www.example.comip{ip_to_check}")

    # if key_value is None:
    #     print(
    #         f'❌ The blacklist key ("plugin_blacklist_www.example.comip{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #         flush=True,
    #     )
    #     exit(1)
    # if key_value != b"ok":
    #     print(
    #         f'❌ The blacklist key ("plugin_blacklist_www.example.comip{ip_to_check}") was found, but the value is not "ok" ({key_value.decode()}), exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #     )

    # print(
    #     f"✅ The blacklist key was found, the value is {key_value.decode()}",
    #     flush=True,
    # )

    # print(
    #     "ℹ️ Checking if the greylist key was created and has the correct value ...",
    #     flush=True,
    # )

    # key_value = redis_client.get(f"plugin_greylist_www.example.comip{ip_to_check}")

    # if key_value is None:
    #     print(
    #         f'❌ The greylist key ("plugin_greylist_www.example.comip{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #         flush=True,
    #     )
    #     exit(1)
    # if key_value != b"ip":
    #     print(
    #         f'❌ The greylist key ("plugin_greylist_www.example.comip{ip_to_check}") was found, but the value is not "ip" ({key_value.decode()}), exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #     )

    # print(
    #     f"✅ The greylist key was found, the value is {key_value.decode()}",
    #     flush=True,
    # )

    # if ip_to_check == "1.0.0.253":
    #     print(
    #         "ℹ️ Checking if the dnsbl keys were created ...",
    #         flush=True,
    #     )

    #     key_value = redis_client.get(f"plugin_dnsbl_www.example.com{ip_to_check}")

    #     if key_value is None:
    #         print(
    #             f'❌ The dnsbl key ("plugin_dnsbl_www.example.com{ip_to_check}") was not found, exiting ...\nkeys: {get_all_redis_key_values(redis_client)}',
    #             flush=True,
    #         )
    #         exit(1)

    #     print(
    #         f"✅ The dnsbl key was found, the value is {key_value.decode()}",
    #         flush=True,
    #     )
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
finally:
    if fastapi_proc:
        fastapi_proc.terminate()
