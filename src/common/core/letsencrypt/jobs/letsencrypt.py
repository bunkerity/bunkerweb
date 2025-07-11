# -*- coding: utf-8 -*-
from pathlib import Path
from sys import path as sys_path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

# Define paths
LIB_PATH = Path("/var/lib/bunkerweb/letsencrypt")
PYTHON_PATH = LIB_PATH / "python"

# Add to sys.path if not already present
python_path_str = PYTHON_PATH.as_posix()
if python_path_str not in sys_path:
    sys_path.append(python_path_str)


def alias_model_validator(field_map: dict):
    """Factory function for creating a `model_validator` for alias mapping."""

    def validator(cls, values):
        for field, aliases in field_map.items():
            for alias in aliases:
                if alias in values:
                    values[field] = values[alias]
                    break
        return values

    return model_validator(mode="before")(validator)


class Provider(BaseModel):
    """Base class for DNS providers."""

    model_config = ConfigDict(extra="ignore")

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials to be written to a file."""
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}).items()).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["ini"]:
        """Return the file type that the credentials should be written to."""
        return "ini"


class CloudflareProvider(Provider):
    """Cloudflare DNS provider."""

    dns_cloudflare_api_token: str = ""
    dns_cloudflare_email: str = ""
    dns_cloudflare_api_key: str = ""

    _validate_aliases = alias_model_validator(
        {
            "dns_cloudflare_api_token": ("dns_cloudflare_api_token", "cloudflare_api_token", "api_token"),
            "dns_cloudflare_email": ("dns_cloudflare_email", "cloudflare_email", "email"),
            "dns_cloudflare_api_key": ("dns_cloudflare_api_key", "cloudflare_api_key", "api_key"),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials, excluding defaults."""
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}, exclude_defaults=True).items()).encode("utf-8")

    @model_validator(mode="after")
    def validate_cloudflare_credentials(self):
        """Validate Cloudflare credentials."""
        if not self.dns_cloudflare_api_token and not (self.dns_cloudflare_email and self.dns_cloudflare_api_key):
            raise ValueError("Either 'dns_cloudflare_api_token' or both 'dns_cloudflare_email' and 'dns_cloudflare_api_key' must be provided.")
        return self


class DesecProvider(Provider):
    """deSEC DNS provider."""

    dns_desec_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_desec_token": ("dns_desec_token", "desec_token", "token"),
        }
    )


class DigitalOceanProvider(Provider):
    """DigitalOcean DNS provider."""

    dns_digitalocean_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_digitalocean_token": ("dns_digitalocean_token", "digitalocean_token", "token"),
        }
    )


class DnsimpleProvider(Provider):
    """DNSimple DNS provider."""

    dns_dnsimple_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsimple_token": ("dns_dnsimple_token", "dnsimple_token", "token"),
        }
    )


class DnsMadeEasyProvider(Provider):
    """DNS Made Easy DNS provider."""

    dns_dnsmadeeasy_api_key: str
    dns_dnsmadeeasy_secret_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsmadeeasy_api_key": ("dns_dnsmadeeasy_api_key", "dnsmadeeasy_api_key", "api_key"),
            "dns_dnsmadeeasy_secret_key": ("dns_dnsmadeeasy_secret_key", "dnsmadeeasy_secret_key", "secret_key"),
        }
    )


class GehirnProvider(Provider):
    """Gehirn DNS provider."""

    dns_gehirn_api_token: str
    dns_gehirn_api_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_gehirn_api_token": ("dns_gehirn_api_token", "gehirn_api_token", "api_token"),
            "dns_gehirn_api_secret": ("dns_gehirn_api_secret", "gehirn_api_secret", "api_secret"),
        }
    )


class GoogleProvider(Provider):
    """Google Cloud DNS provider."""

    type: str = "service_account"
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://accounts.google.com/o/oauth2/token"
    auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url: str

    _validate_aliases = alias_model_validator(
        {
            "type": ("type", "google_type", "dns_google_type"),
            "project_id": ("project_id", "google_project_id", "dns_google_project_id"),
            "private_key_id": ("private_key_id", "google_private_key_id", "dns_google_private_key_id"),
            "private_key": ("private_key", "google_private_key", "dns_google_private_key"),
            "client_email": ("client_email", "google_client_email", "dns_google_client_email"),
            "client_id": ("client_id", "google_client_id", "dns_google_client_id"),
            "auth_uri": ("auth_uri", "google_auth_uri", "dns_google_auth_uri"),
            "token_uri": ("token_uri", "google_token_uri", "dns_google_token_uri"),
            "auth_provider_x509_cert_url": ("auth_provider_x509_cert_url", "google_auth_provider_x509_cert_url", "dns_google_auth_provider_x509_cert_url"),
            "client_x509_cert_url": ("client_x509_cert_url", "google_client_x509_cert_url", "dns_google_client_x509_cert_url"),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials in JSON format."""
        return self.model_dump_json(indent=2, exclude={"file_type"}).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["json"]:
        """Return the file type that the credentials should be written to."""
        return "json"


class InfomaniakProvider(Provider):
    """Infomaniak DNS provider."""

    dns_infomaniak_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_infomaniak_token": ("dns_infomaniak_token", "infomaniak_token", "token"),
        }
    )


class IonosProvider(Provider):
    """Ionos DNS provider."""

    dns_ionos_prefix: str
    dns_ionos_secret: str
    dns_ionos_endpoint: str = "https://api.hosting.ionos.com"

    _validate_aliases = alias_model_validator(
        {
            "dns_ionos_prefix": ("dns_ionos_prefix", "ionos_prefix", "prefix"),
            "dns_ionos_secret": ("dns_ionos_secret", "ionos_secret", "secret"),
            "dns_ionos_endpoint": ("dns_ionos_endpoint", "ionos_endpoint", "endpoint"),
        }
    )


class LinodeProvider(Provider):
    """Linode DNS provider."""

    dns_linode_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_linode_key": ("dns_linode_key", "linode_key", "key"),
        }
    )


class LuaDnsProvider(Provider):
    """LuaDns DNS provider."""

    dns_luadns_email: str
    dns_luadns_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_luadns_email": ("dns_luadns_email", "luadns_email", "email"),
            "dns_luadns_token": ("dns_luadns_token", "luadns_token", "token"),
        }
    )


class NSOneProvider(Provider):
    """NS1 DNS provider."""

    dns_nsone_api_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_nsone_api_key": ("dns_nsone_api_key", "nsone_api_key", "api_key"),
        }
    )


class OvhProvider(Provider):
    """OVH DNS provider."""

    dns_ovh_endpoint: str = "ovh-eu"
    dns_ovh_application_key: str
    dns_ovh_application_secret: str
    dns_ovh_consumer_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_ovh_endpoint": ("dns_ovh_endpoint", "ovh_endpoint", "endpoint"),
            "dns_ovh_application_key": ("dns_ovh_application_key", "ovh_application_key", "application_key"),
            "dns_ovh_application_secret": ("dns_ovh_application_secret", "ovh_application_secret", "application_secret"),
            "dns_ovh_consumer_key": ("dns_ovh_consumer_key", "ovh_consumer_key", "consumer_key"),
        }
    )


class Rfc2136Provider(Provider):
    """RFC 2136 DNS provider."""

    dns_rfc2136_server: str
    dns_rfc2136_port: Optional[str] = None
    dns_rfc2136_name: str
    dns_rfc2136_secret: str
    dns_rfc2136_algorithm: str = "HMAC-SHA512"
    dns_rfc2136_sign_query: str = "false"

    _validate_aliases = alias_model_validator(
        {
            "dns_rfc2136_server": ("dns_rfc2136_server", "rfc2136_server", "server"),
            "dns_rfc2136_port": ("dns_rfc2136_port", "rfc2136_port", "port"),
            "dns_rfc2136_name": ("dns_rfc2136_name", "rfc2136_name", "name"),
            "dns_rfc2136_secret": ("dns_rfc2136_secret", "rfc2136_secret", "secret"),
            "dns_rfc2136_algorithm": ("dns_rfc2136_algorithm", "rfc2136_algorithm", "algorithm"),
            "dns_rfc2136_sign_query": ("dns_rfc2136_sign_query", "rfc2136_sign_query", "sign_query"),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials, excluding defaults."""
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}, exclude_defaults=True).items()).encode("utf-8")


class Route53Provider(Provider):
    """AWS Route 53 DNS provider."""

    aws_access_key_id: str
    aws_secret_access_key: str

    _validate_aliases = alias_model_validator(
        {
            "aws_access_key_id": ("aws_access_key_id", "dns_aws_access_key_id", "access_key_id"),
            "aws_secret_access_key": ("aws_secret_access_key", "dns_aws_secret_access_key", "secret_access_key"),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials in environment variable format."""
        return "\n".join(f"{key.upper()}={value!r}" for key, value in self.model_dump(exclude={"file_type"}).items()).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["env"]:
        """Return the file type that the credentials should be written to."""
        return "env"


class SakuraCloudProvider(Provider):
    """Sakura Cloud DNS provider."""

    dns_sakuracloud_api_token: str
    dns_sakuracloud_api_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_sakuracloud_api_token": ("dns_sakuracloud_api_token", "sakuracloud_api_token", "api_token"),
            "dns_sakuracloud_api_secret": ("dns_sakuracloud_api_secret", "sakuracloud_api_secret", "api_secret"),
        }
    )


class ScalewayProvider(Provider):
    """Scaleway DNS provider."""

    dns_scaleway_application_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_scaleway_application_token": ("dns_scaleway_application_token", "scaleway_application_token", "application_token"),
        }
    )


class NjallaProvider(Provider):
    """Njalla DNS provider."""

    dns_njalla_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_njalla_token": ("dns_njalla_token", "njalla_token", "token", "api_token", "auth_token"),
        }
    )


class WildcardCertificate:
    """Represents a wildcard certificate configuration."""

    def __init__(self, group_name: str, email: str, staging: bool, domains: List[str], provider: str, profile: str, max_retries: int = 0):
        self.group_name = group_name
        self.email = email
        self.staging = staging
        self.domains = set(domains)
        self.provider = provider
        self.profile = profile
        self.max_retries = max_retries
        self._wildcard_domains = None

    @property
    def wildcard_domains(self) -> List[str]:
        """Get the wildcard domains for this certificate."""
        if self._wildcard_domains is None:
            self._wildcard_domains = self._generate_wildcards()
        return self._wildcard_domains

    @property
    def cert_name(self) -> str:
        """Get the certificate name (base domain from the first domain)."""
        if not self.domains:
            return self.group_name
        # Use the base domain from the first domain as cert name
        first_domain = next(iter(self.domains))
        return WildcardGenerator.get_base_domain(first_domain)

    @property
    def domains_str(self) -> str:
        """Get domains as comma-separated string for certbot."""
        return ",".join(sorted(self.wildcard_domains, key=lambda x: (x[0] != "*", x)))

    def _generate_wildcards(self) -> List[str]:
        """Generate wildcard patterns from the domains."""
        wildcards = set()
        for domain in self.domains:
            domain = domain.strip()
            if not domain:
                continue

            parts = domain.split(".")
            if len(parts) > 2:
                # For subdomains, create wildcard for base domain
                base_domain = ".".join(parts[1:])
                wildcards.add(f"*.{base_domain}")
                wildcards.add(base_domain)
            else:
                # For top-level domains, just add as-is
                wildcards.add(domain)

        return sorted(wildcards, key=lambda x: (x[0] != "*", x))

    def add_domains(self, domains: List[str]):
        """Add more domains to this certificate."""
        for domain in domains:
            if domain := domain.strip():
                self.domains.add(domain)
        # Reset cached wildcard domains
        self._wildcard_domains = None


class WildcardGenerator:
    """Manages wildcard certificate configurations."""

    def __init__(self):
        self._certificates: Dict[str, WildcardCertificate] = {}

    def add_certificate(self, group_name: str, domains: List[str], email: str, staging: bool, provider: str, profile: str, max_retries: int = 0):
        """
        Add or update a wildcard certificate configuration.

        Args:
            group_name: Unique identifier for this certificate group
            domains: List of domains for this certificate
            email: Contact email for the certificate
            staging: Whether to use staging environment
            provider: DNS provider name
            profile: Certificate profile (classic, tlsserver, shortlived)
            max_retries: Maximum number of retry attempts
        """
        if group_name in self._certificates:
            # Update existing certificate with new domains
            self._certificates[group_name].add_domains(domains)
        else:
            # Create new certificate configuration
            self._certificates[group_name] = WildcardCertificate(
                group_name=group_name, email=email, staging=staging, domains=domains, provider=provider, profile=profile, max_retries=max_retries
            )

    def get_certificates(self) -> List[WildcardCertificate]:
        """Get all wildcard certificates that need to be generated."""
        return [cert for cert in self._certificates.values() if cert.domains]

    def get_certificate_by_group(self, group_name: str) -> Optional[WildcardCertificate]:
        """Get a specific certificate by group name."""
        return self._certificates.get(group_name)

    def has_certificates(self) -> bool:
        """Check if there are any certificates to generate."""
        return any(cert.domains for cert in self._certificates.values())

    def clear(self):
        """Clear all certificate configurations."""
        self._certificates.clear()

    def get_certificate_by_base_domain(self, domain: str) -> Optional[WildcardCertificate]:
        """Get certificate that would cover the given domain."""
        base_domain = self.get_base_domain(domain)
        for cert in self._certificates.values():
            if cert.cert_name == base_domain:
                return cert
        return None

    # Legacy compatibility methods - no longer parse group names
    def extend(self, group: str, domains: List[str], email: str, staging: bool = False):
        """Legacy method for backward compatibility - now requires provider/profile to be set separately."""
        if group not in self._certificates:
            # Default values when we can't parse from group name
            self.add_certificate(group, domains, email, staging, "unknown", "classic")
        else:
            self._certificates[group].add_domains(domains)

    def get_wildcards(self) -> Dict[str, Dict[str, str]]:
        """Legacy method for backward compatibility."""
        result = {}
        for cert in self._certificates.values():
            if not cert.domains:
                continue

            result[cert.group_name] = {"email": cert.email, "staging" if cert.staging else "prod": cert.domains_str}
        return result

    @staticmethod
    def extract_wildcards_from_domains(domains: List[str]) -> List[str]:
        """
        Generate wildcard patterns from a list of domains.

        Args:
            domains: List of domains to process

        Returns:
            List of extracted wildcard domains
        """
        wildcards = set()
        for domain in domains:
            parts = domain.split(".")
            # Generate wildcards for subdomains
            if len(parts) > 2:
                base_domain = ".".join(parts[1:])
                wildcards.add(f"*.{base_domain}")
                wildcards.add(base_domain)
            else:
                # Just add the domain for top-level domains
                wildcards.add(domain)

        # Sort with wildcards first
        return sorted(wildcards, key=lambda x: x[0] != "*")

    @staticmethod
    def get_base_domain(domain: str) -> str:
        """
        Extract the base domain from a domain name.

        Args:
            domain: Input domain name

        Returns:
            Base domain (without wildcard prefix if present)
        """
        return domain.lstrip("*.")

    @staticmethod
    def create_group_name(domain: str, provider: str, challenge_type: str, staging: bool, content_hash: str, profile: str = "classic") -> str:
        """
        Generate a consistent group name for wildcards.

        Args:
            domain: The domain name
            provider: DNS provider name or 'http' for HTTP challenge
            challenge_type: Challenge type (dns or http)
            staging: Whether this is for staging environment
            content_hash: Hash of credential content
            profile: Certificate profile (classic, tlsserver or shortlived)

        Returns:
            A formatted group name string
        """
        # Extract base domain and format it for the group name
        base_domain = WildcardGenerator.get_base_domain(domain).replace(".", "-")
        env = "staging" if staging else "prod"

        # Use provider name for DNS challenge, otherwise use 'http'
        challenge_identifier = provider if challenge_type == "dns" else "http"

        return f"{challenge_identifier}_{env}_{profile}_{base_domain}_{content_hash}"
