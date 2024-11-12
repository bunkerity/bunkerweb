# -*- coding: utf-8 -*-
from pathlib import Path
from sys import path as sys_path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict

# Define paths
LIB_PATH = Path("/var/lib/bunkerweb/letsencrypt")
PYTHON_PATH = LIB_PATH / "python"

# Add to sys.path if not already present
python_path_str = PYTHON_PATH.as_posix()
if python_path_str not in sys_path:
    sys_path.append(python_path_str)


class Provider(BaseModel):
    """Base class for DNS providers."""

    model_config = ConfigDict(extra="allow")

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials to be written to a file."""
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}).items()).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["ini"]:
        """Return the file type that the credentials should be written to."""
        return "ini"


class CloudflareProvider(Provider):
    """Cloudflare DNS provider."""

    dns_cloudflare_api_token: str


class DigitalOceanProvider(Provider):
    """DigitalOcean DNS provider."""

    dns_digitalocean_token: str


class DnsimpleProvider(Provider):
    """DNSimple DNS provider."""

    dns_dnsimple_token: str


class DnsMadeEasyProvider(Provider):
    """DNS Made Easy DNS provider."""

    dns_dnsmadeeasy_api_key: str
    dns_dnsmadeeasy_secret_key: str


class GehirnProvider(Provider):
    """Gehirn DNS provider."""

    dns_gehirn_api_token: str
    dns_gehirn_api_secret: str


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

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials in JSON format."""
        return self.model_dump_json(indent=2, exclude={"file_type"}).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["json"]:
        """Return the file type that the credentials should be written to."""
        return "json"


class LinodeProvider(Provider):
    """Linode DNS provider."""

    dns_linode_key: str
    dns_linode_version: str = "4"


class LuaDnsProvider(Provider):
    """LuaDns DNS provider."""

    dns_luadns_email: str
    dns_luadns_token: str


class NSOneProvider(Provider):
    """NS1 DNS provider."""

    dns_nsone_api_key: str


class OvhProvider(Provider):
    """OVH DNS provider."""

    dns_ovh_endpoint: str = "ovh-eu"
    dns_ovh_application_key: str
    dns_ovh_application_secret: str
    dns_ovh_consumer_key: str


class Rfc2136Provider(Provider):
    """RFC 2136 DNS provider."""

    dns_rfc2136_server: str
    dns_rfc2136_port: Optional[str] = None
    dns_rfc2136_name: str
    dns_rfc2136_secret: str
    dns_rfc2136_algorithm: str = "HMAC-MD5"
    dns_rfc2136_sign_query: str = "false"

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials, excluding defaults."""
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}, exclude_defaults=True).items()).encode("utf-8")


class Route53Provider(Provider):
    """AWS Route 53 DNS provider."""

    aws_access_key_id: str
    aws_secret_access_key: str

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


class ScalewayProvider(Provider):
    """Scaleway DNS provider."""

    dns_scaleway_application_token: str


class WildcardGenerator:
    def __init__(self):
        self.__domain_groups = {}
        self.__wildcards = {}

    def __generate_wildcards(self, staging: bool = False):
        self.__wildcards.clear()
        _type = "staging" if staging else "prod"

        # * Loop through all the domains and generate wildcards
        for group, types in self.__domain_groups.items():
            if group not in self.__wildcards:
                self.__wildcards[group] = {"staging": set(), "prod": set(), "email": types["email"]}
            for domain in types[_type]:
                parts = domain.split(".")
                # ? Only take subdomains into account for wildcards generation
                if len(parts) > 2:
                    suffix = ".".join(parts[1:])
                    # ? If the suffix is not already in the wildcards, add it
                    if suffix not in self.__wildcards[group][_type]:
                        self.__wildcards[group][_type].add(f"*.{suffix}")
                        self.__wildcards[group][_type].add(suffix)
                    continue

                # ? Add the raw domain to the wildcards
                self.__wildcards[group][_type].add(domain)

    def extend(self, group: str, domains: List[str], email: str, staging: bool = False):
        if group not in self.__domain_groups:
            self.__domain_groups[group] = {"staging": set(), "prod": set(), "email": email}
        for domain in domains:
            if domain := domain.strip():
                self.__domain_groups[group]["staging" if staging else "prod"].add(domain)
        self.__generate_wildcards(staging)

    def get_wildcards(self) -> Dict[str, Dict[Literal["staging", "prod", "email"], str]]:
        ret_data = {}
        for group, data in self.__wildcards.items():
            ret_data[group] = {"email": data["email"]}
            for _type, content in data.items():
                if _type in ("staging", "prod"):
                    # ? Sort domains while favoring wildcards first
                    ret_data[group][_type] = ",".join(sorted(content, key=lambda x: x[0] != "*"))
        return ret_data

    @staticmethod
    def get_wildcards_from_domains(domains: List[str]) -> List[str]:
        wildcards = set()
        for domain in domains:
            parts = domain.split(".")
            # ? Only take subdomains into account for wildcards generation
            if len(parts) > 2:
                suffix = ".".join(parts[1:])
                # ? If the suffix is not already in the wildcards, add it
                if suffix not in wildcards:
                    wildcards.add(f"*.{suffix}")
                    wildcards.add(suffix)
                continue

            # ? Add the raw domain to the wildcards
            wildcards.add(domain)
        return sorted(wildcards, key=lambda x: x[0] != "*")


__all__ = (
    "CloudflareProvider",
    "DigitalOceanProvider",
    "GoogleProvider",
    "LinodeProvider",
    "OvhProvider",
    "Rfc2136Provider",
    "Route53Provider",
    "ScalewayProvider",
)
