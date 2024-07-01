from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta
from os import getenv
from requests import get
from socket import create_connection
from ssl import CERT_NONE, DER_cert_to_PEM_cert, create_default_context
from time import sleep
from traceback import format_exc

try:
    ssl_generated = getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes"
    self_signed_ssl_expiry = getenv("SELF_SIGNED_SSL_EXPIRY", "365")

    self_signed_ssl_expiry = datetime.now() + timedelta(days=int(self_signed_ssl_expiry)) - timedelta(hours=1)

    self_signed_ssl_subj = getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/")

    response = get("http://www.example.com", headers={"Host": "www.example.com"}, verify=False)

    if not ssl_generated and response.status_code == 200:
        print(
            "✅ The SSL generation is disabled and the request returned 200, exiting ...",
            flush=True,
        )
        exit(0)

    sleep(1)

    response = get("https://www.example.com", headers={"Host": "www.example.com"}, verify=False)

    if ssl_generated and response.status_code != 200:
        print(
            f"❌ The SSL generation is enabled and the request returned {response.status_code}, exiting ...",
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
    check_self_signed_ssl_subj = self_signed_ssl_subj.replace("/", "").replace("CN=", "")
    if common_name != check_self_signed_ssl_subj:
        print(
            f"❌ The SSL generation is enabled and the Common Name (CN) is not {check_self_signed_ssl_subj} but {common_name}, exiting ...",
            flush=True,
        )
        exit(1)

    expiration_date = certificate.not_valid_after
    if expiration_date < self_signed_ssl_expiry:
        print(
            f"❌ The SSL generation is enabled and the expiration date is {expiration_date} but should be {self_signed_ssl_expiry}, exiting ...",
            flush=True,
        )
        exit(1)

    print("✅ The SSL generation is enabled and the certificate is valid", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
