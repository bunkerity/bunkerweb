from contextlib import suppress
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from os import getenv
from socket import create_connection
from ssl import CERT_NONE, DER_cert_to_PEM_cert, create_default_context
from requests import RequestException, get
from traceback import format_exc
from time import sleep

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get("http://app1.example.com/ready", headers={"Host": "app1.example.com"}, verify=False, allow_redirects=True)
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

    use_custom_ssl = getenv("USE_CUSTOM_SSL", "no") == "yes"
    fallback = not bool(getenv("CUSTOM_SSL_CERT", False))

    print(
        "ℹ️ Sending a request to http://app1.example.com ...",
        flush=True,
    )

    try:
        req = get("http://app1.example.com", headers={"Host": "app1.example.com"})
        req.raise_for_status()
    except RequestException:
        if not use_custom_ssl:
            print(
                "❌ The request failed even though the Custom Cert isn't activated, exiting ...",
                flush=True,
            )
            exit(1)

    if not use_custom_ssl:
        print("✅ The Custom Cert isn't activated, as expected ...", flush=True)
        exit(0)

    print(
        "ℹ️ Sending a request to https://app1.example.com ...",
        flush=True,
    )

    try:
        req = get("https://app1.example.com", headers={"Host": "app1.example.com"}, verify=False)
        req.raise_for_status()
    except RequestException as e:
        print(
            f"❌ The request failed even though the Custom Cert is activated:\n{e}\n exiting ...",
            flush=True,
        )
        exit(1)

    sleep(1)

    context = create_default_context()
    context.check_hostname = False
    context.verify_mode = CERT_NONE
    with create_connection(("app1.example.com", 443)) as sock:
        with context.wrap_socket(sock, server_hostname="app1.example.com") as ssock:
            # Retrieve the SSL certificate
            pem_data = DER_cert_to_PEM_cert(ssock.getpeercert(True))

    # Parse the PEM certificate
    certificate = x509.load_pem_x509_certificate(pem_data.encode(), default_backend())

    common_name = certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
    if fallback and common_name != "www.example.org":
        print(
            f"❌ The Custom Cert is activated and the Common Name (CN) is not www.example.org (fallback one) but {common_name}, exiting ...",
            flush=True,
        )
        exit(1)
    elif not fallback and common_name != "app1.example.com":
        print(
            f"❌ The Custom Cert is activated and the Common Name (CN) is not app1.example.com but {common_name}, exiting ...",
            flush=True,
        )
        exit(1)

    print("✅ The Custom Cert is activated and the Common Name (CN) is the right one, as expected ...", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
