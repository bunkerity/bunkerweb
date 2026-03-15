from datetime import datetime, timezone
from hashlib import sha256
from json import dumps, loads
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.x509 import load_pem_x509_certificate
from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_CONFIG, DB
from app.utils import LOGGER

customcert = Blueprint("customcert", __name__)

CUSTOMCERT_CACHE_ROOT = Path("/var/cache/bunkerweb/customcert")
CUSTOMCERT_METADATA_ROOT = Path("/var/cache/bunkerweb/customcert-metadata")

# Maximum SANs to display in table (show "and X more" if exceeded)
MAX_DISPLAY_SANS = 8


def _path_under_root(resolved_path: Path, root: Path) -> bool:
    """Return True if resolved_path is under root (prevents path traversal)."""
    try:
        return resolved_path.is_relative_to(root.resolve()) or resolved_path.resolve() == root.resolve()
    except (ValueError, OSError):
        return False


def sanitize_service_name(value: str, max_length: int = 255) -> str:
    """Sanitize service name for path/DB/display: alphanumeric, dot, hyphen, underscore only."""
    if not isinstance(value, str):
        return ""
    value = value.strip()[:max_length]
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_")
    return "".join(c if c in safe_chars else "" for c in value)


def sanitize_cert_field(value: str, max_length: int = 1024) -> str:
    """Sanitize certificate field to prevent injection attacks.

    Only allows alphanumeric, dots, hyphens, underscores, and spaces.
    Truncates to max_length to prevent DOS.
    """
    if not isinstance(value, str):
        return ""

    # Truncate to max length
    value = value[:max_length]

    # Only allow safe characters: alphanumeric, dots, hyphens, underscores, spaces, @, :, /, =, ,
    # This covers domain names, IPs, and common certificate formats (RDN attributes use = and ,)
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_@ :/*=,")
    return "".join(c if c in safe_chars else "?" for c in value)


def matches_domain_pattern(domain: str, pattern: str) -> bool:
    """Check if a domain matches a certificate pattern (supporting wildcards).

    Examples:
    - "www.example.com" matches "www.example.com" -> True
    - "www.example.com" matches "*.example.com" -> True
    - "api.example.com" matches "*.example.com" -> True
    - "example.com" matches "*.example.com" -> False (wildcard requires subdomain)
    - "sub.www.example.com" matches "*.example.com" -> False (too many subdomains)
    """
    pattern = pattern.lower()
    domain = domain.lower()

    if pattern == domain:
        return True

    if pattern.startswith("*."):
        # Wildcard pattern - must match exactly one subdomain level
        suffix = pattern[2:]  # Remove "*."
        if domain.endswith("." + suffix):
            # Check that there's exactly one label before the suffix
            prefix = domain[: -len(suffix) - 1]
            return "." not in prefix

    return False


def validate_cert_names(cn: str | None, sans: list[str], service_domains: list[str]) -> dict:
    """Validate that certificate CN/SANs match the service domain names.

    Returns dict with:
    - "valid": bool - True if at least one service domain is covered by cert
    - "covered_domains": list - service domains covered by the certificate
    - "uncovered_domains": list - service domains NOT covered by the certificate
    - "warnings": list - validation warning messages
    """
    if not service_domains:
        return {
            "valid": True,
            "covered_domains": [],
            "uncovered_domains": [],
            "warnings": [],
        }

    # All possible certificate names (CN + SANs, deduplicated and lowercased)
    cert_names = set()
    if cn:
        cert_names.add(cn.lower())
    for san in sans:
        cert_names.add(san.lower())

    covered = []
    uncovered = []

    for service_domain in service_domains:
        service_domain_lower = service_domain.lower()
        # Check if this service domain matches any certificate name
        if any(matches_domain_pattern(service_domain_lower, cert_name) for cert_name in cert_names):
            covered.append(service_domain)
        else:
            uncovered.append(service_domain)

    warnings = []
    if uncovered:
        warnings.append(
            f"Certificate does not cover: {', '.join(sanitize_cert_field(d) for d in uncovered)}. "
            f"Cert covers: {', '.join(sorted(sanitize_cert_field(n) for n in cert_names))}"
        )

    return {
        "valid": len(uncovered) == 0,
        "covered_domains": [sanitize_cert_field(d) for d in covered],
        "uncovered_domains": [sanitize_cert_field(d) for d in uncovered],
        "warnings": warnings,
    }


def get_cert_key_type_and_size(cert_pem: bytes) -> tuple[str, int | None]:
    """Extract key type and size from certificate."""
    try:
        cert = load_pem_x509_certificate(cert_pem)
        pub_key = cert.public_key()

        if isinstance(pub_key, rsa.RSAPublicKey):
            return "RSA", pub_key.key_size
        elif isinstance(pub_key, ec.EllipticCurvePublicKey):
            return f"ECDSA ({pub_key.curve.name})", pub_key.key_size
        elif isinstance(pub_key, dsa.DSAPublicKey):
            return "DSA", pub_key.key_size
        else:
            return "Unknown", None
    except Exception as e:
        LOGGER.warning(f"Could not extract key type: {e}")
        return "Unknown", None


def get_cert_info(cert_pem: bytes) -> dict:
    """Extract certificate information (CN, SANs, TTL, Issuer, OCSP, EKU, not_before)."""
    try:
        cert = load_pem_x509_certificate(cert_pem)

        # Extract CN (Common Name)
        cn = None
        try:
            from cryptography.x509.oid import NameOID

            cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            if cn_attrs:
                cn = str(cn_attrs[0].value)
        except Exception:
            pass

        # Extract SANs (Subject Alternative Names)
        sans = []
        try:
            from cryptography.x509 import DNSName, SubjectAlternativeName
            from cryptography.x509.oid import ExtensionOID

            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            if isinstance(san_ext.value, SubjectAlternativeName):
                for name in san_ext.value:
                    if isinstance(name, DNSName):
                        sans.append(str(name.value))
        except Exception:
            pass

        # Get validity dates
        now = datetime.now(timezone.utc)
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc

        if getattr(not_before, "tzinfo", None) is None:
            not_before = not_before.replace(tzinfo=timezone.utc)
        if getattr(not_after, "tzinfo", None) is None:
            not_after = not_after.replace(tzinfo=timezone.utc)

        # Calculate TTL
        ttl_seconds = (not_after - now).total_seconds()
        ttl_days = ttl_seconds / 86400.0

        # Check if certificate is not yet valid
        not_yet_valid = now < not_before
        not_yet_valid_days = (not_before - now).total_seconds() / 86400.0 if not_yet_valid else 0

        # Extract Issuer
        issuer = None
        try:
            issuer = cert.issuer.rfc4514_string()
        except Exception:
            issuer = str(cert.issuer)

        # Get key type and size
        key_type, key_size = get_cert_key_type_and_size(cert_pem)
        key_info_raw = f"{key_type} ({key_size} bits)" if key_size else key_type
        key_info = sanitize_cert_field(key_info_raw) or "Unknown"

        # Check Extended Key Usage (specifically for serverAuth)
        server_auth_enabled = False
        try:
            from cryptography.x509 import ExtendedKeyUsage
            from cryptography.x509.oid import ExtensionOID, ExtendedKeyUsageOID

            eku_ext = cert.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
            if isinstance(eku_ext.value, ExtendedKeyUsage):
                server_auth_enabled = ExtendedKeyUsageOID.SERVER_AUTH in eku_ext.value
        except Exception:
            # If no EKU extension found, assume it's valid (older certs may not have it)
            server_auth_enabled = True

        # Check for OCSP URLs
        ocsp_urls = []
        try:
            from cryptography.x509 import AuthorityInformationAccess
            from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

            aia_ext = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
            if isinstance(aia_ext.value, AuthorityInformationAccess):
                for desc in aia_ext.value:
                    if desc.access_method == AuthorityInformationAccessOID.OCSP:
                        ocsp_urls.append(str(desc.access_location.value))
        except Exception:
            pass

        return {
            "cn": sanitize_cert_field(cn) if cn else None,
            "sans": [sanitize_cert_field(san) for san in sans],
            "ttl_seconds": ttl_seconds,
            "ttl_days": ttl_days,
            "expires_at": not_after.isoformat(),
            "not_before": not_before.isoformat(),
            "issuer": sanitize_cert_field(issuer) if issuer else None,
            "key_info": key_info,
            "valid": ttl_seconds > 0,
            "not_yet_valid": not_yet_valid,
            "not_yet_valid_days": not_yet_valid_days,
            "server_auth_enabled": server_auth_enabled,
            "ocsp_urls": [sanitize_cert_field(url) for url in ocsp_urls],
        }
    except Exception as e:
        LOGGER.warning(f"Could not parse certificate: {e}")
        return {}


def compute_cert_hash(cert_pem: bytes) -> str:
    """Compute SHA256 hash of certificate."""
    return sha256(cert_pem).hexdigest()


def cache_cert_metadata(service_name: str, cert_hash: str, metadata: dict) -> None:
    """Cache certificate metadata with checksum in database and filesystem."""
    safe_name = sanitize_service_name(service_name)
    if not safe_name:
        LOGGER.warning("Refusing to cache metadata for empty or invalid service name")
        return
    cache_data = {
        "service_name": safe_name,
        "cert_hash": cert_hash,
        "metadata": metadata,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        # Cache in database
        DB.insert(
            "cache",
            [
                "filename",
                "content",
            ],
            [
                f"customcert-{safe_name}.json",
                dumps(cache_data),
            ],
        )
        LOGGER.debug(f"Cached certificate metadata for {safe_name} in database")
    except Exception as e:
        LOGGER.debug(f"Could not cache metadata in database for {safe_name}: {e}")

    try:
        cache_dir = CUSTOMCERT_METADATA_ROOT
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = (cache_dir / f"{safe_name}.json").resolve()
        if not _path_under_root(cache_file, cache_dir):
            LOGGER.warning(f"Refusing to write metadata outside cache root for service: {safe_name}")
            return
        cache_file.write_text(dumps(cache_data, indent=2))
    except Exception as e:
        LOGGER.debug(f"Could not cache metadata in filesystem for {safe_name}: {e}")


def get_cached_cert_metadata(service_name: str) -> dict | None:
    """Retrieve cached certificate metadata from filesystem if available."""
    safe_name = sanitize_service_name(service_name)
    if not safe_name:
        return None
    try:
        cache_file = (CUSTOMCERT_METADATA_ROOT / f"{safe_name}.json").resolve()
        if not _path_under_root(cache_file, CUSTOMCERT_METADATA_ROOT):
            return None
        if cache_file.exists():
            data = loads(cache_file.read_text())
            if isinstance(data, dict) and "metadata" in data and "cert_hash" in data:
                return data
            LOGGER.debug("Cached metadata invalid structure, ignoring")
    except Exception as e:
        LOGGER.debug(f"Could not read cached metadata from filesystem: {e}")

    return None


def find_cert_file(service_name: str) -> Path | None:
    """Find certificate file for a service (checks -ecdsa, -rsa, plain variants and cert-ecdsa.pem)."""
    safe_name = sanitize_service_name(service_name)
    if not safe_name:
        return None
    # Try different algorithm variants (as directory suffixes)
    # Include both regular and wildcard variants
    variants = [
        f"{safe_name}-ecdsa",
        f"{safe_name}-rsa",
        f"{safe_name}-ML-DSA",
        f"{safe_name}-SLH-DSA",
        f"{safe_name}-pqc",
        safe_name,
        f"_wildcard_.{safe_name}-ecdsa",
        f"_wildcard_.{safe_name}-rsa",
        f"_wildcard_.{safe_name}-ML-DSA",
        f"_wildcard_.{safe_name}-SLH-DSA",
        f"_wildcard_.{safe_name}-pqc",
        f"_wildcard_.{safe_name}",
    ]

    cert_filenames = ["cert.pem", "cert-ecdsa.pem", "cert-rsa.pem"]

    for variant in variants:
        for cert_filename in cert_filenames:
            cert_path = (CUSTOMCERT_CACHE_ROOT / variant / cert_filename).resolve()
            if not _path_under_root(cert_path, CUSTOMCERT_CACHE_ROOT):
                continue
            if cert_path.exists():
                LOGGER.debug(f"✓ Found certificate for {safe_name} at: {cert_path}")
                return cert_path

    LOGGER.debug(f"No certificate found for {safe_name}")
    return None


@customcert.route("/customcert", methods=["GET"])
@login_required
def customcert_page():
    """Display overview of all custom certificates."""
    certs = []

    LOGGER.debug("CUSTOMCERT page start")

    # Get multisite configuration
    try:
        multisite_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("MULTISITE",))
        multisite = multisite_config.get("MULTISITE")
        multisite = multisite == "yes" if multisite else False
        LOGGER.debug(f"Multisite mode: {multisite}")
    except Exception as e:
        LOGGER.error(f"Error getting MULTISITE config: {e}")
        multisite = False

    if multisite:
        # Get all services from SERVER_NAME and check which have custom SSL enabled
        try:
            server_name_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME",))
            server_names = server_name_config.get("SERVER_NAME", "")
            services = []

            if not server_names:
                LOGGER.warning("SERVER_NAME is empty in multisite mode")
            else:
                server_list = server_names.split()
                LOGGER.debug(f"Parsed server list ({len(server_list)} entries)")

                saved_settings = DB.get_services_settings(methods=False, with_drafts=False)
                draft_settings = DB.get_services_settings(methods=False, with_drafts=True)

                for idx, service_name in enumerate(server_list):
                    if idx < len(saved_settings) and idx < len(draft_settings):
                        saved_config = saved_settings[idx]
                        draft_config = draft_settings[idx]

                        use_custom_ssl_saved = saved_config.get("USE_CUSTOM_SSL")
                        use_custom_ssl_draft = draft_config.get("USE_CUSTOM_SSL")

                        is_draft = use_custom_ssl_draft != use_custom_ssl_saved
                        use_custom_ssl = use_custom_ssl_draft if is_draft else use_custom_ssl_saved

                        LOGGER.debug(
                            f"Service {sanitize_service_name(service_name) or '?'}: "
                            f"saved={use_custom_ssl_saved}, draft={use_custom_ssl_draft}, is_draft={is_draft}"
                        )

                        if use_custom_ssl == "yes":
                            services.append((service_name, is_draft))
                    else:
                        LOGGER.warning(f"Service at index {idx} not found in services_settings")
        except Exception as e:
            LOGGER.error(f"Error getting server configuration in multisite mode: {e}")
            services = []
    else:
        # Single-site mode
        try:
            # Get both saved and draft config
            use_custom_ssl_saved_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=(
                "USE_CUSTOM_SSL",
            ), with_drafts=False)
            use_custom_ssl_draft_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=(
                "USE_CUSTOM_SSL",
            ), with_drafts=True)

            use_custom_ssl_saved = use_custom_ssl_saved_config.get("USE_CUSTOM_SSL", "no")
            use_custom_ssl_draft = use_custom_ssl_draft_config.get("USE_CUSTOM_SSL", "no")

            # Determine which value to use and if it's a draft
            is_draft = use_custom_ssl_draft != use_custom_ssl_saved
            use_custom_ssl = use_custom_ssl_draft if is_draft else use_custom_ssl_saved

            server_name_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=(
                "SERVER_NAME",
            ))
            server_name = server_name_config.get("SERVER_NAME", "")

            LOGGER.debug(
                f"Single-site: USE_CUSTOM_SSL={use_custom_ssl}, is_draft={is_draft}, "
                f"SERVER_NAME={sanitize_service_name(server_name) or '?'}"
            )

            if use_custom_ssl == "yes" and server_name:
                service = server_name.split()[0] if isinstance(server_name, str) else server_name
                services = [(service, is_draft)]
            else:
                LOGGER.warning(
                    f"Not collecting certs: USE_CUSTOM_SSL={use_custom_ssl}, "
                    f"SERVER_NAME={sanitize_service_name(server_name) or '?'}"
                )
                services = []
        except Exception as e:
            LOGGER.error(f"Error getting configuration in single-site mode: {e}")
            services = []

    LOGGER.debug(f"Collecting certs for {len(services)} service(s) with custom SSL")
    for service_entry in services:
        if isinstance(service_entry, tuple):
            service_name, is_draft = service_entry
        else:
            service_name = service_entry
            is_draft = False

        safe_name = sanitize_service_name(service_name)
        if not safe_name or safe_name != service_name:
            LOGGER.warning(f"Skipping service with invalid or unsafe name (sanitized: {safe_name!r})")
            continue

        cert_file = find_cert_file(service_name)
        LOGGER.debug(f"Service {safe_name}: cert_file={cert_file}")
        if cert_file and cert_file.exists():
            try:
                cert_pem = cert_file.read_bytes()
                cert_hash = compute_cert_hash(cert_pem)

                # Check if cached metadata is still valid
                cached_data = get_cached_cert_metadata(service_name)
                if cached_data and cached_data.get("cert_hash") == cert_hash:
                    cert_info = cached_data.get("metadata", {})
                    LOGGER.debug(f"Using cached metadata for {safe_name}")
                else:
                    cert_info = get_cert_info(cert_pem)
                    cache_cert_metadata(service_name, cert_hash, cert_info)
                    LOGGER.debug(f"Parsed and cached certificate metadata for {safe_name}")

                # Validate certificate CN/SANs match the service domain names
                try:
                    service_name_config = BW_CONFIG.get_config(
                        global_only=False, methods=False, with_drafts=False
                    )
                    # Get the service's SERVER_NAME (can be multiple space-separated domains)
                    service_server_name_key = f"{service_name}_SERVER_NAME"
                    service_domains_str = service_name_config.get(service_server_name_key) or service_name
                    service_domains = service_domains_str.split() if isinstance(service_domains_str, str) else [service_domains_str]

                    # Validate certificate covers all service domains
                    validation = validate_cert_names(
                        cert_info.get("cn"),
                        cert_info.get("sans", []),
                        service_domains,
                    )
                    cert_info["cert_validation"] = validation
                    LOGGER.debug(f"Certificate validation for {safe_name}: valid={validation['valid']}")
                except Exception as e:
                    LOGGER.warning(f"Could not validate certificate names for {safe_name}: {e}")
                    err_msg = sanitize_cert_field(str(e), max_length=200) if str(e) else "Validation failed"
                    cert_info["cert_validation"] = {
                        "valid": None,
                        "covered_domains": [],
                        "uncovered_domains": [],
                        "warnings": [err_msg or "Validation failed"],
                    }

                cert_info["service_name"] = safe_name
                cert_info["cert_file"] = str(cert_file)
                cert_info["is_draft"] = is_draft
                certs.append(cert_info)
                LOGGER.debug(f"Added certificate for {safe_name}")
            except Exception as e:
                LOGGER.error(f"Error reading certificate for {safe_name}: {e}")
        else:
            LOGGER.warning(f"USE_CUSTOM_SSL is enabled for {safe_name} but no certificate data found")
            certs.append({
                "service_name": safe_name,
                "error": "USE_CUSTOM_SSL is enabled but no certificate data found",
                "is_draft": is_draft,
            })

    LOGGER.debug(f"CUSTOMCERT page end: {len(certs)} cert(s)")
    return render_template("customcert.html", certs=certs, multisite=multisite)
