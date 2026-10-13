"""Redis key names shared with src/bw/lua/bunkerweb/rediskeys.lua.

Standalone and Sentinel keep the historical names. In Redis Cluster mode, keys that scripts
touch together share a hash tag: ban and bad behavior keys are tagged with the IP, the
reports list and its facets with {requests}. Only Redis sees these names.
"""

from re import compile as re_compile

_BAN = re_compile(r"^(.*_ip_)(.+)$")


def is_cluster(client) -> bool:
    try:
        from redis.cluster import RedisCluster
    except ImportError:
        return False
    return isinstance(client, RedisCluster)


def escape(key: str) -> str:
    return key.replace("%", "%25").replace("{", "%7B").replace("}", "%7D")


def unescape(text: str) -> str:
    return text.replace("%7B", "{").replace("%7D", "}").replace("%25", "%")


def ban_key(local_key: str, cluster: bool) -> str:
    if not cluster:
        return local_key
    prefix, ip = _BAN.match(local_key).groups()
    return f"{escape(prefix)}{{{ip}}}"


def ban_ip(raw_ip: str) -> str:
    """IP part of a Redis ban key, tagged or not."""
    return raw_ip[1:-1] if raw_ip.startswith("{") and raw_ip.endswith("}") else raw_ip


def cluster_config_error(cluster_nodes, sentinel_hosts, database) -> "str | None":
    """Same rule as rediskeys.cluster_config_error: cluster plus Sentinel or a non-zero
    database is a configuration error and Redis is left unused."""
    if not (cluster_nodes or "").strip():
        return None
    if sentinel_hosts:
        return "REDIS_CLUSTER_NODES and REDIS_SENTINEL_HOSTS are both set, remove one"
    try:
        is_zero = int(str(database or "0").strip()) == 0
    except ValueError:
        is_zero = False
    if not is_zero:
        return f"REDIS_CLUSTER_NODES requires REDIS_DATABASE 0 (got {database})"
    return None


def _base(cluster: bool) -> str:
    return "{requests}" if cluster else "requests"


def requests_key(cluster: bool) -> str:
    return _base(cluster)


def initialized_key(cluster: bool) -> str:
    return f"{_base(cluster)}:facets:initialized"


def facet_key(cluster: bool, field: str) -> str:
    return f"{_base(cluster)}:facet:{field}"
