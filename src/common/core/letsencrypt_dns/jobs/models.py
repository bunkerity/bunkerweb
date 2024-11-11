# -*- coding: utf-8 -*-
from os.path import sep
from pathlib import Path
from sys import path as sys_path
from typing import Literal, Optional

LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt_dns")

PYTHON_PATH = LIB_PATH.joinpath("python")
if PYTHON_PATH.as_posix() not in sys_path:
    sys_path.append(PYTHON_PATH.as_posix())

from pydantic import BaseModel, ConfigDict


class Provider(BaseModel):
    """Base class for DNS providers."""

    # ? Allow extra fields in the model in case there are additional fields that are not defined in the model.
    model_config = ConfigDict(extra="allow")

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials to be written to a file."""
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}).items()).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["ini"]:
        """Return the file type that the credentials should be written to."""
        return "ini"


class CloudflareProvider(Provider):
    dns_cloudflare_api_token: str


class DigitalOceanProvider(Provider):
    dns_digitalocean_token: str


class GoogleProvider(Provider):
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
        """Return the formatted credentials to be written to a file."""
        return self.model_dump_json(indent=2, exclude={"file_type"}).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["json"]:
        """Return the file type that the credentials should be written to."""
        return "json"


class LinodeProvider(Provider):
    dns_linode_key: str
    dns_linode_version: str = "4"


class OvhProvider(Provider):
    dns_ovh_endpoint: str = "ovh-eu"
    dns_ovh_application_key: str
    dns_ovh_application_secret: str
    dns_ovh_consumer_key: str


class Rfc2136Provider(Provider):
    dns_rfc2136_server: str
    dns_rfc2136_port: Optional[str] = None
    dns_rfc2136_name: str
    dns_rfc2136_secret: str
    dns_rfc2136_algorithm: str = "HMAC-MD5"
    dns_rfc2136_sign_query: str = "false"

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials to be written to a file."""
        # ? Return the formatted credentials as a string. The default values are excluded as they are not required.
        return "\n".join(f"{key} = {value}" for key, value in self.model_dump(exclude={"file_type"}, exclude_defaults=True).items()).encode("utf-8")


class Route53Provider(Provider):
    aws_access_key_id: str
    aws_secret_access_key: str

    def get_formatted_credentials(self) -> bytes:
        """Return the formatted credentials to be written to a file."""
        # ? Return the formatted credentials as a string. The keys are converted to uppercase and the values are represented as a string.
        return "\n".join(f"{key.upper()}={value!r}" for key, value in self.model_dump(exclude={"file_type"}).items()).encode("utf-8")

    @staticmethod
    def get_file_type() -> Literal["env"]:
        """Return the file type that the credentials should be written to."""
        return "env"


class ScalewayProvider(Provider):
    dns_scaleway_application_token: str


__ALL__ = (
    "CloudflareProvider",
    "DigitalOceanProvider",
    "GoogleProvider",
    "LinodeProvider",
    "OvhProvider",
    "Rfc2136Provider",
    "Route53Provider",
    "ScalewayProvider",
)
