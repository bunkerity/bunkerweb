from logging import warning
from typing import List, Literal, Optional, Tuple

from pydantic import field_validator, model_validator

from .action import ActionBase, ActionData


class RedisData(ActionData):
    port: int = 6379
    password: Optional[str] = None
    db: Optional[int] = None
    tls: bool = False
    tls_port: int = 6379
    user: Optional[Tuple[str, str]] = None

    sentinel: bool = False
    sentinel_port: Optional[int] = None
    sentinel_master: str = "bw-master"
    sentinel_user: Optional[Tuple[str, str]] = None
    sentinel_type: Literal["master", "slave"] = "slave"

    query: str
    result: Optional[str] = None
    keys: Optional[List[str]] = None

    valkey: bool = False

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        if v:
            warning("The URL property is only a dummy value, it won't be used in the tests.")
        return v

    @model_validator(mode="after")
    def check_fields(self):
        if self.tls:
            assert self.tls_port, "TLS port is required"

        if self.sentinel:
            assert not self.user, "User is not allowed with Sentinel"
            assert self.sentinel_master, "Sentinel master is required"

            if self.sentinel_port is None:
                self.sentinel_port = 26479 if self.valkey else 26379

        if not any((self.result, self.keys)):
            raise ValueError("At least one of result or keys is required")

        if self.db is None:
            self.db = 0 if self.valkey else 1

        return self


class RedisBase(ActionBase, RedisData):
    type: Literal["redis"] = "redis"


class Redis(RedisBase):
    Docker: Optional[RedisData] = None
    Linux: Optional[RedisData] = None
    Autoconf: Optional[RedisData] = None
    Kubernetes: Optional[RedisData] = None
    All_in_one: Optional[RedisData] = None


__all__ = ("Redis",)
