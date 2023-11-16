from contextlib import suppress
from os import getenv
from requests import RequestException, get
from traceback import format_exc
from time import sleep


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

            ready = status_code < 400 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    use_client_cache = getenv("USE_CLIENT_CACHE", "no") == "yes"
    default_cache_extensions = (
        getenv(
            "CLIENT_CACHE_EXTENSIONS",
            "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2",
        )
        == "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"
    )
    client_cache_etag = getenv("CLIENT_CACHE_ETAG", "yes") == "yes"
    client_cache_control = getenv("CLIENT_CACHE_CONTROL", "public, max-age=15552000")

    print(
        "ℹ️ Sending a request to http://www.example.com/image.png ...",
        flush=True,
    )

    response = get("http://www.example.com/image.png", headers={"Host": "www.example.com"})
    response.raise_for_status()

    if not use_client_cache:
        if "Cache-Control" in response.headers:
            print(f"❌ Cache-Control header is present even if Client cache is deactivated, exiting ...\nheaders: {response.headers}")
            exit(1)
    else:
        if "Cache-Control" not in response.headers and default_cache_extensions:
            print(f"❌ Cache-Control header is not present even if Client cache is activated, exiting ...\nheaders: {response.headers}")
            exit(1)
        elif not default_cache_extensions and "Cache-Control" in response.headers:
            print(
                f"❌ Cache-Control header is present even if the png extension is not in the list of extensions, exiting ...\nheaders: {response.headers}",
                flush=True,
            )
        elif not client_cache_etag and "ETag" in response.headers:
            print(f"❌ ETag header is present even if Client cache ETag is deactivated, exiting ...\nheaders: {response.headers}")
            exit(1)
        elif default_cache_extensions and client_cache_control != response.headers.get("Cache-Control"):
            print(f"❌ Cache-Control header is not equal to the expected value, exiting ...\nheaders: {response.headers}")
            exit(1)

    print("✅ Client cache is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
