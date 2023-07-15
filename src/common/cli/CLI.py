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

        self.__use_redis = False
        redis_host = None
        redis_port = "6379"
        redis_db = "0"
        redis_timeout = "1000.0"
        redis_keepalive_pool = "10"
        redis_ssl = False

        if not db_path.is_dir():
            self.__variables = dotenv_values(join(sep, "etc", "nginx", "variables.env"))
            self.__use_redis = self.__variables.get("USE_REDIS", "no") == "yes"
            redis_host = self.__variables.get("REDIS_HOST")
            redis_port = self.__variables.get("REDIS_PORT", "6379")
            redis_db = self.__variables.get("REDIS_DB", "0")
            redis_timeout = self.__variables.get("REDIS_TIMEOUT", "1000.0")
            redis_keepalive_pool = self.__variables.get("REDIS_KEEPALIVE_POOL", "10")
            redis_ssl = self.__variables.get("REDIS_SSL", "no") == "yes"

            apis = [
                API(
                    f"http://127.0.0.1:{self.__variables.get('API_HTTP_PORT', '5000')}",
                    host=self.__variables.get("API_SERVER_NAME", "bwapi"),
                )
            ]
        else:
            if str(db_path) not in sys_path:
                sys_path.append(str(db_path))

            from Database import Database  # type: ignore

            db = Database(
                self.__logger,
                sqlalchemy_string=getenv("DATABASE_URI", None),
            )
            instances = db.get_config()

            for config in instances.values():
                self.__use_redis = (
                    self.__use_redis or config.get("USE_REDIS", "no") == "yes"
                )
                if self.__use_redis:
                    redis_host = redis_host or config.get("REDIS_HOST")
                    if redis_port == "6379":
                        redis_port = config.get("REDIS_PORT", "6379")
                    if redis_db == "0":
                        redis_db = config.get("REDIS_DB", "0")
                    if redis_timeout == "1000.0":
                        redis_timeout = config.get("REDIS_TIMEOUT", "1000.0")
                    if redis_keepalive_pool == "10":
                        redis_keepalive_pool = config.get("REDIS_KEEPALIVE_POOL", "10")
                    redis_ssl = redis_ssl or config.get("REDIS_SSL", "no") == "yes"

            apis = []

            for instance in db.get_instances():
                endpoint = f"http://{instance['hostname']}:{instance['port']}"
                host = instance["server_name"]
                apis.append(API(endpoint, host=host))

        self.__redis = None
        if self.__use_redis:
            if redis_host:
                if not redis_port.isdigit():
                    self.__logger.error(
                        f"REDIS_PORT is not a valid port number: {redis_port}, defaulting to 6379"
                    )
                    redis_port = "6379"
                redis_port = int(redis_port)

                if not redis_db.isdigit():
                    self.__logger.error(
                        f"REDIS_DB is not a valid database number: {redis_db}, defaulting to 0"
                    )
                    redis_db = "0"
                redis_db = int(redis_db)

                if redis_timeout:
                    try:
                        redis_timeout = float(redis_timeout)
                    except ValueError:
                        self.__logger.error(
                            f"REDIS_TIMEOUT is not a valid timeout: {redis_timeout}, defaulting to 1000 ms"
                        )
                        redis_timeout = 1000.0

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
                    ssl=redis_ssl,
                )
            else:
                self.__logger.error(
                    "USE_REDIS is set to yes but REDIS_HOST is not set, disabling redis"
                )
                self.__use_redis = False

        super().__init__(apis)

    def unban(self, ip: str) -> Tuple[bool, str]:
        if self.__redis:
            ok = self.__redis.delete(f"bans_ip_{ip}")
            if not ok:
                self.__logger.error(f"Failed to delete ban for {ip} from redis")

        if self.send_to_apis("POST", "/unban", data={"ip": ip}):
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

        if self.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp}):
            return (
                True,
                f"IP {ip} has been banned for {format_remaining_time(exp)}",
            )
        return False, "error"

    def bans(self) -> Tuple[bool, str]:
        servers = {}

        ret, resp = self.send_to_apis("GET", "/bans", response=True)
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
            cli_str += "\n"

        return True, cli_str
