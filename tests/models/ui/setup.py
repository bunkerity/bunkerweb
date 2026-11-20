from typing import Dict, Literal, Optional

from pydantic import model_validator

from models.ui.step_base import StepBase


class Setup(StepBase):
    type: Literal["setup"] = "setup"
    admin_username: str
    admin_email: str = ""
    admin_password: str

    server_name: str

    auto_lets_encrypt: bool = False
    lets_encrypt_staging: bool = False
    lets_encrypt_wildcard: bool = False
    lets_encrypt_disable_psl: bool = True
    email_lets_encrypt: str = ""
    lets_encrypt_challenge: Literal["http", "dns"] = "http"
    lets_encrypt_dns_provider: Optional[
        Literal[
            "bunny",
            "cloudns",
            "cloudflare",
            "desec",
            "digitalocean",
            "domainoffensive",
            "domeneshop",
            "dnsimple",
            "dnsmadeeasy",
            "duckdns",
            "dynu",
            "gandi",
            "gehirn",
            "godaddy",
            "google",
            "hetzner",
            "infomaniak",
            "ionos",
            "linode",
            "luadns",
            "njalla",
            "nsone",
            "ovh",
            "pdns",
            "rfc2136",
            "route53",
            "sakuracloud",
            "scaleway",
            "transip",
        ]
    ] = None
    lets_encrypt_profile: Literal["classic", "tlsserver", "shortlived"] = "classic"
    lets_encrypt_custom_profile: str = ""
    lets_encrypt_dns_propagation: Optional[str] = None
    lets_encrypt_dns_credential_items: Optional[Dict[str, str]] = None

    ui_host: Optional[str] = None
    ui_url: str = "/"

    use_real_ip: bool = False
    use_proxy_protocol: bool = False
    real_ip_recursive: bool = True
    real_ip_header: str = "X-Forwarded-For"
    real_ip_from: str = "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    real_ip_from_urls: str = ""

    use_custom_ssl: bool = False
    custom_ssl_cert_priority: Literal["file", "data"] = "file"
    custom_ssl_cert: str = ""
    custom_ssl_key: str = ""
    custom_ssl_cert_data: str = ""
    custom_ssl_key_data: str = ""

    @model_validator(mode="after")
    def check_fields(self):
        if self.lets_encrypt_challenge == "dns":
            if not self.lets_encrypt_dns_provider:
                raise ValueError("lets_encrypt_dns_provider must be set when lets_encrypt_challenge is dns")
            if not self.lets_encrypt_dns_credential_items:
                raise ValueError("lets_encrypt_dns_credential_items must be set when lets_encrypt_challenge is dns")

        if self.use_custom_ssl and (not self.custom_ssl_cert or not self.custom_ssl_key) and (not self.custom_ssl_cert_data or not self.custom_ssl_key_data):
            raise ValueError("custom_ssl_cert and custom_ssl_key or custom_ssl_cert_data and custom_ssl_key_data must be set when use_custom_ssl is True")

        if self.admin_email and self.email_lets_encrypt is None:
            self.email_lets_encrypt = self.admin_email

        return self


__all__ = ("Setup",)
