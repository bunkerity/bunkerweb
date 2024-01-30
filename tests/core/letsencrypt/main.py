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
            resp = get("http://www.example.com/ready", headers={"Host": "www.example.com"}, verify=False, allow_redirects=True)
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

    auto_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"

    print(
        "ℹ️ Sending a request to http://www.example.com ...",
        flush=True,
    )

    try:
        req = get("http://www.example.com", headers={"Host": "www.example.com"})
        req.raise_for_status()
    except RequestException:
        if not auto_letsencrypt:
            print(
                "❌ The request failed even though let's Encrypt isn't activated, exiting ...",
                flush=True,
            )
            exit(1)

    if not auto_letsencrypt:
        print("✅ Let's Encrypt isn't activated, as expected ...", flush=True)
        exit(0)

    print(
        "ℹ️ Sending a request to https://www.example.com ...",
        flush=True,
    )

    try:
        req = get("https://www.example.com", headers={"Host": "www.example.com"}, verify=False)
        req.raise_for_status()
    except RequestException as e:
        print(
            f"❌ The request failed even though let's Encrypt is activated:\n{e}\n exiting ...",
            flush=True,
        )
        exit(1)

    sleep(1)

    context = create_default_context()
    context.check_hostname = False
    context.verify_mode = CERT_NONE
    with create_connection(("www.example.com", 443)) as sock:
        with context.wrap_socket(sock, server_hostname="www.example.com") as ssock:
            # Retrieve the SSL certificate
            pem_data = DER_cert_to_PEM_cert(ssock.getpeercert(True))

    # Parse the PEM certificate
    certificate = x509.load_pem_x509_certificate(pem_data.encode(), default_backend())

    common_name = certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
    if common_name != "www.example.org":
        print(
            f"❌ Let's Encrypt is activated and the Common Name (CN) is not www.example.org (fallback one) but {common_name}, exiting ...",
            flush=True,
        )
        exit(1)

    print("✅ Let's Encrypt is activated and the Common Name (CN) is the expected one (fallback), as expected ...", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
