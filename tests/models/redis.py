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

    # Redis Cluster (tests/misc/docker/redis-cluster.yml): three masters published on
    # 127.0.0.1:cluster_port .. cluster_port + 2. cluster_owner is the 1-based node expected to hold
    # every key of `keys`; checking it proves the keys were routed by slot, not just written somewhere.
    cluster: bool = False
    cluster_port: int = 7001
    cluster_owner: Optional[int] = None

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

        if self.cluster:
            assert not any((self.sentinel, self.tls, self.user, self.valkey)), "Cluster cannot be combined with sentinel, tls, user or valkey"
            assert self.cluster_owner is None or (self.keys and 1 <= self.cluster_owner <= 3), "cluster_owner needs keys and a node between 1 and 3"
            # A cluster has no database 1, REDIS_CLUSTER_NODES requires 0.
            if self.db is None:
                self.db = 0
        elif self.cluster_owner is not None:
            raise ValueError("cluster_owner requires cluster")

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
