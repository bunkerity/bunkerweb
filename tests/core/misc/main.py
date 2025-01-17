from os import getenv
from contextlib import suppress
from subprocess import run
from requests import RequestException, ConnectionError, get, head, post
from socket import create_connection
from ssl import CERT_NONE, create_default_context
from time import sleep
from traceback import format_exc

try:
    ssl_generated = getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes"
    disabled_default_server = getenv("DISABLE_DEFAULT_SERVER", "no") == "yes"
    deny_http_status = getenv("DENY_HTTP_STATUS", "403")
    listen_http = getenv("LISTEN_HTTP", "yes") == "yes"

    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get(f"http{'s' if ssl_generated else ''}://www.example.com/ready", headers={"Host": "www.example.com"}, verify=False)
            status_code = resp.status_code
            text = resp.text

            if resp.status_code >= 500:
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

    error = False

    print(
        f"ℹ️ Sending a HEAD request to http://{'192.168.0.2' if getenv('TEST_TYPE', 'docker') == 'docker' else '127.0.0.1'} (default server) to test DISABLE_DEFAULT_SERVER",
        flush=True,
    )

    try:
        response = head("http://" + ("192.168.0.2" if getenv("TEST_TYPE", "docker") == "docker" else "127.0.0.1"))

        if response.status_code != 403 and disabled_default_server:
            print(
                "❌ Request didn't get rejected, even if default server is disabled, exiting ...",
                flush=True,
            )
            exit(1)
        elif response.status_code == 403:
            if not disabled_default_server:
                print(
                    "❌ Request got rejected, even if the default server is enabled, exiting ...",
                    flush=True,
                )
                exit(1)

            if deny_http_status != "403":
                print(
                    f"❌ Request got rejected, but the status code shouldn't be 403 as DENY_HTTP_STATUS is set to {deny_http_status}, exiting ...",
                    flush=True,
                )
                exit(1)

            print("✅ Request got rejected, as expected", flush=True)
        else:
            if not listen_http:
                print(
                    "❌ Request didn't get rejected, even if the server is not listening on HTTP, exiting ...",
                    flush=True,
                )
                exit(1)

            if response.status_code not in (404, 301):
                response.raise_for_status()

            print("✅ Request didn't get rejected, as expected", flush=True)
    except ConnectionError as e:
        if listen_http:
            if deny_http_status == "403" or not disabled_default_server:
                raise e

            print("✅ Request got rejected with the expected deny_http_status", flush=True)
            exit(0)
        else:
            print(
                "✅ Request got rejected because the server is not listening on HTTP, as expected",
                flush=True,
            )

    if ssl_generated:
        sleep(1)

        ssl_protocols = getenv("SSL_PROTOCOLS", "TLSv1.2 TLSv1.3")

        print("ℹ️ Creating a socket and wrapping it with SSL an SSL context to test SSL_PROTOCOLS", flush=True)

        sock = create_connection(("www.example.com", 443))
        ssl_context = create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = CERT_NONE
        ssl_sock = ssl_context.wrap_socket(sock, server_hostname="www.example.com")

        if ssl_sock.version() not in ssl_protocols.split(" "):
            print(
                f"❌ SSL_PROTOCOLS is set to {ssl_protocols}, but the socket is using {ssl_sock.version()}, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Socket is using the expected SSL protocol", flush=True)

        if not listen_http:
            exit(0)
    else:
        print("ℹ️ Skipping SSL_PROTOCOLS test as SSL is disabled", flush=True)

    sleep(1)

    redirect_http_to_https = getenv("REDIRECT_HTTP_TO_HTTPS", "no") == "yes"
    auto_redirect_http_to_https = getenv("AUTO_REDIRECT_HTTP_TO_HTTPS", "no") == "yes"

    print(
        f"ℹ️ Sending a HEAD request to http://www.example.com to test {'auto ' if auto_redirect_http_to_https else ''}redirect_http_to_https",
        flush=True,
    )

    response = head("http://www.example.com", headers={"Host": "www.example.com"})

    if response.status_code == 403:
        print(
            "✅ Request got rejected, as expected because the server is not listening on HTTP",
            flush=True,
        )
    else:
        if response.status_code not in (404, 301):
            response.raise_for_status()

        if (redirect_http_to_https or (auto_redirect_http_to_https and ssl_generated)) and response.status_code != 301:
            print(
                f"❌ Request didn't get redirected, even if {'auto ' if auto_redirect_http_to_https else ''}redirect_http_to_https is enabled, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Request got redirected to https, as expected", flush=True)

    sleep(1)

    allowed_methods = getenv("ALLOWED_METHODS", "GET|POST|HEAD")

    print(
        f"ℹ️ Sending a GET request to http{'s' if ssl_generated else ''}://www.example.com to test ALLOWED_METHODS",
        flush=True,
    )

    response = get(
        f"http{'s' if ssl_generated else ''}://www.example.com",
        headers={"Host": "www.example.com"},
        verify=False,
    )

    if response.status_code == 405:
        if "GET" in allowed_methods:
            print(
                "❌ Request got rejected, even if GET is in allowed methods, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Request got rejected, as expected", flush=True)
    else:
        if response.status_code != 404:
            response.raise_for_status()

        if "GET" not in allowed_methods:
            print(
                "❌ Request didn't get rejected, even if GET is not in allowed methods, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Request didn't get rejected, as expected", flush=True)

    sleep(1)

    max_client_size = getenv("MAX_CLIENT_SIZE", "5m")

    print(
        f"ℹ️ Sending a POST request to http{'s' if ssl_generated else ''}://www.example.com with a 5+MB body to test MAX_CLIENT_SIZE",
        flush=True,
    )

    response = post(
        f"http{'s' if ssl_generated else ''}://www.example.com",
        headers={"Host": "www.example.com"},
        data="a" * 5242881,
        verify=not ssl_generated,
    )

    if response.status_code in (413, 400):
        if max_client_size != "5m":
            print(
                f"❌ Request got rejected, but the status code shouldn't be 400 or 413 as MAX_CLIENT_SIZE is set to {max_client_size}, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Request got rejected, as expected", flush=True)
    else:
        if response.status_code != 404:
            response.raise_for_status()

        if max_client_size == "5m":
            print(
                f"❌ Request didn't get rejected, even if MAX_CLIENT_SIZE is set to {max_client_size}, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Request didn't get rejected, as expected", flush=True)

    sleep(1)

    serve_files = getenv("SERVE_FILES", "yes") == "yes"

    print(
        f"ℹ️ Sending a HEAD request to http{'s' if ssl_generated else ''}://www.example.com/index.html to test the serve_files option",
        flush=True,
    )

    response = head(
        f"http{'s' if ssl_generated else ''}://www.example.com/index.html",
        headers={"Host": "www.example.com"},
        verify=not ssl_generated,
    )

    if response.status_code != 404 and not serve_files:
        print(
            "❌ Request didn't get rejected, even if serve_files is disabled, exiting ...",
            flush=True,
        )
        exit(1)
    elif response.status_code == 404:
        if serve_files:
            print(
                "❌ Request got rejected, even if serve_files is enabled, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Request got rejected, as expected", flush=True)
    else:
        response.raise_for_status()
        print("✅ Request didn't get rejected, as expected", flush=True)

    sleep(1)

    http2 = getenv("HTTP2", "yes") == "yes"

    print(
        f"ℹ️ Sending a GET request to http{'s' if ssl_generated else ''}://www.example.com with HTTP/2 to test HTTP2",
        flush=True,
    )

    proc = run(
        [
            "curl",
            "--insecure",
            "--http2",
            "-I",
            "-H",
            '"Host: www.example.com"',
            f"http{'s' if ssl_generated else ''}://www.example.com",
            "-w '%{response_code} %{http_version}'",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    status_code, http_version = proc.stdout.splitlines()[-1].replace("'", "").strip().split(" ")

    if status_code not in ("200", "404"):
        print("❌ Request didn't get accepted, exiting ...", flush=True)
        exit(1)
    elif ssl_generated and http2 and http_version != "2":
        print("❌ Request didn't get accepted with HTTP/2, exiting ...", flush=True)
        exit(1)
    elif (not ssl_generated or not http2) and http_version != "1.1":
        print("❌ Request got accepted with HTTP/2, it shouldn't have, exiting ...", flush=True)
        exit(1)

    print(f"✅ Request got accepted with HTTP/{http_version}", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
