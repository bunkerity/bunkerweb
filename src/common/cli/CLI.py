#!/usr/bin/env python3

from datetime import datetime
from json import dumps, loads
from operator import itemgetter
from os import environ, get_terminal_size, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import path as sys_path
from traceback import format_exc
from typing import Any, Optional, Tuple
from time import time

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import setup_logger  # type: ignore

from common_utils import get_redis_client  # type: ignore


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
    # ANSI color and style constants
    RESET = "\033[0m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    MAGENTA = "\033[35m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    # Icons
    ICON_SUCCESS = "✅"
    ICON_ERROR = "❌"
    ICON_WARNING = "⚠️"
    ICON_INFO = "ℹ️"
    ICON_LOCK = "🔒"
    ICON_UNLOCK = "🔓"
    ICON_GLOBE = "🌐"
    ICON_SERVER = "🖧"
    ICON_CLOCK = "⏱"

    def __init__(self):
        self.__logger = setup_logger("CLI", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))
        variables_path = Path(sep, "etc", "nginx", "variables.env")
        self.__variables = {}
        self.__db = None
        if variables_path.is_file():
            with variables_path.open() as f:
                self.__variables = dict(line.strip().split("=", 1) for line in f if line.strip() and not line.startswith("#") and "=" in line)

        if Path(sep, "usr", "share", "bunkerweb", "db").exists():
            from Database import Database  # type: ignore

            self.__logger.info("Getting variables from database")

            self.__db = Database(self.__logger, sqlalchemy_string=self.__get_variable("DATABASE_URI", None))
            self.__variables = self.__db.get_config()

        assert isinstance(self.__variables, dict), "Failed to get variables from database"

        tz = getenv("TZ")
        if tz:
            self.__variables["TZ"] = tz

        # Use the common redis client function instead of implementing the connection logic here
        self.__use_redis = self.__get_variable("USE_REDIS", "no") == "yes"
        self.__redis = get_redis_client(
            use_redis=self.__use_redis,
            redis_host=self.__get_variable("REDIS_HOST"),
            redis_port=self.__get_variable("REDIS_PORT", "6379"),
            redis_db=self.__get_variable("REDIS_DB", "0"),
            redis_timeout=self.__get_variable("REDIS_TIMEOUT", "1000.0"),
            redis_keepalive_pool=self.__get_variable("REDIS_KEEPALIVE_POOL", "10"),
            redis_ssl=self.__get_variable("REDIS_SSL", "no") == "yes",
            redis_username=self.__get_variable("REDIS_USERNAME", None) or None,
            redis_password=self.__get_variable("REDIS_PASSWORD", None) or None,
            redis_sentinel_hosts=self.__get_variable("REDIS_SENTINEL_HOSTS", []),
            redis_sentinel_username=self.__get_variable("REDIS_SENTINEL_USERNAME", None) or None,
            redis_sentinel_password=self.__get_variable("REDIS_SENTINEL_PASSWORD", None) or None,
            redis_sentinel_master=self.__get_variable("REDIS_SENTINEL_MASTER", ""),
            logger=self.__logger,
        )

        if self.__use_redis and not self.__redis:
            self.__logger.error("Failed to connect to Redis, disabling Redis functionality")
            self.__use_redis = False

        super().__init__()
        # Add terminal width detection with error handling for non-TTY environments
        try:
            self.__terminal_width = get_terminal_size().columns
        except (OSError, IOError):
            self.__logger.debug("Unable to determine terminal size. Using default width.")
            self.__terminal_width = 80  # Default width for non-TTY environments

        if self.__db:
            for db_instance in self.__db.get_instances():
                self.apis.append(API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"]))
        else:
            self.apis.append(API(f"http://127.0.0.1:{self.__get_variable('API_HTTP_PORT', '5000')}", self.__get_variable("API_SERVER_NAME", "bwapi")))

    def __get_variable(self, variable: str, default: Optional[Any] = None) -> Optional[str]:
        return getenv(variable, self.__variables.get(variable, default))

    def __adapt_display_width(self):
        """Determine appropriate display width based on terminal size"""
        return min(80, max(40, self.__terminal_width - 5))

    def __format_success(self, message: str) -> str:
        """Format a success message with visual enhancements"""
        width = self.__adapt_display_width()
        message_lines = message.split("\n")

        output = f"\n{self.BG_GREEN}{self.WHITE}{self.BOLD} {self.ICON_SUCCESS} SUCCESS {self.RESET}\n"
        output += f"{self.GREEN}{'─' * width}{self.RESET}\n"

        for line in message_lines:
            output += f"{self.GREEN}• {self.RESET}{line}\n"

        output += f"{self.GREEN}{'─' * width}{self.RESET}\n"
        return output

    def __format_error(self, message: str) -> str:
        """Format an error message with visual enhancements"""
        width = self.__adapt_display_width()
        message_lines = message.split("\n")

        output = f"\n{self.BG_RED}{self.WHITE}{self.BOLD} {self.ICON_ERROR} ERROR {self.RESET}\n"
        output += f"{self.RED}{'─' * width}{self.RESET}\n"

        for line in message_lines:
            output += f"{self.RED}• {self.RESET}{line}\n"

        output += f"{self.RED}{'─' * width}{self.RESET}\n"
        return output

    def unban(self, ip: str, service: Optional[str] = None) -> Tuple[bool, str]:
        """Unban an IP address globally or from a specific service"""
        if self.__redis:
            try:
                # Delete global ban
                ok = self.__redis.delete(f"bans_ip_{ip}")
                if not ok:
                    self.__logger.error(f"Failed to delete ban for {ip} from redis")

                # If service is specified, delete service-specific ban
                if service:
                    service_key = f"bans_service_{service}_ip_{ip}"
                    ok = self.__redis.delete(service_key)
                    if not ok:
                        self.__logger.error(f"Failed to delete service-specific ban for {ip} on service {service} from redis")
                else:
                    # Delete all service-specific bans for this IP
                    for key in self.__redis.scan_iter(f"bans_service_*_ip_{ip}"):
                        self.__redis.delete(key)
            except Exception as e:
                self.__logger.error(f"Failed to delete ban for {ip} from redis: {e}")

        try:
            if self.send_to_apis("POST", "/unban", data={"ip": ip} | ({"service": service} if service else {})):
                if service:
                    success_msg = (
                        f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned from service {self.CYAN}{service}{self.RESET}"
                    )
                else:
                    success_msg = f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned {self.GREEN}globally{self.RESET}"
                return True, self.__format_success(success_msg)
        except BaseException as e:
            return False, self.__format_error(f"Failed to unban {ip}: {e}")
        return False, self.__format_error(f"Failed to unban {ip}")

    def ban(self, ip: str, exp: float, reason: str, service: str = "bwcli") -> Tuple[bool, str]:
        """Ban an IP address globally or from a specific service"""
        # Auto-set scope to service if a non-default service is specified
        ban_scope = "global"
        if service != "bwcli" and service:
            ban_scope = "service"

        # Validate the service name if scope is service
        if ban_scope == "service":
            # Try to get list of services
            services = []
            try:
                if self.__db:
                    config = self.__db.get_config(global_only=True, filtered_settings=("SERVER_NAME",))
                    services = config.get("SERVER_NAME", [])
                else:
                    services = self.__get_variable("SERVER_NAME", "").split(" ")

                # Ensure services is a list
                if isinstance(services, str):
                    services = services.split()

                # Check if service exists
                if not service or service == "bwcli" or service not in services:
                    self.__logger.warning(f"Invalid service '{service}' for IP {ip}, defaulting to global ban")
                    ban_scope = "global"
                    service = "bwcli"
            except Exception as e:
                self.__logger.warning(f"Error validating service: {e}, defaulting to global ban")
                ban_scope = "global"
                service = "bwcli"

        if self.__redis:
            try:
                ban_data = dumps({"reason": reason, "date": time(), "service": service, "ban_scope": ban_scope, "permanent": exp == -1})

                ban_key = f"bans_ip_{ip}"
                if ban_scope == "service" and service != "bwcli":
                    ban_key = f"bans_service_{service}_ip_{ip}"

                ok = self.__redis.set(ban_key, ban_data)
                if not ok:
                    self.__logger.error(f"Failed to ban {ip} in redis")

                # Only set expiration if not permanent ban
                if exp != -1:
                    self.__redis.expire(ban_key, int(exp))
            except Exception as e:
                self.__logger.error(f"Failed to ban {ip} in redis: {e}")

        try:
            if self.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason, "service": service or "bwcli", "ban_scope": ban_scope}):
                scope_text = f"{self.GREEN}globally{self.RESET}" if ban_scope == "global" else f"for service {self.CYAN}{service}{self.RESET}"

                # Display different duration for permanent bans
                if exp == -1:
                    duration = f"{self.RED}permanently{self.RESET}"
                else:
                    duration = f"{self.YELLOW}{format_remaining_time(exp)}{self.RESET}"

                success_msg = (
                    f"{self.ICON_LOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been banned {scope_text}\n"
                    f"{self.ICON_CLOCK} Duration: {duration}\n"
                    f"{self.ICON_INFO} Reason: {self.ITALIC}{reason}{self.RESET}"
                )
                return True, self.__format_success(success_msg)
        except BaseException as e:
            return False, self.__format_error(f"Failed to ban {ip}: {e}")
        return False, self.__format_error(f"Failed to ban {ip}")

    def bans(self) -> Tuple[bool, str]:
        """Get all bans from the system"""
        servers = {}

        try:
            ret, resp = self.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            return False, self.__format_error(f"Failed to get bans: {e}")
        if not ret:
            return False, self.__format_error("Failed to retrieve ban information")

        for k, v in resp.items():
            servers[k] = v.get("data", [])

        if self.__redis:
            try:
                servers["redis"] = []
                # Get global bans
                for key in self.__redis.scan_iter("bans_ip_*"):
                    key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                    ip = key_str.replace("bans_ip_", "")
                    data = self.__redis.get(key)
                    if not data:
                        continue
                    exp = self.__redis.ttl(key)
                    try:
                        ban_data = loads(data.decode("utf-8", "replace"))
                        ban_data["ip"] = ip
                        # If permanent flag is set, override TTL to -1
                        if ban_data.get("permanent", False):
                            exp = -1
                        ban_data["exp"] = exp
                        ban_data["ban_scope"] = ban_data.get("ban_scope", "global")
                        servers["redis"].append(ban_data)
                    except Exception as e:
                        self.__logger.debug(format_exc())
                        self.__logger.error(f"Failed to decode ban data for {ip}: {e}")

                # Get service-specific bans
                for key in self.__redis.scan_iter("bans_service_*_ip_*"):
                    key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                    service, ip = key_str.replace("bans_service_", "").split("_ip_")
                    data = self.__redis.get(key)
                    if not data:
                        continue
                    exp = self.__redis.ttl(key)
                    try:
                        ban_data = loads(data.decode("utf-8", "replace"))
                        ban_data["ip"] = ip
                        # If permanent flag is set, override TTL to -1
                        if ban_data.get("permanent", False):
                            exp = -1
                        ban_data["exp"] = exp
                        ban_data["service"] = service
                        ban_data["ban_scope"] = "service"
                        servers["redis"].append(ban_data)
                    except Exception as e:
                        self.__logger.debug(format_exc())
                        self.__logger.error(f"Failed to decode ban data for {ip} on service {service}: {e}")
            except Exception as e:
                self.__logger.error(f"Failed to get bans from redis: {e}")

        servers = {k: sorted(v, key=itemgetter("date")) for k, v in servers.items()}

        width = self.__adapt_display_width()
        cli_str = f"\n{self.BOLD}{self.BG_BLUE}{self.WHITE} BunkerWeb Ban List {self.RESET}\n"

        for server, bans in servers.items():
            cli_str += f"\n{self.BLUE}▓▓▓ {self.BOLD}{server} Bans {self.RESET}{self.BLUE} ▓▓▓{self.RESET}\n"
            cli_str += f"{self.BLUE}{'─' * width}{self.RESET}\n"

            if not bans:
                cli_str += f"{self.YELLOW}{self.ICON_INFO} No bans found{self.RESET}\n"
                cli_str += f"{self.BLUE}{'─' * width}{self.RESET}\n"
                continue

            # Group bans by scope
            global_bans = [ban for ban in bans if ban.get("ban_scope", "global") == "global"]
            service_bans = [ban for ban in bans if ban.get("ban_scope", "") == "service"]

            # Display global bans
            if global_bans:
                cli_str += f"{self.GREEN}{self.BOLD}{self.ICON_GLOBE} Global Bans:{self.RESET}\n"

                for ban in global_bans:
                    banned_country = ban.get("country", "unknown")
                    banned_date = ""

                    # Handle permanent bans
                    if ban.get("permanent", False) or ban.get("exp", 0) == -1:
                        remaining = f"{self.RED}permanent{self.RESET}"
                    else:
                        remaining = f"for {self.CYAN}{format_remaining_time(ban.get('exp', 0))}{self.RESET}"

                    if ban["date"] != -1:
                        banned_date = f"on {self.WHITE}{datetime.fromtimestamp(ban['date']).strftime('%Y-%m-%d at %H:%M:%S')}{self.RESET} "

                    ip_info = f"{self.BOLD}{self.WHITE}{ban['ip']}{self.RESET} [{banned_country}]"
                    cli_str += f"  {self.ICON_LOCK} {ip_info}\n"
                    cli_str += f"     {self.ICON_CLOCK} Banned {banned_date}{remaining}\n"
                    cli_str += f"     {self.ICON_INFO} Reason: {ban.get('reason', 'no reason given')}\n"

                    # Add separator between bans except after the last one
                    if ban != global_bans[-1]:
                        cli_str += f"  {self.BLUE}· · · · · · · · · · · · · · · · · · · · · · ·{self.RESET}\n"

            # Display service bans
            if service_bans:
                if global_bans:  # Add separator if we displayed global bans
                    cli_str += f"{self.BLUE}{'─' * width}{self.RESET}\n"

                cli_str += f"{self.GREEN}{self.BOLD}{self.ICON_SERVER} Service-Specific Bans:{self.RESET}\n"

                for ban in service_bans:
                    service_name = ban.get("service", "unknown")
                    if service_name == "_":
                        service_name = "default server"

                    banned_country = ban.get("country", "unknown")
                    banned_date = ""

                    # Handle permanent bans
                    if ban.get("permanent", False) or ban.get("exp", 0) == -1:
                        remaining = f"{self.RED}permanent{self.RESET}"
                    else:
                        remaining = f"for {self.CYAN}{format_remaining_time(ban.get('exp', 0))}{self.RESET}"

                    if ban["date"] != -1:
                        banned_date = f"on {self.WHITE}{datetime.fromtimestamp(ban['date']).strftime('%Y-%m-%d at %H:%M:%S')}{self.RESET} "

                    ip_info = f"{self.BOLD}{self.WHITE}{ban['ip']}{self.RESET} [{banned_country}]"
                    service_info = f"{self.YELLOW}Service:{self.RESET} {service_name}"
                    cli_str += f"  {self.ICON_LOCK} {ip_info} - {service_info}\n"
                    cli_str += f"     {self.ICON_CLOCK} Banned {banned_date}{remaining}\n"
                    cli_str += f"     {self.ICON_INFO} Reason: {ban.get('reason', 'no reason given')}\n"

                    if ban != service_bans[-1]:
                        cli_str += f"  {self.BLUE}· · · · · · · · · · · · · · · · · · · · · · ·{self.RESET}\n"

            cli_str += f"{self.BLUE}{'─' * width}{self.RESET}\n"

        return True, cli_str

    def plugin_list(self) -> Tuple[bool, str]:
        if not self.__db:
            return False, self.__format_error("This command can only be executed on the scheduler")

        plugins = self.__db.get_plugins()

        if not plugins:
            return True, f"\n{self.YELLOW}{self.ICON_WARNING} No plugins available with CLI commands{self.RESET}\n"

        width = self.__adapt_display_width()
        plugins_str = f"\n{self.BOLD}{self.BG_BLUE}{self.WHITE} BunkerWeb Plugin Commands {self.RESET}\n"

        for plugin in plugins:
            if "bwcli" not in plugin:
                continue

            plugins_str += f"\n{self.MAGENTA}▓▓▓ {self.BOLD}{plugin['id']} ({plugin['type']}) {self.RESET}{self.MAGENTA} ▓▓▓{self.RESET}\n"
            plugins_str += f"{self.MAGENTA}{'─' * width}{self.RESET}\n"

            if not plugin["bwcli"]:
                plugins_str += f"{self.YELLOW}No commands available{self.RESET}\n"
            else:
                for command in plugin["bwcli"]:
                    plugins_str += f"  {self.ICON_INFO} {self.CYAN}{command}{self.RESET}\n"

            plugins_str += f"{self.MAGENTA}{'─' * width}{self.RESET}\n"

        return True, plugins_str

    def custom(self, plugin_id: str, command: str, debug: bool = False, extra_args: Optional[list] = None) -> Tuple[bool, str]:
        if not self.__db:
            return False, self.__format_error("This command can only be executed on the scheduler")

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
            return False, self.__format_error(f"Plugin {self.BOLD}{plugin_id}{self.RESET} not found")
        elif not file_name:
            return False, self.__format_error(f"Command {self.BOLD}{command}{self.RESET} not found for plugin {self.CYAN}{plugin_id}{self.RESET}")

        command_path = (
            Path(sep, "usr", "share", "bunkerweb", "core", plugin_id)
            if plugin_type == "core"
            else (Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin_id) if plugin_type == "pro" else Path(sep, "etc", "bunkerweb", "plugins", plugin_id))
        ).joinpath("bwcli", file_name)

        if not command_path.is_file():
            return False, self.__format_error(
                f"Command {self.BOLD}{command}{self.RESET} not found for plugin {self.CYAN}{plugin_id}{self.RESET}\nFile {command_path} not found"
            )

        cmd = [command_path.as_posix()]
        if extra_args:
            cmd.extend(extra_args)

        self.__logger.debug(f"Executing command {' '.join(cmd)}")

        print(f"\n{self.CYAN}{self.ICON_INFO} Executing {self.BOLD}{' '.join(cmd)}{self.RESET}\n")

        proc = run(cmd, stdin=DEVNULL, stderr=STDOUT, check=False, env=self.__variables | environ | ({"LOG_LEVEL": "DEBUG"} if debug else {}) | ({"DATABASE_URI": self.__db.database_uri} if self.__db else {}))  # type: ignore

        if proc.returncode != 0:
            return False, self.__format_error(
                f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} failed with exit code {proc.returncode}"
            )

        return True, self.__format_success(f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} executed successfully")
