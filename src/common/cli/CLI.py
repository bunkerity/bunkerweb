#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime, timezone
from json import JSONDecodeError, dumps, loads
from operator import itemgetter
from os import environ, get_terminal_size, getenv, sep
from os.path import join
from pathlib import Path
from re import IGNORECASE, compile as re_compile
from stat import S_ISREG
from subprocess import DEVNULL, PIPE, STDOUT, SubprocessError, run
from sys import argv as sys_argv, exit as sys_exit, path as sys_path, stdout as sys_stdout
from traceback import format_exc
from typing import Any, Dict, List, Optional, Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import getLogger  # type: ignore

from common_utils import get_integration, get_os_info, get_redis_client, handle_docker_secrets  # type: ignore
from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore
from crowdsec_unban import execute, preview  # type: ignore
from env_file import parse_env_file  # type: ignore
from redis_keys import ban_ip, unescape  # type: ignore
from support_common import (  # type: ignore
    FILE_TAIL_CAP,
    LOG_DIR,
    REDACTED,
    TOTAL_CAP,
    TRUNCATED_MARK,
    Anonymizer,
    BundleZip,
    alembic_revision,
    build_environment,
    build_plugins_report,
    cut_text,
    is_secret_header,
    mask_config,
    pseudonym,
    read_log_tail,
    service_domains,
)

# bwcli has to resolve the database the running scheduler resolved, so it reads the operator's
# files the way the scheduler's unit exports them: variables.env then the per-service file, later
# wins (src/common/helpers/utils.sh export_env_file, called twice by bunkerweb-scheduler.sh). A
# Scheduler Only install puts DATABASE_URI in scheduler.env and nowhere else, so dropping that
# file left bwcli talking to a different database than the scheduler. misc/install-bunkerweb.sh
# resolves the same URI from the same two files for the upgrade backup
# (`_upgrade_backup_database_uri`), value-based where this is presence-based, so the two differ on
# a key the later file sets to the empty string.
OPERATOR_VARIABLES_PATHS = (Path(sep, "etc", "bunkerweb", "variables.env"), Path(sep, "etc", "bunkerweb", "scheduler.env"))

# /etc/nginx/variables.env is generated output: during the loading render it carries plugin
# defaults for every setting start.sh does not whitelist, DATABASE_URI among them, so a value read
# from it must never beat one an operator wrote. It only fills keys the operator's files leave
# unset.
GENERATED_VARIABLES_PATHS = (Path(sep, "etc", "nginx", "variables.env"),)

VARIABLES_PATHS = OPERATOR_VARIABLES_PATHS + GENERATED_VARIABLES_PATHS

# Present where the scheduler's code is shipped (scheduler, all-in-one, Linux), absent from the BunkerWeb instance image
DB_PATH = Path(sep, "usr", "share", "bunkerweb", "db")

# Present where the scheduler is shipped (scheduler, all-in-one, Linux), absent from the BunkerWeb instance and autoconf images
SCHEDULER_PATH = Path(sep, "usr", "share", "bunkerweb", "scheduler")

# Present only in the all-in-one image
ALL_IN_ONE_PATH = Path(sep, "usr", "share", "bunkerweb", "all-in-one")

# Written by the Linux packages' postinstall.sh when the topology is declared, absent on legacy hosts
INSTALL_TYPE_PATH = Path(sep, "usr", "share", "bunkerweb", "INSTALL_TYPE")
INSTALL_TYPES = ("full", "manager", "worker", "scheduler", "ui", "api")

# `bwcli support` caps: each JSON file is cut at SUPPORT_JSON_CAP, the generated NGINX configuration as a whole at SUPPORT_NGINX_CAP
SUPPORT_JSON_CAP = 5 * 1024 * 1024
SUPPORT_NGINX_CAP = 2 * 1024 * 1024
# nginx directives that carry a credential without a `=` or `:`: `set $variable value;`, `Name value [always];` headers and the quoted `'Name: value'` arguments
# of more_set_headers. They are read as nginx reads them (whitespace and comments across lines, quotes with backslash escapes), not line by line.
SUPPORT_NGINX_DIRECTIVES = frozenset(
    (
        "proxy_set_header",
        "grpc_set_header",
        "add_header",
        "add_trailer",
        "fastcgi_param",
        "uwsgi_param",
        "scgi_param",
        "more_set_headers",
        "more_set_input_headers",
        "set",
    )
)
SUPPORT_NGINX_SECRET_VARIABLE = re_compile(r"\$\w*(?:token|key|secret|password|passwd|session|csrf|cookie|authorization)\w*", IGNORECASE)
SUPPORT_NGINX_MORE_ARGUMENT = re_compile(r"\s*(?P<name>[\w\-]+)\s*:\s*")
# A lone variable (`$http_authorization`) is a reference, not a credential
SUPPORT_NGINX_VARIABLE = re_compile(r"\$(?:\w+|\{\w+\})(?:[ \t]+always)?")
SUPPORT_NGINX_ESCAPE = re_compile(r"\\([\"'\\trn])")
SUPPORT_LIBRARIES = ("sqlalchemy", "alembic", "requests", "redis", "schedule")
SUPPORT_METADATA_KEYS = (
    "is_initialized",
    "first_config_saved",
    "failover",
    "failover_message",
    "scheduler_first_start",
    "autoconf_loaded",
    "pro_overlapped",
    "last_pro_check",
    "last_instances_change",
    "last_custom_configs_change",
    "last_external_plugins_change",
    "last_pro_plugins_change",
)
SUPPORT_LOG_COMMANDS = {
    "Kubernetes": ("kubectl logs <bunkerweb pod>", "kubectl logs <scheduler pod>"),
    "Linux": ("journalctl -u bunkerweb -u bunkerweb-scheduler -u bunkerweb-ui",),
}
SUPPORT_DOCKER_LOG_COMMANDS = ("docker logs <bunkerweb container>", "docker logs <scheduler container>")


def systemctl_state(verb: str) -> str:
    """Output of `systemctl <verb> bunkerweb-scheduler`, empty when systemctl gives no answer."""
    try:
        return run(["systemctl", verb, "bunkerweb-scheduler"], stdout=PIPE, stderr=DEVNULL, text=True, timeout=5).stdout.strip()
    except (OSError, SubprocessError):
        return ""


def support_refusal() -> Optional[str]:
    """Message refusing `bwcli support` where the scheduler does not run, None where it can.

    A stopped or crashed scheduler is not a refusal: the bundle matters most then. Without an answer from systemctl the command is allowed.
    """
    integration = get_integration()

    if not SCHEDULER_PATH.exists():
        exec_command = "kubectl exec <scheduler pod> --" if integration == "Kubernetes" else "docker exec <scheduler container>"
        return f"bwcli support does not run on a BunkerWeb instance or the autoconf controller, run it where the scheduler runs: {exec_command} bwcli support -o - > bundle.zip"

    # The all-in-one image ships the scheduler's code whether or not its entrypoint starts it, and starts it only when SERVICE_SCHEDULER is exactly "yes"
    if ALL_IN_ONE_PATH.exists() and getenv("SERVICE_SCHEDULER") != "yes":
        return "bwcli support does not run here, the scheduler is disabled (SERVICE_SCHEDULER is not yes): run it where the scheduler runs, or enable SERVICE_SCHEDULER"

    if integration != "Linux":
        return None

    # The install-type marker is authoritative when valid, like the installer reads it
    try:
        install_type = INSTALL_TYPE_PATH.read_text().strip()
    except (OSError, ValueError):
        install_type = ""
    if install_type in INSTALL_TYPES:
        if install_type in ("worker", "ui", "api"):
            return f"bwcli support does not run on a host installed as {install_type}, run it on the host where the scheduler runs"
        return None

    # Legacy host without a marker: a worker has the scheduler disabled and stopped
    if systemctl_state("is-enabled") in ("disabled", "masked") and systemctl_state("is-active") == "inactive":
        return "bwcli support does not run on a worker host, run it on the host where the scheduler runs (the manager), or start bunkerweb-scheduler here"

    return None


def resolve_variables(
    operator_paths: Tuple[Path, ...] = OPERATOR_VARIABLES_PATHS,
    generated_paths: Tuple[Path, ...] = GENERATED_VARIABLES_PATHS,
) -> Dict[str, str]:
    """Merge the variables files the way the scheduler's environment ends up merged.

    The operator's files override one another in order, the generated one only fills gaps. The
    process environment is not merged in here: it wins at lookup time, see `__get_variable`.
    """
    variables: Dict[str, str] = {}
    for path in operator_paths:
        if path.is_file():
            variables.update(parse_env_file(path))
    for path in generated_paths:
        if path.is_file():
            for key, value in parse_env_file(path).items():
                if not variables.get(key):
                    variables[key] = value
    return variables


def format_remaining_time(seconds):
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "permanent"

    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    time_parts = []
    if days > 0:
        time_parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        time_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0:
        time_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    if not time_parts:
        return "less than a second"

    if len(time_parts) > 1:
        time_parts[-1] = f"and {time_parts[-1]}"

    return " ".join(time_parts)


def nginx_statement(text: str, pos: int) -> Tuple[List[Tuple[int, int]], int]:
    """Spans of the words of the statement starting at pos (directive name first), and the index after the `;`, `{` or `}` that ends it.

    Comments are skipped, quoted words end at their closing quote and a bare word ends at whitespace, `;` or a `{` that does not open a `${variable}`.
    """
    spans = []
    size = len(text)
    while pos < size:
        char = text[pos]
        if char.isspace():
            pos += 1
        elif char == "#":
            pos = text.find("\n", pos)
            pos = size if pos < 0 else pos
        elif char in ";{}":
            return spans, pos + 1
        else:
            start = pos
            if char in "\"'":
                pos += 1
                while pos < size and text[pos] != char:
                    pos += 2 if text[pos] == "\\" else 1
                pos += 1
            else:
                while pos < size and not text[pos].isspace() and text[pos] != ";" and not (text[pos] == "{" and text[pos - 1] != "$"):
                    pos += 2 if text[pos] == "\\" else 1
            spans.append((start, min(pos, size)))
    return spans, size


def nginx_word(raw: str) -> str:
    """Value nginx gives a raw word: surrounding quotes dropped, backslash escapes decoded."""
    if raw[:1] in ("'", '"'):
        raw = raw[1:-1] if len(raw) > 1 and raw[-1] == raw[0] else raw[1:]
    return SUPPORT_NGINX_ESCAPE.sub(lambda match: {"t": "\t", "r": "\r", "n": "\n"}.get(match[1], match[1]), raw)


def redact_nginx(text: str) -> str:
    """Redact the credentials nginx directives carry without a `=` or `:`: variables named like a secret and credential header values.

    The text is walked statement by statement the way nginx reads it, so a directive name inside a comment or a quoted value is never taken for a directive.
    """
    out = []
    done = 0
    pos = 0
    while pos < len(text):
        spans, pos = nginx_statement(text, pos)
        name = nginx_word(text[spans[0][0] : spans[0][1]]) if spans else ""  # noqa: E203
        if name not in SUPPORT_NGINX_DIRECTIVES:
            continue
        spans = spans[1:]
        edits = []
        if name.startswith("more_set_"):
            for start, end in spans:
                argument = text[start:end]
                quote = argument[0] if argument[0] in "\"'" else ""
                closing = quote if quote and len(argument) > 1 and argument[-1] == quote else ""
                header = SUPPORT_NGINX_MORE_ARGUMENT.match(argument, len(quote))
                if header and is_secret_header(header["name"]):
                    edits.append((start, end, f"{argument[:header.end()]}{REDACTED}{closing}"))
        elif name == "set":
            if len(spans) > 1 and SUPPORT_NGINX_SECRET_VARIABLE.fullmatch(nginx_word(text[spans[0][0] : spans[0][1]])):  # noqa: E203
                edits.append((spans[1][0], spans[-1][1], REDACTED))
        elif len(spans) > 1:
            header_name = nginx_word(text[spans[0][0] : spans[0][1]])  # noqa: E203
            value = " ".join(nginx_word(text[start:end]) for start, end in spans[1:])
            if is_secret_header(header_name) and not SUPPORT_NGINX_VARIABLE.fullmatch(value):
                edits.append((spans[1][0], spans[-1][1], REDACTED))
        for start, end, replacement in edits:
            out.append(text[done:start] + replacement)
            done = end
    out.append(text[done:])
    return "".join(out)


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

    def __init__(self, tolerant_db: bool = False):
        self.__logger = getLogger("CLI")

        # Handle Docker secrets first
        docker_secrets = handle_docker_secrets()
        if docker_secrets:
            self.__logger.info(f"Loaded {len(docker_secrets)} Docker secrets")
            # Update environment with secrets
            environ.update(docker_secrets)

        self.__variables = resolve_variables()
        self.__db = None
        self.__db_error = None

        if DB_PATH.exists():
            from Database import Database, DatabaseInitError, mask_db_uri  # type: ignore

            self.__logger.info("Getting variables from database")

            if tolerant_db:
                # Database() exits the process on any failure, bwcli support builds it to raise and keeps going without it
                try:
                    self.__db = Database(self.__logger, sqlalchemy_string=self.__get_variable("DATABASE_URI", None), exit_on_error=False)
                except Exception as e:
                    self.__db_error = (
                        str(e) if isinstance(e, DatabaseInitError) else f"Cannot initialize the database: {type(e).__name__}: {mask_db_uri(str(e))}"
                    )
                    self.__logger.warning(self.__db_error)
            else:
                self.__db = Database(self.__logger, sqlalchemy_string=self.__get_variable("DATABASE_URI", None))

            if self.__db:
                # SQLAlchemy creates a SQLite file on connect, so an unresolved DATABASE_URI gives a
                # connection that succeeds against an empty database and a traceback on the first
                # query. Say which database is missing its schema instead.
                metadata = self.__db.get_metadata()
                if metadata.get("default") or not metadata.get("is_initialized"):
                    message = (
                        "The database has no BunkerWeb schema. Check that DATABASE_URI is set in "
                        f"{' or '.join(path.as_posix() for path in VARIABLES_PATHS)} or in the environment, "
                        "and that the scheduler has already initialized it."
                    )
                    if not tolerant_db:
                        self.__logger.error(message)
                        sys_exit(1)

                    # bwcli support still has logs, nginx and environment to export: it records this in the manifest
                    self.__logger.warning(message)
                    self.__db_error = message
                    self.__db = None
                else:
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
            redis_db=self.__get_variable("REDIS_DATABASE", "0"),
            redis_timeout=self.__get_variable("REDIS_TIMEOUT", "1000.0"),
            redis_keepalive_pool=self.__get_variable("REDIS_KEEPALIVE_POOL", "10"),
            redis_ssl=self.__get_variable("REDIS_SSL", "no") == "yes",
            # Verify unless told not to: bwcli verified by redis-py default before this existed.
            redis_ssl_verify=self.__get_variable("REDIS_SSL_VERIFY", "yes") != "no",
            redis_username=self.__get_variable("REDIS_USERNAME", None) or None,
            redis_password=self.__get_variable("REDIS_PASSWORD", None) or None,
            redis_sentinel_hosts=self.__get_variable("REDIS_SENTINEL_HOSTS", []),
            redis_sentinel_username=self.__get_variable("REDIS_SENTINEL_USERNAME", None) or None,
            redis_sentinel_password=self.__get_variable("REDIS_SENTINEL_PASSWORD", None) or None,
            redis_sentinel_master=self.__get_variable("REDIS_SENTINEL_MASTER", ""),
            redis_cluster_nodes=self.__get_variable("REDIS_CLUSTER_NODES", ""),
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

        # API only falls back to the environment, which a shell running bwcli does not have.
        # The token lives in the database (or in variables.env), so read it from there.
        api_token = self.__get_variable("API_TOKEN") or None
        self.__api_token = api_token

        if self.__db:
            for db_instance in self.__db.get_instances():
                try:
                    # Centralized builder handles scheme/port/host
                    self.apis.append(API.from_instance(db_instance, token=api_token))
                except ValueError as e:
                    self.__logger.warning(f"Skipping invalid instance {db_instance.get('hostname', '<missing>')}: {e}")
        else:
            # Build single local API endpoint from environment variables
            server_name = self.__get_variable("API_SERVER_NAME", "bwapi") or "bwapi"
            endpoint = API.build_endpoint(
                "127.0.0.1",
                port=int(self.__get_variable("API_HTTP_PORT", "5000") or "5000"),
                listen_https=(self.__get_variable("API_LISTEN_HTTPS", "no") or "no").lower() == "yes",
                https_port=int(self.__get_variable("API_HTTPS_PORT", "5443") or "5443"),
            )
            self.apis.append(API(endpoint, server_name, token=api_token))

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

    def __lookup_lease(self, ip: str, ban_scope: str, service: Optional[str]) -> Tuple[bool, List[str]]:
        """Ask every instance for the CrowdSec lease of this ban.

        Returns (found, failures). A lease may live on one instance only (written while Redis was
        unreachable), so absence needs a completed negative from every instance: any failed,
        non-200 or malformed reply is listed in failures and the check is incomplete.
        """
        data = {"ip": ip, "ban_scope": ban_scope}
        if ban_scope == "service" and service:
            data["service"] = service
        failures = []
        for api in self.apis:
            sent, err, status, resp = api.request("POST", "/lease_lookup", data=data, timeout=(5, 10))
            if not sent or status != 200:
                failures.append(f"{api.endpoint}: {err if not sent else f'status {status}'}")
                continue
            reply = resp.get("data") if isinstance(resp, dict) else None
            if not isinstance(reply, dict) or not isinstance(reply.get("found"), bool):
                failures.append(f"{api.endpoint}: malformed lease lookup reply")
                continue
            if not reply["found"]:
                continue
            row = reply.get("row")
            if isinstance(row, dict) and isinstance(row.get("reason_data"), dict):
                return True, failures
            failures.append(f"{api.endpoint}: malformed lease row")
        return False, failures

    def __format_lease_preview(self, ip: str, current: dict) -> str:
        lines = [f"IP {ip} is banned by CrowdSec. Unbanning it deletes these CrowdSec decisions first, then removes the BunkerWeb ban:"]
        for decision in current["decisions"]:
            lines.append(
                f"  {decision.get('scope')} {decision.get('value')}: {decision.get('type')}, origin {decision.get('origin')}, "
                f"scenario {decision.get('scenario')} (connection {decision.get('connection_id')})"
            )
        if not current["decisions"]:
            lines.append("  no active CrowdSec ban decision, only the BunkerWeb ban is removed")
        if current["unavailable"]:
            lines.append(f"{self.ICON_WARNING} Unavailable, the result will be partial: {', '.join(current['unavailable'])}")
        if current["warnings"]["list_origin"]:
            lines.append(
                f"{self.ICON_WARNING} Some decisions come from a CrowdSec list or the community blocklist and may come back: add the IP to a CrowdSec allowlist"
            )
        if current["warnings"]["range"]:
            lines.append(f"{self.ICON_WARNING} A decision covers a range: leases already created for other IPs in that range stay until their TTL ends")
        if current["management_missing"]:
            lines.append(f"{self.ICON_WARNING} CrowdSec management credentials are missing on: {', '.join(current['management_missing'])}")
        lines.append("Run the command again with -confirm to apply.")
        return "\n".join(lines)

    def __unban_lease(self, ip: str, ban_scope: str, service: Optional[str], confirm: bool) -> Tuple[bool, str]:
        if not self.__db:
            return (
                False,
                f"IP {ip} is banned by CrowdSec. Removing a CrowdSec ban needs the scheduler host (database access): use the Web UI or the API instead",
            )
        try:
            client = CrowdSecClient(self.__db, token=self.__api_token)
            current = preview(client, ip, ban_scope, service)
            if not confirm:
                return False, self.__format_lease_preview(ip, current)
            result = execute(client, ip, ban_scope, service, [decision["key"] for decision in current["decisions"]])
        except CrowdSecError as e:
            return False, f"Failed to unban {ip} from CrowdSec: {e}"
        if result["status"] == "changed":
            return False, f"The CrowdSec decisions for {ip} changed since the preview, nothing was changed: run the command again"
        if result["status"] != "success":
            lines = [f"Partial CrowdSec result for {ip}, the BunkerWeb lease is kept where a step failed: run the command again to retry"]
            lines += [f"failed {failure.get('key') or failure.get('connection_id')}: {failure['error']}" for failure in result["failed"]]
            lines += [f"lease not removed on {failure['instance']}: {failure['error']}" for failure in result["lease_failed"]]
            lines += [f"instance down, its lease ends on its own: {host}" for host in result["down"]]
            lines += [f"unavailable: {name}" for name in result["unavailable"]]
            return False, "\n".join(lines)
        return True, f"CrowdSec decisions deleted: {len(result['deleted'])}, already absent: {len(result['already_absent'])}"

    def unban(self, ip: str, service: Optional[str] = None, confirm: bool = False) -> Tuple[bool, str]:
        """Unban an IP address globally or from a specific service"""
        # Always use API as the source of truth for unban
        ban_scope = "service" if service else "global"
        try:
            if not self.apis:
                return False, self.__format_error(f"Failed to unban {ip}: no BunkerWeb instance to send the request to")
            lease, failures = self.__lookup_lease(ip, ban_scope, service)
            # The explicit ban is always removed, a lease or an incomplete lease check never skips it
            ok, explicit = self.__unban_explicit(ip, ban_scope, service)
            if not lease and not failures:
                return ok, explicit
            lines = [f"The explicit unban {'succeeded' if ok else 'failed'}"]
            if lease:
                lease_ok, lease_text = self.__unban_lease(ip, ban_scope, service, confirm)
                ok = ok and lease_ok
                lines.append(lease_text)
            if failures:
                ok = False
                lines.append(f"Could not check every BunkerWeb instance for a CrowdSec ban of {ip}: " + "; ".join(failures))
            message = "\n".join(lines)
            return ok, self.__format_success(message) if ok else self.__format_error(message)
        except BaseException as e:
            return False, self.__format_error(f"Failed to unban {ip}: {e}")

    def __unban_explicit(self, ip: str, ban_scope: str, service: Optional[str]) -> Tuple[bool, str]:
        data = {"ip": ip, "ban_scope": ban_scope}
        if service:
            data["service"] = service
        # send_to_apis returns (ok, responses); testing the tuple itself is always truthy
        ok, _ = self.send_to_apis("POST", "/unban", data=data)
        if ok:
            if service:
                success_msg = f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned from service {self.CYAN}{service}{self.RESET}"
            else:
                success_msg = f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned {self.GREEN}globally{self.RESET}"
            return True, self.__format_success(success_msg)
        return False, self.__format_error(f"Failed to unban {ip}")

    def ban(self, ip: str, exp: float, reason: str, service: str = "bwcli") -> Tuple[bool, str]:
        """Ban an IP address globally or from a specific service"""
        # Auto-set scope to service if a non-default service is specified
        ban_scope = "global"
        if service != "bwcli" and service:
            ban_scope = "service"

        # Validate the service name if scope is service
        if ban_scope == "service":
            services = []
            try:
                if self.__db:
                    config = self.__db.get_config(global_only=True, filtered_settings=("SERVER_NAME",))
                    services = config.get("SERVER_NAME", [])
                else:
                    srv = self.__get_variable("SERVER_NAME", "")
                    services = srv.split() if isinstance(srv, str) else []
                if isinstance(services, str):
                    services = services.split()
                if not service or service == "bwcli" or service not in services:
                    self.__logger.warning(f"Invalid service '{service}' for IP {ip}, defaulting to global ban")
                    ban_scope = "global"
                    service = "bwcli"
            except Exception as e:
                self.__logger.warning(f"Error validating service: {e}, defaulting to global ban")
                ban_scope = "global"
                service = "bwcli"

        try:
            data = {"ip": ip, "exp": exp, "reason": reason, "service": service or "bwcli", "ban_scope": ban_scope}
            if not self.apis:
                return False, self.__format_error(f"Failed to ban {ip}: no BunkerWeb instance to send the request to")
            # send_to_apis returns (ok, responses); testing the tuple itself is always truthy
            ok, _ = self.send_to_apis("POST", "/ban", data=data)
            if ok:
                scope_text = f"{self.GREEN}globally{self.RESET}" if ban_scope == "global" else f"for service {self.CYAN}{service}{self.RESET}"
                if not exp:
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

    def __collect_redis_bans(self, pattern: str, scope: str, kind: str = "ban") -> list:
        """Read every ban matching a pattern in two round trips instead of 3N.

        scan_iter without count leaves Redis on its COUNT=10 default, so key
        discovery costs one round trip per ten keys, and a get plus a ttl per key
        adds two more each. Both are collapsed here.
        """
        keys = list(self.__redis.scan_iter(pattern, count=1000))
        if not keys:
            return []

        pipe = self.__redis.pipeline(transaction=False)
        for key in keys:
            pipe.get(key)
            pipe.ttl(key)
        results = pipe.execute()

        bans = []
        for idx, key in enumerate(keys):
            data = results[2 * idx]
            if not data:
                continue
            exp = results[2 * idx + 1]
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            raw_value = data.decode("utf-8", "replace") if isinstance(data, bytes) else data

            # Leases (CrowdSec) live under bans_cs_*, explicit bans under bans_*
            prefix = "bans_cs_" if kind == "crowdsec_lease" else "bans_"
            if scope == "global":
                ip = ban_ip(key_str.replace(f"{prefix}ip_", ""))
                service = "unknown"
            else:
                service, ip = key_str.replace(f"{prefix}service_", "").rsplit("_ip_", 1)
                service, ip = unescape(service), ban_ip(ip)

            try:
                ban_data = loads(raw_value)
            except (JSONDecodeError, ValueError) as e:
                self.__logger.warning(f"Failed to decode ban data for {ip}, using raw value as reason: {e}")
                ban_data = {"reason": raw_value, "service": service, "date": 0, "country": "unknown", "ban_scope": scope, "permanent": False}

            ban_data["ip"] = ip
            ban_data["kind"] = kind
            ban_data.setdefault("date", 0)
            # If permanent flag is set, override TTL to 0
            if ban_data.get("permanent", False):
                exp = 0
            ban_data["exp"] = exp
            if scope == "global":
                ban_data["ban_scope"] = ban_data.get("ban_scope", "global")
            else:
                ban_data["service"] = service
                ban_data["ban_scope"] = "service"
            bans.append(ban_data)
        return bans

    @staticmethod
    def __format_kind(ban: dict) -> str:
        return "CrowdSec lease" if ban.get("kind") == "crowdsec_lease" else "ban"

    def bans(self) -> Tuple[bool, str]:
        """Get all bans from the system"""
        servers = {}

        if not self.apis:
            return False, self.__format_error("Failed to retrieve ban information: no BunkerWeb instance to query")

        try:
            ret, resp = self.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            return False, self.__format_error(f"Failed to get bans: {e}")
        if not ret or not resp:
            return False, self.__format_error("Failed to retrieve ban information")

        for k, v in resp.items():
            servers[k] = v.get("data", [])

        if self.__redis:
            try:
                servers["redis"] = (
                    self.__collect_redis_bans("bans_ip_*", "global")
                    + self.__collect_redis_bans("bans_service_*_ip_*", "service")
                    + self.__collect_redis_bans("bans_cs_ip_*", "global", "crowdsec_lease")
                    + self.__collect_redis_bans("bans_cs_service_*_ip_*", "service", "crowdsec_lease")
                )
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
                    if ban.get("permanent", False) or not ban.get("exp", 0):
                        remaining = f"{self.RED}permanent{self.RESET}"
                    else:
                        remaining = f"for {self.CYAN}{format_remaining_time(ban.get('exp', 0))}{self.RESET}"

                    if ban["date"] >= 1:
                        banned_date = f"on {self.WHITE}{datetime.fromtimestamp(ban['date']).strftime('%Y-%m-%d at %H:%M:%S')}{self.RESET} "

                    ip_info = f"{self.BOLD}{self.WHITE}{ban['ip']}{self.RESET} [{banned_country}]"
                    cli_str += f"  {self.ICON_LOCK} {ip_info}\n"
                    cli_str += f"     {self.ICON_CLOCK} Banned {banned_date}{remaining}\n"
                    cli_str += f"     {self.ICON_INFO} Reason: {ban.get('reason', 'no reason given')}\n"
                    cli_str += f"     {self.ICON_INFO} Kind: {self.__format_kind(ban)}\n"

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
                    if ban.get("permanent", False) or not ban.get("exp", 0):
                        remaining = f"{self.RED}permanent{self.RESET}"
                    else:
                        remaining = f"for {self.CYAN}{format_remaining_time(ban.get('exp', 0))}{self.RESET}"

                    if ban["date"] >= 1:
                        banned_date = f"on {self.WHITE}{datetime.fromtimestamp(ban['date']).strftime('%Y-%m-%d at %H:%M:%S')}{self.RESET} "

                    ip_info = f"{self.BOLD}{self.WHITE}{ban['ip']}{self.RESET} [{banned_country}]"
                    service_info = f"{self.YELLOW}Service:{self.RESET} {service_name}"
                    cli_str += f"  {self.ICON_LOCK} {ip_info} - {service_info}\n"
                    cli_str += f"     {self.ICON_CLOCK} Banned {banned_date}{remaining}\n"
                    cli_str += f"     {self.ICON_INFO} Reason: {ban.get('reason', 'no reason given')}\n"
                    cli_str += f"     {self.ICON_INFO} Kind: {self.__format_kind(ban)}\n"

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
        available_commands = []

        for db_plugin in self.__db.get_plugins():
            if db_plugin["id"] == plugin_id:
                found = True
                plugin_type = db_plugin["type"]
                available_commands = list(db_plugin.get("bwcli", {}).keys()) if db_plugin.get("bwcli") else []
                file_name = db_plugin["bwcli"].get(command, None) if db_plugin.get("bwcli") else None
                break

        if not found:
            return False, self.__format_error(f"Plugin {self.BOLD}{plugin_id}{self.RESET} not found")
        elif not file_name:
            error_msg = f"Command {self.BOLD}{command}{self.RESET} not found for plugin {self.CYAN}{plugin_id}{self.RESET}"
            if available_commands:
                error_msg += f"\nAvailable commands: {self.YELLOW}{', '.join(available_commands)}{self.RESET}"
            else:
                error_msg += f"\nNo CLI commands available for plugin {self.CYAN}{plugin_id}{self.RESET}"
            return False, self.__format_error(error_msg)

        plugin_base_path = (
            Path(sep, "usr", "share", "bunkerweb", "core", plugin_id)
            if plugin_type == "core"
            else (Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin_id) if plugin_type == "pro" else Path(sep, "etc", "bunkerweb", "plugins", plugin_id))
        )

        command_path = plugin_base_path.joinpath("bwcli", file_name)

        if not command_path.is_file():
            return False, self.__format_error(
                f"Command {self.BOLD}{command}{self.RESET} not found for plugin {self.CYAN}{plugin_id}{self.RESET}\nFile {command_path} not found"
            )

        # Check if it's a Python module
        if file_name.endswith(".py"):
            return self.__exec_plugin_module(command_path, plugin_base_path, plugin_id, command, debug, extra_args)
        return self.__exec_external_command(command_path, plugin_id, command, debug, extra_args)

    def __exec_plugin_module(
        self, command_path: Path, plugin_base_path: Path, plugin_id: str, command: str, debug: bool = False, extra_args: Optional[list] = None
    ) -> Tuple[bool, str]:
        """Execute a Python module as a plugin command, similar to JobScheduler approach."""
        from importlib.util import module_from_spec, spec_from_file_location

        # Convert to absolute paths
        abs_command_path = command_path.resolve()
        abs_plugin_path = plugin_base_path.resolve()

        # Get the command directory (parent of the command file, e.g., .../<plugin>/bwcli)
        cmd_dir = abs_command_path.parent.as_posix()
        # Plugin root directory (e.g., .../<plugin>)
        plugin_dir = abs_plugin_path.as_posix()

        # Validate paths exist
        if not abs_command_path.exists():
            return False, self.__format_error(f"Plugin command file not found: {abs_command_path}")

        if not abs_plugin_path.exists():
            return False, self.__format_error(f"Plugin directory not found: {abs_plugin_path}")

        self.__logger.debug(f"Adding to sys.path: plugin_dir={plugin_dir}, cmd_dir={cmd_dir}")

        # Add plugin root and command directory to sys.path temporarily
        # Plugin root should be added first so imports work correctly
        added_paths = []
        for p in (plugin_dir, cmd_dir):
            if p and p not in sys_path:
                sys_path.insert(0, p)
                added_paths.append(p)
                self.__logger.debug(f"Added {p} to sys.path")

        try:
            # Prepare environment similar to JobScheduler
            old_env = environ.copy()
            plugin_env = self.__variables.copy()
            plugin_env.update(environ)
            if debug:
                plugin_env["LOG_LEVEL"] = "DEBUG"
            if self.__db:
                plugin_env["DATABASE_URI"] = self.__db.database_uri

            # Store extra args in environment for the module to access
            if extra_args:
                plugin_env["CLI_EXTRA_ARGS"] = " ".join(extra_args)

            environ.clear()
            environ.update(plugin_env)

            self.__logger.debug(f"Executing Python module {abs_command_path.as_posix()}")
            self.__logger.info(f"Executing {plugin_id}:{command} (Python module)")

            # Backup and modify sys.argv to prevent argument parsing conflicts
            old_argv = sys_argv.copy()
            # Set sys.argv to just the script name and any extra args
            sys_argv[:] = [abs_command_path.as_posix()] + (extra_args or [])

            self.__logger.debug(f"sys.argv for module: {sys_argv}")

            # Load and execute the module
            spec = spec_from_file_location(f"{plugin_id}_{command}", abs_command_path.as_posix())
            if spec is None:
                return False, self.__format_error(f"Failed to create module spec for {abs_command_path}")

            if spec.loader is None:
                return False, self.__format_error(f"Failed to create module loader for {abs_command_path}")

            self.__logger.debug(f"Module spec: {spec}")

            module = module_from_spec(spec)

            # Execute the module
            try:
                spec.loader.exec_module(module)
                return True, self.__format_success(
                    f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} executed successfully"
                )
            except SystemExit as e:
                exit_code = e.code if isinstance(e.code, int) else 1
                if exit_code == 0:
                    return True, self.__format_success(
                        f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} executed successfully"
                    )
                else:
                    return False, self.__format_error(
                        f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} failed with exit code {exit_code}"
                    )
            except Exception as e:
                self.__logger.error(f"Exception while executing command '{command}' from plugin '{plugin_id}': {e}")
                self.__logger.debug(format_exc())
                return False, self.__format_error(f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} failed: {e}")

        finally:
            # Restore original sys.argv
            if "old_argv" in locals():
                sys_argv[:] = old_argv

            # Restore original environment
            environ.clear()
            environ.update(old_env)

            # Remove any paths we added to sys.path (in reverse order of addition)
            for p in reversed(added_paths):
                if p in sys_path:
                    with suppress(ValueError):
                        sys_path.remove(p)
                        self.__logger.debug(f"Removed {p} from sys.path")

    def __exec_external_command(
        self, command_path: Path, plugin_id: str, command: str, debug: bool = False, extra_args: Optional[list] = None
    ) -> Tuple[bool, str]:
        """Execute an external command (legacy support for non-Python commands)."""
        cmd = [command_path.as_posix()]
        if extra_args:
            cmd.extend(extra_args)

        self.__logger.debug(f"Executing external command {' '.join(cmd)}")
        print(f"\n{self.CYAN}{self.ICON_INFO} Executing {self.BOLD}{' '.join(cmd)}{self.RESET}\n")

        # Prepare environment
        cmd_env = self.__variables.copy()
        cmd_env.update(environ)
        if debug:
            cmd_env["LOG_LEVEL"] = "DEBUG"
        if self.__db:
            cmd_env["DATABASE_URI"] = self.__db.database_uri

        proc = run(cmd, stdin=DEVNULL, stderr=STDOUT, check=False, env=cmd_env)

        if proc.returncode != 0:
            return False, self.__format_error(
                f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} failed with exit code {proc.returncode}"
            )

        return True, self.__format_success(f"Command {self.BOLD}{command}{self.RESET} for plugin {self.CYAN}{plugin_id}{self.RESET} executed successfully")

    def support(self, output: Optional[str] = None, anonymize: bool = True) -> Tuple[bool, str]:
        """Write the support bundle: credentials are always redacted, IP addresses and service domains are anonymized unless anonymize is False.

        A failing section is listed in the manifest and the rest of the bundle is still written, so this only fails when the archive cannot be.
        """
        to_stdout = output == "-"
        if to_stdout and sys_stdout.isatty():
            return False, self.__format_error("Refusing to write a zip to the terminal: redirect stdout to a file or use -o <path>")

        now = datetime.now(timezone.utc)
        db = self.__db
        integration = get_integration()
        unavailable: List[Dict[str, str]] = []
        domains = set()
        if db:
            try:
                domains = service_domains(db.get_config(methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",)))
            except Exception as e:
                unavailable.append({"item": "service domains", "reason": f"{type(e).__name__}: {e}, domains are not anonymized"})
        anonymizer = Anonymizer(domains, anonymize)
        if self.__db_error:
            unavailable.append({"item": "database", "reason": anonymizer.redact(self.__db_error)})
        bundle = BundleZip(TOTAL_CAP)

        def add_text(name: str, text: str, cap: int, note: str = "") -> None:
            """Add text cut to its own cap and to what is left of the total budget, keeping the beginning."""
            room = max(bundle.room, 0)
            limit = min(cap, room)
            cut = len(text.encode("utf-8")) > limit
            if cut:
                text, _ = cut_text(text, max(limit - len(TRUNCATED_MARK), 0))
                if len(text.encode("utf-8")) > limit:
                    text = ""
            if cut and not text:
                unavailable.append({"item": name, "reason": "total size cap reached"})
                return
            bundle.add(name, text, note=note)
            if cut:
                bundle.files[-1]["truncated"] = f"kept the first {limit} bytes, " + ("total size cap reached" if limit == room else "file size cap reached")

        def add_json(name: str, data: Any, note: str = "") -> None:
            add_text(name, dumps(anonymizer.scrub(data), indent=2, default=str), SUPPORT_JSON_CAP, note)

        def section(name: str, build) -> None:
            try:
                add_json(name, build())
            except Exception as e:
                self.__logger.debug(format_exc())
                unavailable.append({"item": name, "reason": anonymizer.redact(f"{type(e).__name__}: {e}")})

        def require_db() -> None:
            if not db:
                raise RuntimeError(self.__db_error or "The database module is not installed on this host")

        def environment() -> Dict[str, Any]:
            metadata = db.get_metadata() if db else {}
            report = build_environment(
                metadata=metadata,
                integration=integration,
                instances=db.get_instances() if db else [],
                service_count=len(db.get_services()) if db else 0,
                db_dialect=db.sql_engine.dialect.name if db else "unknown",
                db_revision=alembic_revision(db) if db else None,
                library_names=SUPPORT_LIBRARIES,
                pseudonymize_hosts=anonymize,
            )
            report["os"] = get_os_info()
            report["metadata"] = {key: metadata.get(key) for key in SUPPORT_METADATA_KEYS}
            return report

        def health(api: API) -> Dict[str, Any]:
            sent, err, status, response = api.request("GET", "/health", timeout=(3, 5))
            return {"reachable": sent, "status": status, "response": response, "error": None if sent else err}

        def instances() -> List[Dict[str, Any]]:
            if db:
                targets: List[Tuple[Dict[str, Any], Any]] = []
                for row in db.get_instances():
                    try:
                        targets.append((row, API.from_instance(row, token=self.__api_token)))
                    except ValueError as e:
                        targets.append((row, e))
            else:
                targets = [({"hostname": api.endpoint}, api) for api in self.apis]
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(
                    pool.map(lambda target: {"reachable": False, "error": str(target[1])} if isinstance(target[1], ValueError) else health(target[1]), targets)
                )
            report = []
            for (row, _), result in zip(targets, results):
                if anonymize and db:
                    hostname = str(row["hostname"])
                    row = {**row, "hostname": pseudonym(hostname)}
                    result = {**result, "error": result["error"].replace(hostname, row["hostname"]) if result.get("error") else None}
                report.append({**row, "health": result})
            return report

        def config() -> Dict[str, Any]:
            require_db()
            settings = {name: setting for plugin in db.get_plugins(_type="all") for name, setting in plugin.get("settings", {}).items()}
            with suppress(OSError, ValueError):
                settings.update(loads(Path(sep, "usr", "share", "bunkerweb", "settings.json").read_text(encoding="utf-8")))
            return mask_config(db.get_config(methods=True, with_drafts=True), settings)

        def plugins() -> Dict[str, Any]:
            require_db()
            roots = {
                "core": Path(sep, "usr", "share", "bunkerweb", "core"),
                "external": Path(sep, "etc", "bunkerweb", "plugins"),
                "pro": Path(sep, "etc", "bunkerweb", "pro", "plugins"),
            }
            return build_plugins_report(db.get_plugins(_type="all"), roots)

        def jobs() -> Dict[str, Any]:
            require_db()
            report = db.get_jobs()
            for job in report.values():
                job["last_run"] = job["history"][0] if job["history"] else None
                job.pop("cache")
            cache_files = []
            for cache in db.get_jobs_cache_files(with_data=False):
                # Read one file at a time, a chunked blob is only sized once reassembled and the data is dropped right away
                data = db.get_job_cache_file(cache["job_name"], cache["file_name"], service_id=cache["service_id"] or "")
                cache_files.append({**cache, "service_id": anonymizer.pseudonymize(cache["service_id"] or ""), "bytes": len(data) if data else 0})
            return {"jobs": report, "cache_files": cache_files}

        def custom_configs() -> List[Dict[str, Any]]:
            require_db()
            return [
                {
                    "name": custom_config["name"],
                    "type": custom_config["type"],
                    "service": anonymizer.pseudonymize(custom_config["service_id"] or ""),
                    "method": custom_config["method"],
                    "checksum": custom_config["checksum"],
                    "is_draft": custom_config["is_draft"],
                    "content": "[REDACTED]",
                }
                for custom_config in db.get_custom_configs(with_drafts=True, with_data=False)
            ]

        section("environment.json", environment)
        section("instances.json", instances)
        section("config.json", config)
        section("plugins.json", plugins)
        section("jobs.json", jobs)
        section("custom_configs.json", custom_configs)

        logs = []
        for path in sorted(Path(LOG_DIR).glob("*.log")):
            report = {"path": path.as_posix()}
            logs.append(report)
            try:
                # A FIFO without a writer blocks open() forever
                if not S_ISREG(path.stat().st_mode):
                    report["status"] = "skipped: not a regular file (stream or device)"
                    continue
                text, size = read_log_tail(path.as_posix(), FILE_TAIL_CAP)
            except OSError as e:
                report["status"] = f"unreadable: {e.strerror or type(e).__name__}"
                continue
            text = anonymizer.redact(text)
            report.update({"status": "included", "file_bytes": size, "cut_to_last_bytes": FILE_TAIL_CAP if size > FILE_TAIL_CAP else None})
            bundle.add(f"logs/{path.name}", text, note=path.as_posix())
        if not any(report["status"] == "included" for report in logs):
            commands = SUPPORT_LOG_COMMANDS.get(integration, SUPPORT_DOCKER_LOG_COMMANDS)
            unavailable.append(
                {"item": "logs", "reason": f"no log file in {LOG_DIR}, the logs go to stdout and stderr, collect them with: " + "; ".join(commands)}
            )

        nginx_path = Path(sep, "etc", "nginx")
        if nginx_path.is_dir():
            try:
                parts, size = [], 0
                for path in sorted(nginx_path.rglob("*.conf")):
                    if size >= SUPPORT_NGINX_CAP:
                        break
                    if path.is_symlink() or not path.is_file():
                        continue
                    content = anonymizer.redact(redact_nginx(path.read_text(encoding="utf-8", errors="replace")))
                    parts.append(f"# ---- {anonymizer.redact(path.as_posix())} ----\n{content}\n")
                    size += len(parts[-1])
                add_text("nginx/etc-nginx-conf.txt", "".join(parts), SUPPORT_NGINX_CAP, f"the *.conf files of {nginx_path.as_posix()}")
            except OSError as e:
                unavailable.append({"item": "nginx/etc-nginx-conf.txt", "reason": f"unreadable: {e.strerror or type(e).__name__}"})
        else:
            unavailable.append({"item": "nginx/etc-nginx-conf.txt", "reason": f"{nginx_path.as_posix()} does not exist on this host"})

        data = bundle.finish(
            {
                "generated_at": now.isoformat(),
                "command": "bwcli support",
                "integration": integration,
                "anonymization": {
                    "mode": "anonymized" if anonymize else "not anonymized (--no-anonymize)",
                    "credentials": "always redacted, the license key and the database password are never collected",
                    "ip_addresses_and_domains": "replaced by placeholders" if anonymize else "kept as they are",
                },
                "caps": {"file_tail_bytes": FILE_TAIL_CAP, "json_bytes": SUPPORT_JSON_CAP, "nginx_config_bytes": SUPPORT_NGINX_CAP, "total_bytes": TOTAL_CAP},
                "logs": logs,
                "unavailable": unavailable,
            }
        )

        if to_stdout:
            sys_stdout.buffer.write(data)
            sys_stdout.buffer.flush()
            return True, f"Support bundle written to stdout ({len(data)} bytes)"

        path = Path(output or f"bunkerweb-support-{now.strftime('%Y%m%dT%H%M%SZ')}.zip")
        try:
            path.write_bytes(data)
        except OSError as e:
            return False, self.__format_error(f"Failed to write {path}: {e.strerror or e}")
        print(path.resolve())
        return True, f"Support bundle written to {path.resolve()} ({len(data)} bytes)"
