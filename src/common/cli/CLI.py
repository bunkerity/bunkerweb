#!/usr/bin/env python3

from datetime import datetime
from json import dumps, loads
from operator import itemgetter
from time import time
from dotenv import dotenv_values
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from redis import StrictRedis, Sentinel
from subprocess import DEVNULL, STDOUT, run
from sys import path as sys_path
from typing import Any, Optional, Tuple


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import setup_logger  # type: ignore


def format_remaining_time(seconds):
    years, seconds = divmod(seconds, 60 * 60 * 24 * 365)
    months, seconds = divmod(seconds, 60 * 60 * 24 * 30)
    while months >= 12:
        years += 1
        months -= 12
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if years > 0:
        time_parts.append(f"{int(years)} year{'' if years == 1 else 's'}")
    if months > 0:
        time_parts.append(f"{int(months)} month{'' if months == 1 else 's'}")
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
        variables_path = Path(sep, "etc", "nginx", "variables.env")
        self.__variables = {}
        self.__db = None
        if variables_path.is_file():
            self.__variables = dotenv_values(variables_path)

        if Path(sep, "usr", "share", "bunkerweb", "db").exists():
            from Database import Database  # type: ignore

            self.__logger.info("Getting variables from database")

            self.__db = Database(self.__logger, sqlalchemy_string=self.__get_variable("DATABASE_URI", None))
            self.__variables = self.__db.get_config()

        assert isinstance(self.__variables, dict), "Failed to get variables from database"

        self.__integration = self.__detect_integration()
        self.__use_redis = self.__get_variable("USE_REDIS", "no") == "yes"
        self.__redis = None
        if self.__use_redis:
            self.__logger.info("Fetching redis configuration")
            redis_host = self.__get_variable("REDIS_HOST")
            if redis_host:
                redis_port = self.__get_variable("REDIS_PORT", "6379")
                assert isinstance(redis_port, str), "REDIS_PORT is not a string"
                if not redis_port.isdigit():
                    self.__logger.error(f"REDIS_PORT is not a valid port number: {redis_port}, defaulting to 6379")
                    redis_port = "6379"
                redis_port = int(redis_port)

                redis_db = self.__get_variable("REDIS_DB", "0")
                assert isinstance(redis_db, str), "REDIS_DB is not a string"
                if not redis_db.isdigit():
                    self.__logger.error(f"REDIS_DB is not a valid database number: {redis_db}, defaulting to 0")
                    redis_db = "0"
                redis_db = int(redis_db)

                redis_timeout = self.__get_variable("REDIS_TIMEOUT", "1000.0")
                if redis_timeout:
                    try:
                        redis_timeout = float(redis_timeout)
                    except ValueError:
                        self.__logger.error(f"REDIS_TIMEOUT is not a valid timeout: {redis_timeout}, defaulting to 1000 ms")
                        redis_timeout = 1000.0

                redis_keepalive_pool = self.__get_variable("REDIS_KEEPALIVE_POOL", "10")
                assert isinstance(redis_keepalive_pool, str), "REDIS_KEEPALIVE_POOL is not a string"
                if not redis_keepalive_pool.isdigit():
                    self.__logger.error(f"REDIS_KEEPALIVE_POOL is not a valid number of connections: {redis_keepalive_pool}, defaulting to 10")
                    redis_keepalive_pool = "10"
                redis_keepalive_pool = int(redis_keepalive_pool)

                self.__logger.info("Redis configuration is valid")

                redis_ssl = self.__get_variable("REDIS_SSL", "no") == "yes"
                username = self.__get_variable("REDIS_USERNAME", None) or None
                password = self.__get_variable("REDIS_PASSWORD", None) or None
                sentinel_hosts = self.__get_variable("REDIS_SENTINEL_HOSTS", [])

                if isinstance(sentinel_hosts, str):
                    sentinel_hosts = [host.split(":") if ":" in host else host for host in sentinel_hosts.split(" ") if host]

                if sentinel_hosts:
                    sentinel_username = self.__get_variable("REDIS_SENTINEL_USERNAME", None) or None
                    sentinel_password = self.__get_variable("REDIS_SENTINEL_PASSWORD", None) or None
                    sentinel_master = self.__get_variable("REDIS_SENTINEL_MASTER", "")

                    self.__logger.info(
                        f"Connecting to redis sentinel cluster with the following parameters:\n{sentinel_hosts=}\n{sentinel_username=}\n{sentinel_password=}\n{sentinel_master=}\n{redis_timeout=}\nmax_connections={redis_keepalive_pool}\n{redis_ssl=}"
                    )
                    sentinel = Sentinel(
                        sentinel_hosts,
                        username=sentinel_username,
                        password=sentinel_password,
                        ssl=redis_ssl,
                        socket_timeout=redis_timeout,
                        socket_connect_timeout=redis_timeout,
                        socket_keepalive=True,
                        max_connections=redis_keepalive_pool,
                    )
                    try:
                        sentinel.discover_master(sentinel_master)
                    except Exception as e:
                        self.__logger.error(f"Failed to connect to redis sentinel cluster: {e}, disabling redis")
                        self.__use_redis = False

                    if self.__use_redis:
                        self.__logger.info(
                            f"Connected to redis sentinel cluster, getting master with the following parameters:\n{sentinel_master=}\n{redis_db=}\n{username=}\n{password=}"
                        )
                        self.__redis = sentinel.master_for(
                            sentinel_master,
                            db=redis_db,
                            username=username,
                            password=password,
                        )
                else:
                    self.__logger.info(
                        f"Connecting to redis with the following parameters:\n{redis_host=}\n{redis_port=}\n{redis_db=}\n{username=}\n{password=}\n{redis_timeout=}\nmax_connections={redis_keepalive_pool}\n{redis_ssl=}"
                    )
                    self.__redis = StrictRedis(
                        host=redis_host,
                        port=redis_port,
                        db=redis_db,
                        username=username,
                        password=password,
                        socket_timeout=redis_timeout,
                        socket_connect_timeout=redis_timeout,
                        socket_keepalive=True,
                        max_connections=redis_keepalive_pool,
                        ssl=redis_ssl,
                    )

                try:
                    if self.__use_redis:
                        assert self.__redis, "Redis connection is None"
                        self.__redis.ping()
                except Exception as e:
                    self.__logger.error(f"Failed to connect to redis: {e}, disabling redis")
                    self.__use_redis = False
                self.__logger.info("Connected to redis")
            else:
                self.__logger.error("USE_REDIS is set to yes but REDIS_HOST is not set, disabling redis")
                self.__use_redis = False

        if self.__integration == "linux":
            super().__init__(
                [
                    API(
                        f"http://127.0.0.1:{self.__get_variable('API_HTTP_PORT', '5000')}",
                        host=self.__get_variable("API_SERVER_NAME", "bwapi"),
                    )
                ]
            )
        else:
            super().__init__()
            self.auto_setup(self.__integration)

    def __get_variable(self, variable: str, default: Optional[Any] = None) -> Optional[str]:
        return getenv(variable, self.__variables.get(variable, default))

    def __detect_integration(self) -> str:
        if Path(sep, "usr", "sbin", "nginx").exists():
            return "linux"

        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if self.__get_variable("KUBERNETES_MODE", "no").lower() == "yes":  # type: ignore
            return "kubernetes"
        elif self.__get_variable("SWARM_MODE", "no").lower() == "yes":  # type: ignore
            return "swarm"
        elif self.__get_variable("AUTOCONF_MODE", "no").lower() == "yes":  # type: ignore
            return "autoconf"
        elif integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip().lower()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            return "docker"

        return "linux"

    def unban(self, ip: str) -> Tuple[bool, str]:
        if self.__redis:
            try:
                ok = self.__redis.delete(f"bans_ip_{ip}")
                if not ok:
                    self.__logger.error(f"Failed to delete ban for {ip} from redis")
            except Exception as e:
                self.__logger.error(f"Failed to delete ban for {ip} from redis: {e}")

        if self.send_to_apis("POST", "/unban", data={"ip": ip}):
            return True, f"IP {ip} has been unbanned"
        return False, f"Failed to unban {ip}"

    def ban(self, ip: str, exp: float, reason: str) -> Tuple[bool, str]:
        if self.__redis:
            try:
                ok = self.__redis.set(f"bans_ip_{ip}", dumps({"reason": reason, "date": time()}))
                if not ok:
                    self.__logger.error(f"Failed to ban {ip} in redis")
                self.__redis.expire(f"bans_ip_{ip}", int(exp))
            except Exception as e:
                self.__logger.error(f"Failed to ban {ip} in redis: {e}")

        if self.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason}):
            return (True, f"IP {ip} has been banned for {format_remaining_time(exp)} with reason {reason}")
        return False, f"Failed to ban {ip}"

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
                data = self.__redis.get(key)
                if not data:
                    continue
                exp = self.__redis.ttl(key)
                servers["redis"].append({"ip": ip, "exp": exp} | loads(data))

        servers = {k: sorted(v, key=itemgetter("date")) for k, v in servers.items()}

        cli_str = ""
        for server, bans in servers.items():
            cli_str += f"List of bans for {server}:\n"
            if not bans:
                cli_str += "No ban found\n"

            for ban in bans:
                banned_date = ""
                remaining = "for eternity"
                if ban["date"] != -1:
                    banned_date = f"the {datetime.fromtimestamp(ban['date']).strftime('%d-%m-%Y at %H:%M:%S')} "
                if ban["exp"] != -1:
                    remaining = f"for {format_remaining_time(ban['exp'])} remaining"
                cli_str += f"- {ban['ip']} ; banned {banned_date}{remaining} with reason \"{ban.get('reason', 'no reason given')}\"\n"
            cli_str += "\n"

        return True, cli_str

    def custom(self, plugin_id: str, command: str, *args: str, debug: bool = False) -> Tuple[bool, str]:
        if not self.__db:
            raise Exception("This command can only be executed on the scheduler")

        found = False
        plugin_type = "core"
        file_name = None

        for db_plugin in self.__db.get_plugins():
            if db_plugin["id"] == plugin_id:
                found = True
                plugin_type = db_plugin["type"]
                file_name = db_plugin["bwcli"].get(command, None)
                break

        if not found:
            return False, f"Plugin {plugin_id} not found"
        elif not file_name:
            return False, f"Command {command} not found for plugin {plugin_id}"

        command_path = (
            Path(sep, "usr", "share", "bunkerweb", "core", plugin_id)
            if plugin_type == "core"
            else (
                Path(sep, "etc", "bunkerweb", "plugins", plugin_id) if plugin_type == "external" else Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin_id)
            )
        ).joinpath("bwcli", file_name)

        if not command_path.is_file():
            return False, f"Command {command} not found for plugin {plugin_id} (file {command_path} not found)"

        cmd = [command_path.as_posix()]
        if args:
            cmd.extend(args)

        self.__logger.debug(f"Executing command {' '.join(cmd)}")
        proc = run(cmd, stdin=DEVNULL, stderr=STDOUT, check=False, env=self.__variables | environ | ({"LOG_LEVEL": "DEBUG"} if debug else {}))  # type: ignore

        if proc.returncode != 0:
            return False, f"Command {command} failed"

        return True, ""
