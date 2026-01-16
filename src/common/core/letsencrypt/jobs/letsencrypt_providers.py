# -*- coding: utf-8 -*-
from pathlib import Path
from sys import path as sys_path
from typing import List, Literal, Optional

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

    @staticmethod
    def get_extra_args() -> List[str]:
        """Return additional arguments for the provider."""
        return []


class BunnyNetProvider(Provider):
    """BunnyNet DNS provider."""

    dns_bunny_api_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_bunny_api_key": ("dns_bunny_api_key", "bunnynet_api_key", "api_key"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["-a", "dns-bunny"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-cloudflare"]


class DesecProvider(Provider):
    """deSEC DNS provider."""

    dns_desec_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_desec_token": ("dns_desec_token", "desec_token", "token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["-a", "dns-desec"]


class DigitalOceanProvider(Provider):
    """DigitalOcean DNS provider."""

    dns_digitalocean_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_digitalocean_token": ("dns_digitalocean_token", "digitalocean_token", "token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-digitalocean"]


class DomainOffensiveProvider(Provider):
    """Domain Offensive DNS provider."""

    dns_domainoffensive_api_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_domainoffensive_api_token": ("dns_domainoffensive_api_token", "domainoffensive_api_token", "api_token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--authenticator", "dns-domainoffensive"]


class DomeneshopProvider(Provider):
    """Domeneshop DNS provider."""

    dns_domeneshop_token: str
    dns_domeneshop_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_domeneshop_token": ("dns_domeneshop_token", "domeneshop_token", "token"),
            "dns_domeneshop_secret": ("dns_domeneshop_secret", "domeneshop_secret", "secret"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--authenticator", "dns-domeneshop"]


class DnsimpleProvider(Provider):
    """DNSimple DNS provider."""

    dns_dnsimple_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsimple_token": ("dns_dnsimple_token", "dnsimple_token", "token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-dnsimple"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-dnsmadeeasy"]


class DuckDnsProvider(Provider):
    """DuckDNS DNS provider."""

    dns_duckdns_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_duckdns_token": ("dns_duckdns_token", "duckdns_token", "token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--authenticator", "dns-duckdns"]


class DynuProvider(Provider):
    """Dynu DNS provider."""

    dns_dynu_auth_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dynu_auth_token": ("dns_dynu_auth_token", "dynu_auth_token", "auth_token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--authenticator", "dns-dynu"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-gehirn"]


class GoDaddyProvider(Provider):
    """GoDaddy DNS provider."""

    dns_godaddy_key: str
    dns_godaddy_secret: str
    dns_godaddy_ttl: str = "600"

    _validate_aliases = alias_model_validator(
        {
            "dns_godaddy_key": ("dns_godaddy_key", "godaddy_key", "key"),
            "dns_godaddy_secret": ("dns_godaddy_secret", "godaddy_secret", "secret"),
            "dns_godaddy_ttl": ("dns_godaddy_ttl", "godaddy_ttl", "ttl"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--authenticator", "dns-godaddy"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-google"]


class InfomaniakProvider(Provider):
    """Infomaniak DNS provider."""

    dns_infomaniak_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_infomaniak_token": ("dns_infomaniak_token", "infomaniak_token", "token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["-a", "dns-infomaniak", "--rsa-key-size", "4096"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["-a", "dns-ionos", "--rsa-key-size", "4096"]


class LinodeProvider(Provider):
    """Linode DNS provider."""

    dns_linode_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_linode_key": ("dns_linode_key", "linode_key", "key"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-linode"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-luadns"]


class NjallaProvider(Provider):
    """Njalla DNS provider."""

    dns_njalla_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_njalla_token": ("dns_njalla_token", "njalla_token", "token", "api_token", "auth_token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["-a", "dns-njalla"]


class NSOneProvider(Provider):
    """NS1 DNS provider."""

    dns_nsone_api_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_nsone_api_key": ("dns_nsone_api_key", "nsone_api_key", "api_key"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-nsone"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-ovh"]


class PowerdnsProvider(Provider):
    """PowerDNS DNS provider."""

    dns_pdns_endpoint: str
    dns_pdns_api_key: str
    dns_pdns_server_id: str = "localhost"
    dns_pdns_disable_notify: str = "false"

    _validate_aliases = alias_model_validator(
        {
            "dns_pdns_endpoint": ("dns_pdns_endpoint", "pdns_endpoint", "endpoint"),
            "dns_pdns_api_key": ("dns_pdns_api_key", "pdns_api_key", "api_key"),
            "dns_pdns_server_id": ("dns_pdns_server_id", "pdns_server_id", "server_id"),
            "dns_pdns_disable_notify": ("dns_pdns_disable_notify", "pdns_disable_notify", "disable_notify"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--authenticator", "dns-pdns"]


class Rfc2136Provider(Provider):
    """RFC 2136 DNS provider."""

    dns_rfc2136_server: str
    dns_rfc2136_port: Optional[str] = None
    dns_rfc2136_name: str
    dns_rfc2136_secret: str
    dns_rfc2136_algorithm: str = "HMAC-MD5"
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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-rfc2136"]


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
        """Return the formatted credentials in environment variable format, with [default] at the top."""
        lines = ["[default]"]
        for key, value in self.model_dump(exclude={"file_type"}).items():
            lines.append(f"{key}={value}")
        return "\n".join(lines).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["env"]:
        """Return the file type that the credentials should be written to."""
        return "env"

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-route53"]


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

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["--dns-sakuracloud"]


class ScalewayProvider(Provider):
    """Scaleway DNS provider."""

    dns_scaleway_application_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_scaleway_application_token": ("dns_scaleway_application_token", "scaleway_application_token", "application_token"),
        }
    )

    @staticmethod
    def get_extra_args() -> dict:
        """Return additional arguments for the provider."""
        return ["-a", "dns-scaleway"]
