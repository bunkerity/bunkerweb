from logging import warning
from pydantic import BaseModel, field_validator, model_validator
from ipaddress import ip_address
from re import compile as re_compile, match
from urllib.parse import urlsplit
from typing import Any, Dict, Literal, Optional, Set, Tuple


URL_IN_TEXT = re_compile(r"https?://[^\s'\"`]+")


def check_runner_host(value: str) -> None:
    """Raise if `value` is a URL the RUNNER dials whose host cannot resolve deterministically.

    A bare container name does not: the suite expects dnsmasq to answer it, but a workstation asks
    its own resolver, and a DNS `search` domain turns the bare name into an FQDN in some other zone.
    On the machine this was written on that zone is a WILDCARD, so *every* bare name resolves to a
    real host -- `custom-api`, `app1` and `definitely-not-a-real-host-xyz9` all return the same
    address. Nothing can ever NXDOMAIN, so the mistake never looks like DNS: it looks like a
    ten-second connect timeout on an unrelated action. That cost `bunkernet` a full run before
    anyone read the resolver.

    Deterministic hosts only: a dotted name (`www.example.com` comes from /etc/hosts), an IP
    literal, or `localhost`. Reach a container by its PUBLISHED port on loopback instead -- which is
    what the Kubernetes overrides in bunkernet.yml already did.

    Container-side settings are NOT checked and must not be: `BUNKERNET_SERVER`,
    `WHITELIST_IP_URLS`, `CROWDSEC_API` and friends live in `config`, are resolved inside the
    network where dnsmasq is authoritative, and a bare name there is correct.
    """
    if "%" in value:  # ui specs template their base URL in later
        return
    host = urlsplit(value).hostname  # strips userinfo, so `user:pass@host` cannot be misread
    if not host or host == "localhost" or "." in host:
        return
    try:
        ip_address(host)
    except ValueError:
        raise ValueError(
            f"url host {host!r} is a bare name the runner cannot resolve deterministically; "
            "use a *.example.com name or the published port on 127.0.0.1"
        )


def check_embedded_runner_urls(text: str) -> None:
    """Same rule, for a runner-side field that *embeds* URLs rather than being one.

    `tool` arguments and `script` argv are executed on the runner, so a bare name there fails
    exactly like one in `url` -- and with no `url` field involved for that guard to see. This is the
    blind spot the first version shipped with: `crowdsec.yml` passes
    `'http://127.0.0.1 -H "Host: www.example.com" -f'`, which was loopback by the author's choice
    and by nothing enforcing it.
    """
    for match_ in URL_IN_TEXT.finditer(text or ""):
        check_runner_host(match_.group(0))


class ActionData(BaseModel):
    bw_version: str = "tests"  # ? The version of BunkerWeb to use for the action
    config: Dict[str, Optional[str]] = {}  # ? If config value is None, then the config is not set
    labels: Dict[str, Optional[str]] = {"bunkerweb.SERVER_NAME": "www.example.com"}  # ? If label value is None, then the label is not set
    annotations: Dict[str, Optional[str]] = {"bunkerweb.io/SERVER_NAME": "www.example.com"}  # ? If annotation value is None, then the annotation is not set
    delay: float = 0.0
    timeout: int = 120
    retries: int = 0  # ? If retries is 0, then no retries are made Else, retries are made until the limit is reached or the action is successful
    url: str = ""
    headers: Dict[str, Optional[str]] = {}  # ? If headers value is None, then the header is not sent
    method: Literal["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    log: str = ""  # ? If log is not empty, then the log must be present in BunkerWeb logs
    not_log: str = ""  # ? If not_log is not empty, then the log must not be present in BunkerWeb logs
    log_from: Literal["bunkerweb", "controller", "scheduler", "database"] = "bunkerweb"
    auth: Optional[Tuple[str, str]] = None
    body: Optional[str] = None
    body_length: int = 0  # ? If body_length is 0, then no body is sent Else, will send the letter "a" body_length times
    client_cert: Optional[str] = None  # ? Absolute path to a client certificate (PEM) for mutual TLS tests
    client_cert_key: Optional[str] = None  # ? Absolute path to the private key associated with the client certificate
    follow_redirects: bool = False
    verify_ssl: bool = True
    http2: bool = False
    raise_for_status: bool = True
    full_clean: bool = False
    restart_stack: bool = True
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = "sqlite"
    repeat: int = 0  # ? The number of times to repeat the action
    cooldown: float = 0.0  # ? The cooldown time (in seconds) between tests
    crowdsec_config: Dict[str, Optional[str]] = {}  # ? If crowdsec_config value is None, then the config is not set
    api: Dict[str, Optional[str]] = {}  # ? If api value is None, then the api setting is not set
    services: Dict[str, Any] = {}  # ? Extra Docker Compose services required by the action

    @model_validator(mode="after")
    def check_fields(self):
        if self.url.startswith("http://") and self.http2:
            raise ValueError("http2 must be False if the URL is not HTTPS as HTTP/2 is not supported over HTTP yet")
        elif self.body and self.method in ("GET", "HEAD"):
            raise ValueError("body must be None if the method is GET or HEAD")
        elif self.body_length and self.method in ("GET", "HEAD"):
            raise ValueError("body_length must be 0 if the method is GET or HEAD")

        if not self.restart_stack:
            warning(
                "The stack will not be restarted after this action is executed, therefore, the potential configuration changes made by the next action will not be applied"
            )

        return self

    @field_validator("labels")
    @classmethod
    def check_labels(cls, v: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        for label in v.copy():
            v[f"bunkerweb.{v[label].replace('bunkerweb.', '').upper()}"] = v.pop(label)
        return v

    @field_validator("annotations")
    @classmethod
    def check_annotations(cls, v: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        for annotation in v.copy():
            if not annotation.startswith("bunkerweb.io/"):
                v[f"bunkerweb.io/{v[annotation]}"] = v.pop(annotation)
        return v

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        if not v:
            raise ValueError("url must not be empty")

        check_runner_host(v)
        return v

    @field_validator("headers")
    @classmethod
    def check_headers(cls, v: Dict[str, str]) -> Dict[str, str]:
        for header in v:
            if not match(r"^[\w-]+$", header):
                raise ValueError("header_name must be a valid HTTP header")
        return v


class ActionBase(ActionData):
    type: str
    integrations: Set[Literal["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"]] = {"Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"}


class Action(ActionBase):
    Docker: Optional[ActionData] = None
    Linux: Optional[ActionData] = None
    Autoconf: Optional[ActionData] = None
    Kubernetes: Optional[ActionData] = None
    All_in_one: Optional[ActionData] = None


__all__ = ("Action",)
