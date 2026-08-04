"""Single source of truth for validating a custom certificate/key pair.

The scheduler job caches whatever it is given and the certificate is only ever
parsed for real later, in Lua, by `parse_pem_cert`/`parse_pem_priv_key` at init.
A pair that fails there logs one line and the service silently falls back to the
default certificate, so the operator's first signal is a browser warning. This
module makes the pair fail loudly, at the point it is supplied, with the reason.

Imported by:
  - src/common/core/customcert/jobs/custom-cert.py (scheduler)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key
from cryptography.x509.oid import NameOID


def _public_bytes(key) -> bytes:
    return key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)


def _subject_cn(cert: x509.Certificate) -> Optional[str]:
    attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not attributes:
        return None
    value = attributes[0].value
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


def _sans(cert: x509.Certificate) -> List[str]:
    try:
        extension = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return []
    return extension.value.get_values_for_type(x509.DNSName)


def validate_certificate_pair(cert_pem: bytes, key_pem: bytes) -> Dict[str, Any]:
    """Check that a PEM certificate and private key parse and belong together.

    Returns a dict with:
      ok             False when the pair cannot be used at all
      error          why, when ok is False
      warnings       usable but questionable (expired, not yet valid)
      subject_cn     certificate common name, when present
      sans           subjectAltName DNS entries
      not_before     ISO 8601 UTC, when the certificate parsed
      not_after      ISO 8601 UTC, when the certificate parsed
      days_remaining negative once expired
      key_type       private key class name, when the key parsed

    Expiry is deliberately a warning and never blocking: refusing an expired
    certificate would withdraw one that is currently being served and drop the
    service to the default certificate, which is worse than serving expired.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "error": "",
        "warnings": [],
        "subject_cn": None,
        "sans": [],
        "not_before": None,
        "not_after": None,
        "days_remaining": None,
        "key_type": None,
    }

    try:
        cert = x509.load_pem_x509_certificate(cert_pem)
    except BaseException as e:
        result["error"] = f"Certificate could not be parsed: {e}"
        return result

    result["subject_cn"] = _subject_cn(cert)
    result["sans"] = _sans(cert)
    result["not_before"] = cert.not_valid_before_utc.isoformat()
    result["not_after"] = cert.not_valid_after_utc.isoformat()

    try:
        # password=None is what rejects an encrypted key, which NGINX could not
        # use either without a passphrase file.
        key = load_pem_private_key(key_pem, password=None)
    except TypeError:
        result["error"] = "Private key is encrypted, which is not supported. Supply an unencrypted key."
        return result
    except BaseException as e:
        result["error"] = f"Private key could not be parsed: {e}"
        return result

    result["key_type"] = type(key).__name__

    try:
        matches = _public_bytes(cert.public_key()) == _public_bytes(key.public_key())
    except BaseException as e:
        result["error"] = f"Certificate and private key could not be compared: {e}"
        return result

    if not matches:
        result["error"] = "Private key does not match the certificate."
        return result

    now = datetime.now(timezone.utc)
    result["days_remaining"] = (cert.not_valid_after_utc - now).days
    if cert.not_valid_after_utc < now:
        result["warnings"].append(f"Certificate expired on {result['not_after']}.")
    elif cert.not_valid_before_utc > now:
        result["warnings"].append(f"Certificate is not valid before {result['not_before']}.")

    result["ok"] = True
    return result
