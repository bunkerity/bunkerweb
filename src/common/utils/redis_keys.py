"""Redis key names shared with src/bw/lua/bunkerweb/rediskeys.lua.

Standalone and Sentinel keep the historical names. In Redis Cluster mode, keys that scripts
touch together share a hash tag: ban and bad behavior keys are tagged with the IP, the
reports list and its facets with {requests}. Only Redis sees these names.
"""

from re import compile as re_compile
from ipaddress import IPv6Address

_BAN = re_compile(r"^(.*_ip_)(.+)$")
_NODE = re_compile(r"^(\[[0-9a-fA-F:.]+\]|[\w.-]+):([0-9]+)$")


def is_cluster(client) -> bool:
    try:
        from redis.cluster import RedisCluster
    except ImportError:
        return False
    return isinstance(client, RedisCluster)


def escape(key: str) -> str:
    for char, encoded in (("%", "%25"), ("{", "%7B"), ("}", "%7D"), ("*", "%2A"), ("?", "%3F"), ("[", "%5B"), ("]", "%5D"), ("\\", "%5C")):
        key = key.replace(char, encoded)
    return key


def unescape(text: str) -> str:
    for encoded, char in (("%7B", "{"), ("%7D", "}"), ("%2A", "*"), ("%3F", "?"), ("%5B", "["), ("%5D", "]"), ("%5C", "\\"), ("%25", "%")):
        text = text.replace(encoded, char)
    return text


def parse_nodes(value: str) -> list:
    """Explicit host:port seeds; bracket IPv6 to keep the port unambiguous."""
    nodes = []
    for node in value.split():
        match = _NODE.fullmatch(node)
        if not match or not 1 <= int(match[2]) <= 65535:
            raise ValueError(f"REDIS_CLUSTER_NODES requires host:port with port 1-65535 (got {node})")
        host = match[1]
        if host.startswith("["):
            IPv6Address(host[1:-1])
            host = host[1:-1]
        nodes.append((host, int(match[2])))
    return nodes


def ban_key(local_key: str, cluster: bool) -> str:
    if not cluster:
        return local_key
    match = _BAN.match(local_key)
    if match is None:
        raise ValueError(f"Invalid local ban key: {local_key}")
    prefix, ip = match.groups()
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
    try:
        parse_nodes(cluster_nodes)
    except ValueError as exc:
        return f"Invalid REDIS_CLUSTER_NODES: {exc}"
    return None


def _base(cluster: bool) -> str:
    return "{requests}" if cluster else "requests"


def requests_key(cluster: bool) -> str:
    return _base(cluster)


def initialized_key(cluster: bool) -> str:
    return f"{_base(cluster)}:facets:initialized"


def facet_key(cluster: bool, field: str) -> str:
    return f"{_base(cluster)}:facet:{field}"
