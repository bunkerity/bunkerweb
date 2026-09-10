#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from traceback import format_exc
from typing import Set, Tuple, Union, Optional, Literal

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from certificate_utils import certificate_status, parse_certificate  # type: ignore
from common_utils import bytes_hash  # type: ignore
from default_server import DEFAULT_SERVER_ID, strip_default_server, strip_default_server_unless_alone  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("CUSTOM-CERT")
JOB = Job(LOGGER, __file__)

# The default server's own material. Cached under the reserved `default-server` pseudo-service once
# that row exists (it is the default server's owner, so the cache row gets a real FK instead of a
# NULL service_id), and at the root of the plugin cache on a database that has not been seeded yet --
# customcert.lua reads both, which is also what carries an upgrade across the one reload where the
# old file is still the live one. Deliberately NOT
# /var/lib/bunkerweb/default-server-cert.{pem,key} -- that pair is the static fallback of EVERY
# service block (confs/server-http/ssl-certificate-lua.conf:1-2), not just the default server's.
DEFAULT_SERVER_CERT_CACHE = "default-server-cert.pem"
DEFAULT_SERVER_KEY_CACHE = "default-server-key.pem"
# What the operator sees in a log line; `process_ssl_data` formats it into its own messages.
DEFAULT_SERVER_LABEL = "the default server"


def process_ssl_data(data: str, file_path: Optional[str], data_type: Literal["cert", "key"], server_name: str) -> Union[bytes, Path, None]:
    """Process SSL certificate or key data from file path or direct data (base64 or plain text)"""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{data_type.capitalize()} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                LOGGER.error(f"Invalid certificate format for server {server_name}")
                return None
            if data_type == "key" and b"PRIVATE KEY" not in text_data:
                LOGGER.error(f"Invalid key format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode. We remove whitespaces and pad if needed.
        decoded = b""
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if data_type == "cert" and not decoded.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                raise ValueError("decoded certificate data is not PEM")
            if data_type == "key" and (not decoded.strip().startswith(b"-----BEGIN") or b"PRIVATE KEY" not in decoded):
                raise ValueError("decoded key data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode {data_type} data as base64 for server {server_name}, trying as plain text")

            # Fallback: validate and use plaintext data.
            try:
                if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                    LOGGER.error(f"Invalid certificate format for server {server_name}")
                    return None
                elif data_type == "key" and (not text_data.strip().startswith(b"-----BEGIN") or b"PRIVATE KEY" not in text_data):
                    LOGGER.error(f"Invalid key format for server {server_name}")
                    return None
                return text_data
            except BaseException:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while processing {data_type} data for server {server_name}")
                return None
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {data_type} for {server_name}: {e}")
        return None


def check_cert(cert_file: Union[Path, bytes], key_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    try:
        ret = False
        if not cert_file or not key_file:
            return False, "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"

        if isinstance(cert_file, Path):
            if not cert_file.is_file():
                return False, f"Certificate file {cert_file} is not a valid file, ignoring the custom certificate"
            cert_file = cert_file.read_bytes()

        if isinstance(key_file, Path):
            if not key_file.is_file():
                return False, f"Key file {key_file} is not a valid file, ignoring the custom certificate"
            key_file = key_file.read_bytes()

        # Validate the pair through the same function the inventory path uses
        # (`db_methods.certificates.create_certificate`), so a certificate supplied by setting
        # is held to the checks as one uploaded through the API. The previous check ran
        # `openssl x509 -noout` on the certificate alone and never looked at the key, so a
        # malformed, encrypted or mismatched key was cached and pushed to every instance, and
        # only failed later in Lua -- where the service silently falls back to the default
        # certificate and the operator's first signal is a browser warning.
        try:
            parsed = parse_certificate(cert_file, key_file)
        except (TypeError, ValueError) as e:
            return False, str(e)

        # Expiry warns and never blocks: refusing a certificate that is currently being served
        # would withdraw it and drop the service to the default one, which is worse than
        # serving expired.
        # Not named `status`: the job body below uses a module-level `status` as its exit code.
        cert_state = certificate_status(parsed["valid_from"], parsed["valid_to"])
        if cert_state != "valid":
            LOGGER.warning(f"{first_server}: custom certificate is {cert_state.replace('_', ' ')} (valid from {parsed['valid_from']} to {parsed['valid_to']})")

        cert_hash = bytes_hash(cert_file)
        old_hash = JOB.cache_hash("cert.pem", service_id=first_server)
        cert_path = Path(sep, "var", "cache", "bunkerweb", "customcert", first_server, "cert.pem")
        if old_hash != cert_hash or not cert_path.is_file():
            ret = True
            cached, err = JOB.cache_file("cert.pem", cert_file, service_id=first_server, checksum=cert_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-cert cert.pem file : {err}")
                return False, err

        key_hash = bytes_hash(key_file)
        old_hash = JOB.cache_hash("key.pem", service_id=first_server)
        key_path = Path(sep, "var", "cache", "bunkerweb", "customcert", first_server, "key.pem")
        if old_hash != key_hash or not key_path.is_file():
            ret = True
            cached, err = JOB.cache_file("key.pem", key_file, service_id=first_server, checksum=key_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-key key.pem file : {err}")
                return False, err

        return ret, ""
    except BaseException as e:
        return False, e


def normalize_hostname(hostname: str) -> str:
    """Case-, whitespace- and trailing-dot-free form every hostname comparison below runs on."""
    return hostname.strip().rstrip(".").lower()


def hostname_covered_by(pattern: str, name: str) -> bool:
    """True when `pattern` -- a certificate SAN/CN or a SERVER_NAME value -- answers for `name`.

    Both sides can carry a wildcard: a certificate can be issued for `*.example.com`, and a service
    can be configured with `SERVER_NAME=*.example.com` (settings.json accepts it and NGINX matches
    it). The caller tests both directions, so this only has to decide one.
    """
    pattern, name = normalize_hostname(pattern), normalize_hostname(name)
    if not pattern or not name:
        return False
    if pattern == name:
        return True
    if pattern.startswith("."):
        # NGINX's ".example.com" means example.com AND every sub-domain of it.
        base = pattern[1:]
        return bool(base) and (name == base or name.endswith(f".{base}"))
    if pattern.startswith("*."):
        # RFC 6125 and NGINX agree: a leading wildcard covers exactly one label.
        base = pattern[2:]
        return bool(base) and name.endswith(f".{base}") and "." not in name.removesuffix(f".{base}")
    if pattern.endswith(".*"):
        # NGINX's trailing wildcard, "www.example.*".
        base = pattern[:-2]
        return bool(base) and name.startswith(f"{base}.") and "." not in name.removeprefix(f"{base}.")
    return False


def get_configured_hostnames(all_domains: list, multisite: bool) -> Set[str]:
    """Every hostname a configured service is served on, across every service.

    Takes the roster the job already resolved rather than re-reading `SERVER_NAME`: the two
    readings have different defaults, and an empty coverage set here would silently accept a
    certificate covering a service -- the under-match is the direction that opens the hole.
    """
    if not multisite:
        # Single site: every value of SERVER_NAME is a vhost of the one service.
        return {normalize_hostname(name) for name in all_domains if name}

    hostnames = set()
    for first_server in all_domains:
        # A service always answers on its own id, even when it declares no <id>_SERVER_NAME.
        names = getenv(f"{first_server}_SERVER_NAME", "") or first_server
        hostnames.update(normalize_hostname(name) for name in names.split() if name)
    return hostnames


def find_covered_hostname(certificate_names: Set[str], configured_hostnames: Set[str]) -> Optional[str]:
    """Name the first configured service hostname the certificate would also answer for."""
    for certificate_name in sorted(certificate_names):
        for hostname in sorted(configured_hostnames):
            if hostname_covered_by(certificate_name, hostname) or hostname_covered_by(hostname, certificate_name):
                return hostname
    return None


def process_default_server(configured_hostnames: Set[str], service_id: str = "") -> int:
    """The default server's own certificate: DEFAULT_SERVER_SSL_CERT/_KEY and their _DATA twins.

    ONE function, and this docstring is the seam option (b) of the default-server conception
    reuses: turning the default server into a reserved pseudo-service changes `service_id` (empty
    today, the reserved service id then) and NOTHING else. The validation, the coalescence refusal,
    the cache names and the `ssl_certificate_default` Lua phase this feeds are identical in both
    worlds, so do not spread this branch across the job body.

    Returns this branch's contribution to the exit code: 1 = changed, 0 = nothing to do, 2 =
    refused. On 2 the cache is left exactly as it was, so the default server keeps serving whatever
    it was already serving (PO ruling 4).
    """
    cert_file_path = getenv("DEFAULT_SERVER_SSL_CERT", "")
    key_file_path = getenv("DEFAULT_SERVER_SSL_KEY", "")
    cert_data = getenv("DEFAULT_SERVER_SSL_CERT_DATA", "")
    key_data = getenv("DEFAULT_SERVER_SSL_KEY_DATA", "")

    # Whether this deployment renders a default server block AT ALL. `http.conf` includes
    # `default-server-http.conf` only under `MULTISITE=yes`, `DISABLE_DEFAULT_SERVER=yes` or the
    # transient `IS_LOADING=yes` -- so on a plain single-site deployment the one configured service's
    # own block IS NGINX's implicit default, and `ssl_certificate_default` (the phase this override
    # feeds) has no block to run in. The material is still cached: `DISABLE_DEFAULT_SERVER=yes` is a
    # real single-site configuration that serves it, and the operator can flip either switch without
    # re-supplying the certificate. What must not happen is reporting a success nobody can observe.
    servable = "yes" in (getenv("MULTISITE", "no"), getenv("DISABLE_DEFAULT_SERVER", "no"))

    if not any((cert_file_path, key_file_path, cert_data, key_data)):
        # Not configured, or just cleared: drop the cache so the internal certificate comes back.
        if not JOB.cache_hash(DEFAULT_SERVER_CERT_CACHE, service_id=service_id) and not JOB.cache_hash(DEFAULT_SERVER_KEY_CACHE, service_id=service_id):
            return 0
        JOB.del_cache(DEFAULT_SERVER_CERT_CACHE, service_id=service_id)
        JOB.del_cache(DEFAULT_SERVER_KEY_CACHE, service_id=service_id)
        # Same rule as the "applied" message below : where no default server block is rendered, the
        # internal leaf is not what comes back -- the configured service's own block answers, with
        # its own certificate. Saying otherwise names a control the operator does not have.
        LOGGER.info(
            "The default server certificate override was removed : requests that match no configured service "
            "(unknown SNI, raw IP access) are served the internal self-signed certificate again."
            if servable
            else "The default server certificate override was removed. It was never served on this single-site "
            "deployment anyway : no default server block is rendered here, so the configured service answers the "
            "requests that match no service, with its own certificate."
        )
        return 1

    # No priority setting here, unlike the per-service pair : a path wins when one is given, the
    # inline data is used otherwise. Both are stated in the settings help.
    cert_file = process_ssl_data("" if cert_file_path else cert_data, cert_file_path or None, "cert", DEFAULT_SERVER_LABEL)
    key_file = process_ssl_data("" if key_file_path else key_data, key_file_path or None, "key", DEFAULT_SERVER_LABEL)
    if not cert_file or not key_file:
        LOGGER.error(
            "The default server certificate was refused : DEFAULT_SERVER_SSL_CERT (or DEFAULT_SERVER_SSL_CERT_DATA) and "
            "DEFAULT_SERVER_SSL_KEY (or DEFAULT_SERVER_SSL_KEY_DATA) must both be set, readable and valid PEM. "
            "The default server keeps serving the certificate it was already serving."
        )
        return 2

    try:
        cert_pem = cert_file.read_bytes() if isinstance(cert_file, Path) else cert_file
        key_pem = key_file.read_bytes() if isinstance(key_file, Path) else key_file
        # The same pairing check the inventory path runs, so a certificate supplied by setting is
        # held to the checks one uploaded through the API is.
        parsed = parse_certificate(cert_pem, key_pem)
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"The default server certificate was refused : {e}. The default server keeps serving the certificate it was already serving.")
        return 2

    certificate_names = set(parsed["sans"])
    if parsed["common_name"]:
        certificate_names.add(parsed["common_name"])
    covered = find_covered_hostname(certificate_names, configured_hostnames)
    if covered:
        # The coalescence refusal (PO ruling 2). The default server answers hostnames no service
        # claims, so a certificate that ALSO covers a configured service hands a client a way to
        # reach that service over a connection the service never authorised : open the connection
        # with an unknown SNI, get this certificate, then reuse the same connection for
        # `Host: <service>` (HTTP/2 connection coalescing). NGINX re-selects the server block
        # without redoing the handshake. Refusing here is cheaper and clearer than excluding the
        # hostname at request time, and it is the only mitigation the operator can act on.
        LOGGER.error(
            f"The default server certificate was refused because it also covers {covered}, which is a hostname of a configured service. "
            "A certificate served for unknown hostnames must not be usable for a service that never asked for it : a client can open the "
            "connection with an unknown SNI, be given this certificate, then reuse that same connection for the service. Use a certificate "
            "that covers no configured service hostname, or attach this one to the service with USE_CUSTOM_SSL. The default server keeps "
            "serving the certificate it was already serving."
        )
        # The refusal is about the MATERIAL, not about the moment. An override accepted before the
        # service it covers existed is still cached, still pushed and still served, and a later run
        # that refuses it would leave exactly the state the refusal exists to prevent -- "the
        # previously served certificate stays" would mean serving the certificate just refused.
        # When the offending material IS what is cached, withdraw it: the default server falls back
        # to the internal self-signed leaf, which covers no service. Returns 1 so the removal
        # actually reaches the instances (exit 1 is the only thing that ships the cache).
        # A DIFFERENT, previously vetted certificate in the cache is left alone -- that is the case
        # PO ruling 2 is written about.
        if JOB.cache_hash(DEFAULT_SERVER_CERT_CACHE, service_id=service_id) == bytes_hash(cert_pem):
            JOB.del_cache(DEFAULT_SERVER_CERT_CACHE, service_id=service_id)
            JOB.del_cache(DEFAULT_SERVER_KEY_CACHE, service_id=service_id)
            LOGGER.error(
                f"The default server certificate that was being served has been WITHDRAWN because a configured service now uses {covered}. "
                "The default server falls back to the internal self-signed certificate until a certificate covering no configured "
                "service hostname is supplied."
            )
            return 1
        return 2

    # Expiry warns and never blocks, exactly as it does for a service certificate : refusing one
    # that is currently being served would withdraw it, which is worse than serving it expired.
    cert_state = certificate_status(parsed["valid_from"], parsed["valid_to"])
    if cert_state != "valid":
        LOGGER.warning(f"The default server certificate is {cert_state.replace('_', ' ')} (valid from {parsed['valid_from']} to {parsed['valid_to']}).")

    changed = False
    for cache_name, content in ((DEFAULT_SERVER_CERT_CACHE, cert_pem), (DEFAULT_SERVER_KEY_CACHE, key_pem)):
        checksum = bytes_hash(content)
        cache_path = Path(sep, "var", "cache", "bunkerweb", "customcert", service_id, cache_name)
        if JOB.cache_hash(cache_name, service_id=service_id) == checksum and cache_path.is_file():
            continue
        cached, err = JOB.cache_file(cache_name, content, service_id=service_id, checksum=checksum, delete_file=False)
        if not cached:
            LOGGER.error(
                f"The default server certificate could not be cached ({cache_name}) : {err}. "
                "The default server keeps serving the certificate it was already serving."
            )
            return 2
        changed = True

    if not changed:
        LOGGER.info("No change in the default server certificate.")
        return 0

    subject = parsed["common_name"] or ", ".join(sorted(certificate_names)) or "the supplied material"
    if not servable:
        LOGGER.warning(
            f"The default server certificate override for {subject} was stored but CANNOT be served : this single-site deployment "
            "renders no default server block, so the configured service answers the requests that match no service itself. Set "
            "DISABLE_DEFAULT_SERVER=yes to render the default server block, or run in multisite mode (MULTISITE=yes)."
        )
        return 1

    LOGGER.info(
        f"The default server certificate override was applied : requests that match no configured service (unknown SNI, raw IP access) "
        f"are now served the certificate for {subject}."
    )
    return 1


status = 0

try:
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"

    if isinstance(all_domains, str):
        all_domains = all_domains.split()

    # The reserved default-server pseudo-service is in SERVER_NAME like any other row, but it is not
    # a hostname and it has no per-service certificate of its own : dropped from the roster so the
    # loop below neither manages it nor counts it as a name the override must not cover. Its
    # presence is what says the row was seeded, and therefore whether the cache can carry its id.
    #
    # In single-site the same rule as `Templator.__init__`, NOT a plain MULTISITE gate : strip the
    # id unless nothing else remains. The reserved row exists only in multisite, so in single-site
    # this name is an ordinary service of the operator's -- `config_read`, which builds the
    # SERVER_NAME this job reads, keeps it on purpose unless its method is the reserved one --
    # and the two guards have to agree on WHICH name the single block is, because that name is the
    # cache directory `customcert.lua` reads (the first token of the rendered SERVER_NAME).
    # Stripping it blind emptied `all_domains` for a `SERVER_NAME=default-server` deployment, fired
    # the `sys_exit` below before the per-service branch, and silently ignored a configured
    # USE_CUSTOM_SSL ; keeping it blind would do the same thing to `default-server www.example.com`,
    # where the Templator strips it and this job would then cache under a directory nobody reads.
    default_server_seeded = multisite and DEFAULT_SERVER_ID in all_domains
    # Multisite: a plain strip, always -- the reserved row renders into its own block regardless of
    # what else is in the roster. Single-site: `strip_default_server_unless_alone` is the same rule
    # `Templator.__init__` and `config_read` enforce (strip unless nothing else would remain).
    all_domains = strip_default_server(all_domains) if multisite else strip_default_server_unless_alone(all_domains)

    # Before the roster check on purpose : the default server exists whether or not any service
    # does, so its override must be evaluated even when SERVER_NAME is empty.
    default_server_status = process_default_server(
        get_configured_hostnames(all_domains, multisite), service_id=DEFAULT_SERVER_ID if default_server_seeded else ""
    )

    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(default_server_status)

    skipped_servers = []
    managed_servers = []
    if not multisite:
        all_domains = [all_domains[0]]
        if getenv("USE_CUSTOM_SSL", "no") == "no":
            LOGGER.info("Custom SSL is not enabled, skipping ...")
            skipped_servers = all_domains

    if not skipped_servers:
        for first_server in all_domains:
            if (getenv(f"{first_server}_USE_CUSTOM_SSL", "no") if multisite else getenv("USE_CUSTOM_SSL", "no")) == "no":
                skipped_servers.append(first_server)
                continue

            LOGGER.info(f"Service {first_server} is using custom SSL certificates, checking ...")

            cert_priority = getenv(f"{first_server}_CUSTOM_SSL_CERT_PRIORITY", "file") if multisite else getenv("CUSTOM_SSL_CERT_PRIORITY", "file")
            cert_file_path = getenv(f"{first_server}_CUSTOM_SSL_CERT", "") if multisite else getenv("CUSTOM_SSL_CERT", "")
            key_file_path = getenv(f"{first_server}_CUSTOM_SSL_KEY", "") if multisite else getenv("CUSTOM_SSL_KEY", "")
            cert_data = getenv(f"{first_server}_CUSTOM_SSL_CERT_DATA", "") if multisite else getenv("CUSTOM_SSL_CERT_DATA", "")
            key_data = getenv(f"{first_server}_CUSTOM_SSL_KEY_DATA", "") if multisite else getenv("CUSTOM_SSL_KEY_DATA", "")

            # Use file or data based on priority
            use_cert_file = cert_priority == "file" and cert_file_path
            use_key_file = cert_priority == "file" and key_file_path

            cert_file = process_ssl_data(cert_data if not use_cert_file else "", cert_file_path if use_cert_file else None, "cert", first_server)

            key_file = process_ssl_data(key_data if not use_key_file else "", key_file_path if use_key_file else None, "key", first_server)

            if not cert_file or not key_file:
                LOGGER.warning(
                    "Variables (CUSTOM_SSL_CERT or CUSTOM_SSL_CERT_DATA) and (CUSTOM_SSL_KEY or CUSTOM_SSL_KEY_DATA) "
                    f"have to be set and valid to use custom certificates for {first_server}"
                )
                skipped_servers.append(first_server)
                status = 2
                continue

            LOGGER.info(f"Checking certificate for {first_server} ...")
            need_reload, err = check_cert(cert_file, key_file, first_server)
            if isinstance(err, BaseException):
                LOGGER.error(f"Exception while checking {first_server}'s certificate, skipping ... \n{err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            elif err:
                LOGGER.warning(f"Error while checking {first_server}'s certificate : {err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            # Mirror the material into the central inventory so the certificate is visible and
            # manageable from the certificates page, which this provider has no UI of its own for.
            managed_servers.append(first_server)
            # In the file-priority branch these are still Paths — check_cert() reads them into
            # bytes only inside its own scope — and the inventory API takes PEM bytes.
            import_err, _ = JOB.db.import_certificate(
                name=first_server,
                description="Managed by the custom certificate provider",
                source="customcert",
                certificate_pem=cert_file.read_bytes() if isinstance(cert_file, Path) else cert_file,
                private_key_pem=key_file.read_bytes() if isinstance(key_file, Path) else key_file,
                service_ids=[first_server],
                primary=True,
                renewal_metadata={"managed_by": "customcert"},
            )
            if import_err:
                LOGGER.error(f"Could not add {first_server}'s certificate to the inventory : {import_err}")

            if need_reload:
                LOGGER.info(f"Detected change in {first_server}'s certificate")
                status = 1
                continue

            LOGGER.info(f"No change in {first_server}'s certificate")

    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)

    # Services this provider no longer covers must lose their attachment, otherwise the
    # inventory would keep serving a certificate whose setting has just been turned off.
    if sync_err := JOB.db.sync_managed_attachments("customcert", managed_servers):
        LOGGER.error(f"Could not sync the custom certificate attachments : {sync_err}")

    # Never overwrite a status the service loop already set. Exit 1 is the ONLY thing that ships
    # the cache to the instances and asks for a reload (src/worker/tasks.py), so promoting a 2 over
    # a 1 would silently drop a delivery -- either a service certificate that genuinely changed, or
    # this branch's own withdrawal. The refusal is already loud in the log and, on its own, still
    # reaches the exit code through this line.
    if status == 0:
        status = default_server_status
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running custom-cert.py :\n{e}")

sys_exit(status)
