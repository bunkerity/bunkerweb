#!/usr/bin/python3

from dotenv import dotenv_values
from os import getenv, sep
from os.path import join
from pathlib import Path
from redis import StrictRedis
from sys import path as sys_path
from typing import Tuple


if join(sep, "usr", "share", "bunkerweb", "utils") not in sys_path:
    sys_path.append(join(sep, "usr", "share", "bunkerweb", "utils"))

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import setup_logger  # type: ignore


def format_remaining_time(seconds):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if days > 0:
        time_parts.append(f"{int(days)} day{'' if days == 1 else 's'}")
    if hours > 0:
        time_parts.append(f"{int(hours)} hour{'' if hours == 1 else 's'}")
    if minutes > 0:
        time_parts.append(f"{int(minutes)} minute{'' if minutes == 1 else 's'}")
    if seconds > 0:
        time_parts.append(f"{seconds} second{'' if seconds == 1 else 's'}")

    if len(time_parts) > 1:
        time_parts[-1] = f"and {time_parts[-1]}"

    return " ".join(time_parts)


class CLI(ApiCaller):
    def __init__(self):
        self.__logger = setup_logger("CLI", getenv("LOG_LEVEL", "INFO"))
        db_path = Path(sep, "usr", "share", "bunkerweb", "db")

        if not db_path.is_dir():
            self.__variables = dotenv_values(join(sep, "etc", "nginx", "variables.env"))
        else:
            if str(db_path) not in sys_path:
                sys_path.append(str(db_path))

            from Database import Database  # type: ignore

            db = Database(
                self.__logger,
                sqlalchemy_string=getenv("DATABASE_URI", None),
            )
            self.__variables = db.get_config()

        self.__integration = self.__detect_integration()
        self.__use_redis = self.__variables.get("USE_REDIS", "no") == "yes"
        self.__redis = None
        if self.__use_redis:
            redis_host = self.__variables.get("REDIS_HOST")
            if redis_host:
                redis_port = self.__variables.get("REDIS_PORT", "6379")
                if not redis_port.isdigit():
                    self.__logger.error(
                        f"REDIS_PORT is not a valid port number: {redis_port}, defaulting to 6379"
                    )
                    redis_port = "6379"
                redis_port = int(redis_port)

                redis_db = self.__variables.get("REDIS_DB", "0")
                if not redis_db.isdigit():
                    self.__logger.error(
                        f"REDIS_DB is not a valid database number: {redis_db}, defaulting to 0"
                    )
                    redis_db = "0"
                redis_db = int(redis_db)

                redis_timeout = self.__variables.get("REDIS_TIMEOUT", "1000.0")
                if redis_timeout:
                    try:
                        redis_timeout = float(redis_timeout)
                    except ValueError:
                        self.__logger.error(
                            f"REDIS_TIMEOUT is not a valid timeout: {redis_timeout}, defaulting to 1000 ms"
                        )
                        redis_timeout = 1000.0

                redis_keepalive_pool = self.__variables.get(
                    "REDIS_KEEPALIVE_POOL", "10"
                )
                if not redis_keepalive_pool.isdigit():
                    self.__logger.error(
                        f"REDIS_KEEPALIVE_POOL is not a valid number of connections: {redis_keepalive_pool}, defaulting to 10"
                    )
                    redis_keepalive_pool = "10"
                redis_keepalive_pool = int(redis_keepalive_pool)

                self.__redis = StrictRedis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    socket_timeout=redis_timeout,
                    socket_connect_timeout=redis_timeout,
                    socket_keepalive=True,
                    max_connections=redis_keepalive_pool,
                    ssl=self.__variables.get("REDIS_SSL", "no") == "yes",
                )
            else:
                self.__logger.error(
                    "USE_REDIS is set to yes but REDIS_HOST is not set, disabling redis"
                )
                self.__use_redis = False

        if not db_path.is_dir() or self.__integration not in (
            "kubernetes",
            "swarm",
            "autoconf",
        ):
            # Docker & Linux case
            super().__init__(
                apis=[
                    API(
                        f"http://127.0.0.1:{self.__variables.get('API_HTTP_PORT', '5000')}",
                        host=self.__variables.get("API_SERVER_NAME", "bwapi"),
                    )
                ]
            )
        else:
            super().__init__()
            self.auto_setup(self.__integration)

    def __detect_integration(self) -> str:
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if self.__variables.get("KUBERNETES_MODE", "no").lower() == "yes":
            return "kubernetes"
        elif self.__variables.get("SWARM_MODE", "no").lower() == "yes":
            return "swarm"
        elif self.__variables.get("AUTOCONF_MODE", "no").lower() == "yes":
            return "autoconf"
        elif integration_path.is_file():
            return integration_path.read_text().strip().lower()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text():
            return "docker"

        return "linux"

    def unban(self, ip: str) -> Tuple[bool, str]:
        if self.__redis:
            ok = self.__redis.delete(f"bans_ip_{ip}")
            if not ok:
                self.__logger.error(f"Failed to delete ban for {ip} from redis")

        if self._send_to_apis("POST", "/unban", data={"ip": ip}):
            return True, f"IP {ip} has been unbanned"
        return False, "error"

    def ban(self, ip: str, exp: float) -> Tuple[bool, str]:
        if self.__redis:
            ok = self.__redis.set(
                f"bans_ip_{ip}",
                "manual",
                ex=exp,
            )
            if not ok:
                self.__logger.error(f"Failed to ban {ip} in redis")

        if self._send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp}):
            return (
                True,
                f"IP {ip} has been banned for {format_remaining_time(exp)}",
            )
        return False, "error"

    def bans(self) -> Tuple[bool, str]:
        servers = {}

        ret, resp = self._send_to_apis("GET", "/bans", response=True)
        if not ret:
            return False, "error"

        for k, v in resp.items():
            servers[k] = v.get("data", [])

        if self.__redis:
            servers["redis"] = []
            for key in self.__redis.scan_iter("bans_ip_*"):
                ip = key.decode("utf-8").replace("bans_ip_", "")
                exp = self.__redis.ttl(key)
                servers["redis"].append(
                    {
                        "ip": ip,
                        "exp": exp,
                        "reason": "manual",
                    }
                )

        cli_str = ""
        for server, bans in servers.items():
            cli_str += f"List of bans for {server}:\n"
            if not bans:
                cli_str += "No ban found\n"

            for ban in bans:
                cli_str += f"- {ban['ip']} for {format_remaining_time(ban['exp'])} : {ban.get('reason', 'no reason given')}\n"
            else:
                cli_str += "\n"

        return True, cli_str
