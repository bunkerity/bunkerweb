"""Single-site aliases must not acquire separate upstream TLS caches."""

import pytest

from test_trusted_cert import CERT, CRL, KEY, execute  # noqa: F401


@pytest.mark.parametrize("multisite,services", [("no", ("a.example",)), ("yes", ("a.example", "b.example", "c.example"))])
def test_alias_material_is_cached_once_per_service(execute, multisite, services):  # noqa: F811
    material = {}
    for prefix in ("REVERSE_PROXY", "GRPC"):
        material.update(
            {
                f"USE_{prefix}": "yes",
                f"{prefix}_SSL_VERIFY": "yes",
                f"{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": CERT,
                f"{prefix}_SSL_CRL_DATA": CRL,
                f"{prefix}_SSL_CLIENT_CERT_DATA": CERT,
                f"{prefix}_SSL_CLIENT_KEY_DATA": KEY,
            }
        )
    settings = material if multisite == "no" else {f"{service}_{key}": value for service in services for key, value in material.items()}
    settings.update(MULTISITE=multisite, SERVER_NAME="a.example b.example c.example")
    status, files, _ = execute(settings)
    names = ("trusted-ca.pem", "crl.pem", "client-cert.pem", "client-key.pem", "grpc-trusted-ca.pem", "grpc-crl.pem", "grpc-client.pem", "grpc-client.key")
    assert status == 1
    assert set(files) == {f"{service}/{name}" for service in services for name in names}
    assert execute(settings)[0] == 0
