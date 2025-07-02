from hashlib import new as new_hash
from io import BytesIO
from os import getenv, sep
from pathlib import Path
from platform import machine
from typing import Dict, List, Optional, Union, Any, Hashable
import logging


def handle_docker_secrets() -> Dict[str, str]:
    """Handle Docker secrets by reading from /run/secrets directory (Alpine only)"""
    secrets = {}

    # Only check for Docker secrets on Alpine Linux
    os_release_path = Path("/etc/os-release")
    if not os_release_path.is_file():
        return secrets

    try:
        os_release_content = os_release_path.read_text(encoding="utf-8")
        if "alpine" not in os_release_content.casefold():
            return secrets
    except Exception:
        return secrets

    secrets_dir = Path("/run/secrets")
    if secrets_dir.is_dir():
        for secret_file in secrets_dir.glob("*"):
            if secret_file.is_file():
                try:
                    secret_name = secret_file.name.upper()
                    secret_value = secret_file.read_text(encoding="utf-8").strip()
                    secrets[secret_name] = secret_value
                except Exception as e:
                    print(f"Warning: Failed to read Docker secret {secret_file.name}: {e}")

    return secrets


def dict_to_frozenset(d: JsonValue) -> Hashable:
    if isinstance(d, list):
        # Recursively call the function on each item in the list.
        # The result of the generator is sorted and converted to a tuple.
        return tuple(sorted(dict_to_frozenset(item) for item in d))
    elif isinstance(d, dict):
        # Recursively call the function on each value in the dictionary.
        # The key-value pairs are turned into a frozenset.
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def get_version() -> str:
    return Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()


def get_integration() -> str:
    try:
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if getenv("KUBERNETES_MODE", "no").lower() == "yes":
            return "Kubernetes"
        elif getenv("SWARM_MODE", "no").lower() == "yes":
            return "Swarm"
        elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
            return "Autoconf"
        elif integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip().title()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            return "Docker"

        return "Linux"
    except:
        return "Unknown"


def get_os_info() -> Dict[str, str]:
    os_data = {
        "name": "Linux",
        "version": "Unknown",
        "version_id": "Unknown",
        "version_codename": "Unknown",
        "id": "Unknown",
        "arch": machine(),
    }

    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text().splitlines():
            if "=" not in line or line.split("=")[0].strip().lower() not in os_data:
                continue
            os_data[line.split("=")[0].lower()] = line.split("=")[1].strip('"')

    return os_data


def file_hash(file: Union[str, Path], *, algorithm: str = "sha512") -> str:
    _hash = new_hash(algorithm)
    if not isinstance(file, Path):
        file = Path(file)

    with file.open("rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _hash.update(data)
    return _hash.hexdigest()


def bytes_hash(bio: Union[str, bytes, BytesIO], *, algorithm: str = "sha512") -> str:
    if isinstance(bio, str):
        bio = BytesIO(bio.encode("utf-8"))
    elif isinstance(bio, bytes):
        bio = BytesIO(bio)

    assert isinstance(bio, BytesIO)

    _hash = new_hash(algorithm)
    while True:
        data = bio.read(1024)
        if not data:
            break
        _hash.update(data)
    bio.seek(0, 0)
    return _hash.hexdigest()


def get_redis_client(
    use_redis: bool = False,
    redis_host: Optional[str] = None,
    redis_port: Union[str, int] = "6379",
    redis_db: Union[str, int] = "0",
    redis_timeout: Union[str, float] = "1000.0",
    redis_keepalive_pool: Union[str, int] = "10",
    redis_ssl: bool = False,
    redis_username: Optional[str] = None,
    redis_password: Optional[str] = None,
    redis_sentinel_hosts: Union[List[List[str]], List[tuple], str] = [],
    redis_sentinel_username: Optional[str] = None,
    redis_sentinel_password: Optional[str] = None,
    redis_sentinel_master: str = "",
    logger: Optional[logging.Logger] = None,
) -> Any:
    """
    Get a Redis client using provided configuration parameters.

    Args:
        use_redis: Whether to use Redis or not
        redis_host: Redis host address
        redis_port: Redis port number
        redis_db: Redis database number
        redis_timeout: Connection timeout in milliseconds
        redis_keepalive_pool: Maximum connections in pool
        redis_ssl: Whether to use SSL for connection
        redis_username: Redis username for authentication
        redis_password: Redis password for authentication
        redis_sentinel_hosts: List of Redis Sentinel hosts
        redis_sentinel_username: Redis Sentinel username
        redis_sentinel_password: Redis Sentinel password
        redis_sentinel_master: Redis Sentinel master name
        logger: Logger instance for logging errors

    Returns:
        Redis client instance or None if connection fails
    """
    if not use_redis:
        return None

    try:
        from redis import StrictRedis, Sentinel
    except ImportError:
        if logger:
            logger.error("Redis package is not installed")
        return None

    if not redis_host and not redis_sentinel_hosts:
        if logger:
            logger.error("Neither redis_host nor redis_sentinel_hosts is provided")
        return None

    # Convert string parameters to appropriate types
    try:
        if isinstance(redis_port, str):
            redis_port = int(redis_port)

        if isinstance(redis_db, str):
            redis_db = int(redis_db)

        if isinstance(redis_timeout, str):
            redis_timeout = float(redis_timeout)

        if isinstance(redis_keepalive_pool, str):
            redis_keepalive_pool = int(redis_keepalive_pool)
    except ValueError as e:
        if logger:
            logger.error(f"Error converting redis parameters: {e}")
            logger.error("Using defaults: redis_port=6379, redis_db=0, redis_timeout=1000.0, redis_keepalive_pool=10")
        redis_port = 6379
        redis_db = 0
        redis_timeout = 1000.0
        redis_keepalive_pool = 10

    # Process sentinel hosts if provided as string
    if isinstance(redis_sentinel_hosts, str):
        redis_sentinel_hosts = [host.split(":") if ":" in host else (host, "26379") for host in redis_sentinel_hosts.split() if host]

    redis_client = None

    try:
        # Connect via Sentinel if sentinel hosts are provided
        if redis_sentinel_hosts:
            if logger:
                logger.info(f"Connecting to Redis Sentinel cluster: {redis_sentinel_hosts}")

            sentinel = Sentinel(
                redis_sentinel_hosts,
                username=redis_sentinel_username,
                password=redis_sentinel_password,
                ssl=redis_ssl,
                socket_timeout=redis_timeout / 1000,
                socket_connect_timeout=redis_timeout / 1000,
                socket_keepalive=True,
                max_connections=redis_keepalive_pool,
            )

            try:
                # Test the connection
                sentinel.discover_master(redis_sentinel_master)

                # Get master connection
                redis_client = sentinel.master_for(
                    redis_sentinel_master,
                    db=redis_db,
                    username=redis_username,
                    password=redis_password,
                )
            except Exception as e:
                if logger:
                    logger.error(f"Failed to connect to Redis Sentinel: {e}")
                return None

        # Direct connection to Redis
        else:
            if logger:
                logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")

            redis_client = StrictRedis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                username=redis_username,
                password=redis_password,
                socket_timeout=redis_timeout / 1000,
                socket_connect_timeout=redis_timeout / 1000,
                socket_keepalive=True,
                max_connections=redis_keepalive_pool,
                ssl=redis_ssl,
            )

        # Test the connection
        redis_client.ping()
        if logger:
            logger.info("Successfully connected to Redis")

        return redis_client

    except Exception as e:
        if logger:
            logger.error(f"Failed to connect to Redis: {e}")
        return None
