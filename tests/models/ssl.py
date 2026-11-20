from pydantic import field_validator
from typing import Literal, Optional, Set

from .action import ActionBase, ActionData


class SslData(ActionData):
    ssl_protocols: Set[Literal["SSLv2", "SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"]] = {"TLSv1.2", "TLSv1.3"}
    client_ssl_cipher: Optional[str] = None  # If None, the ciphers won't be enforced
    ssl_cipher: Optional[str] = None  # If None, the ciphers won't be checked
    ssl_expiration: int = 365
    ssl_subject: str = "/CN=www.example.com/"
    ssl_algorithm: Literal["ec-prime256v1", "ec-secp384r1", "rsa-2048", "rsa-4096"] = "ec-secp384r1"
    success: bool = True  # Whether the SSL connection is expected to succeed

    @field_validator("url", check_fields=False)
    @classmethod
    def check_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("The URL must be HTTPS when using the ssl type")
        return v


class SslBase(ActionBase, SslData):
    type: Literal["ssl"] = "ssl"


class Ssl(SslBase):
    Docker: Optional[SslData] = None
    Linux: Optional[SslData] = None
    Autoconf: Optional[SslData] = None
    Kubernetes: Optional[SslData] = None
    All_in_one: Optional[SslData] = None


__all__ = ("Ssl",)
