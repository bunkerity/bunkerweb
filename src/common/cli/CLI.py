#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
from json import JSONDecodeError, dumps, loads
from operator import itemgetter
from os import W_OK, access, environ, get_terminal_size, getenv, sep
from os.path import join
from pathlib import Path
from posixpath import normpath
from re import DOTALL, IGNORECASE, compile as re_compile, escape as re_escape
from shutil import which
from socket import create_connection
from stat import S_ISREG
from subprocess import DEVNULL, PIPE, STDOUT, SubprocessError, run
from sys import argv as sys_argv, exit as sys_exit, path as sys_path, stdout as sys_stdout
from traceback import format_exc
from typing import Any, Collection, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from base_api_client import ApiClientError, ApiUnavailableError, BaseApiClient  # type: ignore
from custom_configs_validation import TYPE_ERROR_MESSAGE, normalize_type as normalize_custom_config_type, validate_name as validate_custom_config_name  # type: ignore
from logger import getLogger  # type: ignore

from common_utils import bytes_hash, get_integration, get_os_info, get_redis_client, handle_docker_secrets, parse_host  # type: ignore
from env_file import parse_env_file  # type: ignore
from ip_identity import normalize_ip  # type: ignore
from redis_keys import ban_ip, is_cluster, unescape  # type: ignore
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


# Present where the scheduler is shipped (scheduler, all-in-one, Linux), absent from the BunkerWeb instance and autoconf images
SCHEDULER_PATH = Path(sep, "usr", "share", "bunkerweb", "scheduler")

# Present only in the all-in-one image
ALL_IN_ONE_PATH = Path(sep, "usr", "share", "bunkerweb", "all-in-one")

# Written by the Linux packages' postinstall.sh when the topology is declared, absent on legacy hosts
INSTALL_TYPE_PATH = Path(sep, "usr", "share", "bunkerweb", "INSTALL_TYPE")
INSTALL_TYPES = ("full", "manager", "worker", "scheduler", "ui", "api")

# Where `bwcli support` reads the generated NGINX configuration
NGINX_PATH = Path(sep, "etc", "nginx")

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
SUPPORT_NGINX_VARIABLE_NAME = re_compile(r"\$(?:(\w+)|\{(\w+)\})")
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
    operator_paths: Optional[Tuple[Path, ...]] = None,
    generated_paths: Optional[Tuple[Path, ...]] = None,
) -> Dict[str, str]:
    """Merge the variables files the way the scheduler's environment ends up merged.

    The operator's files override one another in order (later wins, empty value included, the way
    `export_env_file` does it), the generated one only fills gaps. The process environment is not
    merged in here: it wins at lookup time, see `__get_variable`.

    The two path tuples are resolved from the module globals at CALL time, not bound as defaults:
    they are built with the real `Path` at import, so the unit tests substitute them by patching
    the module attributes.
    """
    operator_paths = OPERATOR_VARIABLES_PATHS if operator_paths is None else operator_paths
    generated_paths = GENERATED_VARIABLES_PATHS if generated_paths is None else generated_paths
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


# Minted by redeem_enrollment_code() (utils.sh) and read back by api.lua: once this file exists,
# the local instance refuses the global API_TOKEN and answers only to this credential. bwcli has
# to agree, or every command against an enrolled bare-container instance 401s.
INSTANCE_CREDENTIAL_FILE = Path(sep, "var", "lib", "bunkerweb", "instance-credential.json")


def is_mounted(path, mountinfo=Path("/proc/self/mountinfo")) -> bool:
    """Detect ordinary and bind mounts; pathlib alone misses same-device binds."""
    target = Path(path).resolve()
    with suppress(IndexError, OSError):
        for line in mountinfo.read_text(encoding="utf-8").splitlines():
            mount_point = line.split(" - ", 1)[0].split()[4]
            for escaped, value in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
                mount_point = mount_point.replace(escaped, value)
            if Path(mount_point) == target:
                return True
    return target.is_mount()


def backup_preflight(backup_directory=None) -> Tuple[bool, str]:
    """Require an explicit writable backup mount in the dedicated image."""
    if getenv("BWCLI_REQUIRE_BACKUP_MOUNT", "no").lower() != "yes":
        return True, ""

    backup_path = Path(backup_directory or getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
    if not backup_path.is_dir():
        return False, f"Backup directory {backup_path} does not exist"
    if not is_mounted(backup_path):
        return False, f"Backup directory {backup_path} is not mounted"
    if not access(backup_path, W_OK):
        return False, f"Backup directory {backup_path} is not writable"
    return True, ""


def detect_capabilities() -> dict:
    """Return the non-secret runtime capabilities needed by bwcli commands."""
    api_url = getenv("BWCLI_API_URL", "").strip()
    api_reachable = False
    if api_url:
        with suppress(OSError, TypeError, ValueError):
            _, api_host, api_port = parse_host(API.build_endpoint(api_url))
            timeout = max(0.1, float(getenv("BWCLI_TIMEOUT", "2")))
            with create_connection((api_host, api_port), timeout=timeout):
                api_reachable = True

    has_pymysql = find_spec("pymysql") is not None
    mysql_dump = which("mariadb-dump") or which("mysqldump")
    mysql_restore = which("mariadb") or which("mysql")
    backup_path = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
    return {
        "api": {"configured": bool(api_url), "reachable": api_reachable},
        "database": {
            "sqlite": {"driver": find_spec("sqlite3") is not None, "dump": bool(which("sqlite3")), "restore": bool(which("sqlite3"))},
            "mysql": {"driver": has_pymysql, "dump": bool(mysql_dump), "restore": bool(mysql_restore)},
            "mariadb": {"driver": has_pymysql, "dump": bool(mysql_dump), "restore": bool(mysql_restore)},
            "postgresql": {"driver": find_spec("psycopg") is not None, "dump": bool(which("pg_dump")), "restore": bool(which("psql"))},
        },
        "backup": {"path": str(backup_path), "mounted": is_mounted(backup_path), "writable": backup_path.is_dir() and access(backup_path, W_OK)},
    }


def render_capabilities(capabilities: Optional[dict] = None) -> str:
    capabilities = capabilities or detect_capabilities()
    if getenv("BWCLI_OUTPUT", "table").lower() == "json":
        return dumps(capabilities, sort_keys=True)

    lines = [
        f"API configured: {'yes' if capabilities['api']['configured'] else 'no'}",
        f"API reachable: {'yes' if capabilities['api']['reachable'] else 'no'}",
    ]
    for engine, status in capabilities["database"].items():
        lines.append(
            f"{engine}: driver={'yes' if status['driver'] else 'no'}, dump={'yes' if status['dump'] else 'no'}, restore={'yes' if status['restore'] else 'no'}"
        )
    backup = capabilities["backup"]
    lines.extend(
        (
            f"Backup path: {backup['path']}",
            f"Backup mounted: {'yes' if backup['mounted'] else 'no'}",
            f"Backup writable: {'yes' if backup['writable'] else 'no'}",
        )
    )
    return "\n".join(lines)


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


class CustomConfigsApiClient(BaseApiClient):
    """Client for the control-plane API's `/configs` routes, used by `bwcli custom-configs`.

    Distinct from `ApiCaller`/`self.apis` below, which push bans/reloads straight to each
    BunkerWeb instance's own embedded API: custom configs live in the control-plane API service
    (src/api/), reachable from any host with network access to it -- no shared /etc/bunkerweb
    volume required. The BWCLI_API_URL -> API_URL -> default precedence matches the convention
    src/common/core/backup/downgrade.py:api_url() already established for reaching that service
    from bwcli.
    """

    DEFAULT_URL = "http://127.0.0.1:8888"

    def __init__(self, api_token: str):
        base_url = getenv("BWCLI_API_URL", "").strip() or getenv("API_URL", "").strip() or self.DEFAULT_URL
        super().__init__(base_url, api_token, logger_name="CLI")

    def list_configs(self, *, service: Optional[str] = None, config_type: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {"with_drafts": "true"}
        if service:
            params["service"] = service
        if config_type:
            params["type"] = config_type
        return self._get("/configs", params=params).get("configs", [])

    def list_services(self) -> List[str]:
        return [s["id"] for s in self._get("/services").get("services", []) if s.get("id")]

    def bulk_save(self, custom_configs: List[Dict[str, Any]], method: str) -> str:
        """Full replace of every config tagged `method`. Returns '' on success, or the API's
        advisory message (a write that landed with a caveat, e.g. an unknown service_id)."""
        payload = self._put("/configs/bulk", json={"custom_configs": custom_configs, "method": method, "changed": True})
        return (payload or {}).get("message", "")

    def create_config(self, *, service: Optional[str], config_type: str, name: str, data: str, is_draft: bool) -> None:
        self._post("/configs", json={"service": service, "type": config_type, "name": name, "data": data, "is_draft": is_draft})

    def update_config(self, *, service: Optional[str], config_type: str, name: str, data: str, is_draft: bool) -> None:
        # The API reads the new scope from the BODY, not the URL, and an absent `service` there
        # means "global" (api/app/schemas.py:253-263) -- omitting it would re-scope a per-service
        # config to global on every update. Same fix as src/ui/app/api_client.py:487-493.
        self._patch(f"/configs/{service or 'global'}/{config_type}/{name}", json={"service": service, "data": data, "is_draft": is_draft})


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


def nginx_statements(text: str, included_under: Collection[str] = ()) -> Iterator[Tuple[List[Tuple[int, int]], Tuple[str, ...], bool]]:
    """The statements of the text as (word spans, map outputs, inline).

    The outputs (no `$`) are the output variables of the `map` the statement is an entry of: the block it sits in (inline is True), or, for a statement
    outside any block, the maps that `include` this text (`included_under`, inline False: the statement may still be a plain directive when the include
    could only be a glob over-match). Statements that open a block have no outputs.
    """
    pos = 0
    block = None
    while pos < len(text):
        spans, pos = nginx_statement(text, pos)
        ending = text[pos - 1]
        if ending == "{":
            first = nginx_word(text[spans[0][0] : spans[0][1]]) if spans else ""  # noqa: E203
            block = nginx_word(text[spans[2][0] : spans[2][1]]).removeprefix("$") if first == "map" and len(spans) == 3 else None  # noqa: E203
            yield spans, (), False
            continue
        yield spans, (block,) if block is not None else tuple(sorted(included_under)), block is not None
        if ending == "}":
            block = None


def nginx_include_statements(text: str) -> List[Tuple[str, Tuple[str, ...]]]:
    """The `include` statements of the text as (path pattern, the outputs of the `map` block it sits in, empty outside one)."""
    return [
        (nginx_word(text[spans[1][0] : spans[1][1]]), outputs if inline else ())  # noqa: E203
        for spans, outputs, inline in nginx_statements(text)
        if len(spans) == 2 and nginx_word(text[spans[0][0] : spans[0][1]]) == "include"  # noqa: E203
    ]


def nginx_glob_class(pattern: str, start: int) -> Optional[Tuple[str, int]]:
    """The regex of the `[...]` class opening at `pattern[start]` and the index after it, None when it is not read with certainty as glob(3) reads it.

    `[!x]` negates, a `]` right after the opening is a member. A class opening with `^` (glibc negates it, but not under POSIXLY_CORRECT, and FreeBSD
    reads it as a literal member), a nested `[` (POSIX classes `[:alpha:]`, `[.x.]`, `[=x=]`), a backslash, any range (`[a-z]`, ASCII or not, negated
    or not: in a UTF-8 locale glibc orders it by collation, not by code point, so no translation is provably a superset across locales and libcs) and a
    class that never closes are left to the caller. A `^` that is not first is a literal member everywhere.
    """
    if pattern.startswith("^", start + 1):
        return None
    negate = pattern.startswith("!", start + 1)
    first = start + 1 + negate
    end = pattern.find("]", first + 1)
    if end < 0:
        return None
    members, regex = pattern[first:end], ""
    if "[" in members or "\\" in members:
        return None
    for index, member in enumerate(members):
        if member == "-" and 0 < index < len(members) - 1:
            return None
        regex += re_escape(member)
    return f"[{'^' if negate else ''}{regex}]", end + 1


def nginx_glob_regex(pattern: str):
    """The regex an `include` glob names, read like glob(3) except that `*` and `?` cross `/` (a superset).

    Syntax it does not translate with certainty (see nginx_glob_class(), and backslash escapes) stops the translation there: the rest of the pattern is
    `.*`, so the regex matches every path that could match under the literal prefix, never fewer than glob(3).
    """
    regex, index = "", 0
    while index < len(pattern):
        char = pattern[index]
        if char == "[":
            translated = nginx_glob_class(pattern, index)
            if translated is None:
                return re_compile(regex + ".*", DOTALL)
            piece, index = translated
            regex += piece
            continue
        if char == "\\":
            return re_compile(regex + ".*", DOTALL)
        regex += ".*" if char == "*" else "." if char == "?" else re_escape(char)
        index += 1
    return re_compile(regex, DOTALL)


def nginx_byte_view(text: str) -> str:
    """The UTF-8 bytes of the text, one character per byte (latin-1), so that nginx_glob_regex() reads `?` and classes per byte like glob(3) in the C locale."""
    return text.encode("utf-8", "surrogateescape").decode("latin-1")


def nginx_include_matches(pattern: str, files: Iterable[str], root: str) -> List[str]:
    """The exported files (posix paths) an `include` pattern could name, relative paths being read from the nginx prefix `root` the export mirrors.

    It fails closed: the pattern is also read as the tail of a path, in case the nginx prefix is not `root`, it is read per character (a UTF-8 locale) and
    per byte (nginx runs glob(3) in the C locale, where `é` is two bytes, nginx_byte_view()), `*` crosses directories and glob syntax
    that is not translated with certainty (nginx_glob_regex()) matches every path under its literal prefix, so it may name more files than nginx
    would, never fewer.
    """
    if not pattern:
        return []
    candidates = (normpath(join(root, pattern)), "*/" + normpath(pattern).lstrip("/"))
    matchers = [nginx_glob_regex(candidate).fullmatch for candidate in candidates]
    byte_matchers = [nginx_glob_regex(nginx_byte_view(candidate)).fullmatch for candidate in candidates]
    return [path for path in files if any(matcher(path) for matcher in matchers) or any(matcher(nginx_byte_view(path)) for matcher in byte_matchers)]


def nginx_included_outputs(includes: Dict[str, List[Tuple[str, Tuple[str, ...]]]], root: str) -> Dict[str, Set[str]]:
    """For each exported file (posix path), the output variables of the `map` blocks that include it, directly or through other included files.

    `includes` maps every exported file to the result of nginx_include_statements() over its text.
    """
    included: Dict[str, Set[str]] = {}
    todo = list(includes)
    while todo:
        path = todo.pop()
        for pattern, outputs in includes[path]:
            reached = set(outputs) or included.get(path, set())
            if not reached:
                continue
            for target in nginx_include_matches(pattern, includes, root):
                new = reached - included.setdefault(target, set())
                if new:
                    included[target] |= new
                    todo.append(target)
    return included


def nginx_map_value_spans(text: str, spans: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """The value words of a `map` entry (`key value;`): none for `hostnames;`, `volatile;` and the `include` of another file."""
    return spans[1:] if len(spans) > 1 and nginx_word(text[spans[0][0] : spans[0][1]]) != "include" else []  # noqa: E203


def nginx_variable_links(text: str, included_under: Collection[str] = ()) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """What the text says about credential variables, names without the `$`.

    Returns the variables used inside the value of a credential header (any directive of SUPPORT_NGINX_DIRECTIVES) and, for every variable
    assigned by a `set` or a `map` entry, the variables its value references. `included_under` are the output variables of the `map` blocks
    that include this text: its statements are entries of those maps.
    """
    used = set()
    links: Dict[str, Set[str]] = {}
    for spans, outputs, inline in nginx_statements(text, included_under):
        name = nginx_word(text[spans[0][0] : spans[0][1]]) if spans else ""  # noqa: E203
        assigned = [(output, nginx_map_value_spans(text, spans)) for output in outputs]
        if inline:
            pass
        elif name == "set" and len(spans) > 2:
            assigned.append((nginx_word(text[spans[1][0] : spans[1][1]]).removeprefix("$"), spans[2:]))  # noqa: E203
        elif name in SUPPORT_NGINX_DIRECTIVES and name.startswith("more_set_"):
            for start, end in spans[1:]:
                argument = text[start:end]
                header = SUPPORT_NGINX_MORE_ARGUMENT.match(argument, 1 if argument[0] in "\"'" else 0)
                if header and is_secret_header(header["name"]):
                    used.update(match[1] or match[2] for match in SUPPORT_NGINX_VARIABLE_NAME.finditer(argument[header.end() :]))  # noqa: E203
        elif name in SUPPORT_NGINX_DIRECTIVES and len(spans) > 2 and is_secret_header(nginx_word(text[spans[1][0] : spans[1][1]])):  # noqa: E203
            used.update(match[1] or match[2] for start, end in spans[2:] for match in SUPPORT_NGINX_VARIABLE_NAME.finditer(text[start:end]))
        for target, values in assigned:
            links.setdefault(target, set()).update(
                match[1] or match[2] for start, end in values for match in SUPPORT_NGINX_VARIABLE_NAME.finditer(text[start:end])
            )
    return used, links


def nginx_secret_variables(texts: Iterable[Union[str, Tuple[str, Collection[str]]]], seeds: Collection[str] = ()) -> Set[str]:
    """Names (no `$`) of the variables that carry a credential across all the texts (each a text, or a text and the outputs of the maps that include it): those used as the value of a credential header, those named like
    a secret that are assigned, the `seeds`, and, to a fixpoint, every variable the value of one of them references.
    """
    secret = set(seeds)
    links: Dict[str, Set[str]] = {}
    for item in texts:
        used, found = nginx_variable_links(*((item,) if isinstance(item, str) else item))
        secret |= used
        for variable, references in found.items():
            links.setdefault(variable, set()).update(references)
    secret |= {variable for variable in links if SUPPORT_NGINX_SECRET_VARIABLE.fullmatch(f"${variable}")}
    todo = list(secret)
    while todo:
        for reference in links.get(todo.pop(), ()):
            if reference not in secret:
                secret.add(reference)
                todo.append(reference)
    return secret


def redact_nginx(text: str, secret_variables: Collection[str] = (), included_under: Collection[str] = ()) -> str:
    """Redact the credentials nginx directives carry without a `=` or `:`: variables named like a secret, credential header values, and the values
    of a `map` block whose output variable is a secret.

    The text is walked statement by statement the way nginx reads it, so a directive name inside a comment or a quoted value is never taken for a directive.
    The `set` of a variable used as a credential header value, and what a secret variable references in turn, is redacted wherever it sits: in this text, or
    in another one when the caller passes the names nginx_secret_variables() found over all the texts as `secret_variables`. A text that a `map` block
    includes (`included_under` holds that block's output variable) is read as the entries of that map.
    """
    secret_variables = nginx_secret_variables(((text, included_under),), secret_variables)
    out = []
    done = 0
    for spans, outputs, inline in nginx_statements(text, included_under):
        values = nginx_map_value_spans(text, spans) if any(output in secret_variables for output in outputs) else []
        if values:
            out.append(text[done : values[0][0]] + REDACTED)  # noqa: E203
            done = values[-1][1]
            continue
        if inline:
            continue
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
            variable = nginx_word(text[spans[0][0] : spans[0][1]]) if spans else ""  # noqa: E203
            if len(spans) > 1 and variable.removeprefix("$") in secret_variables:
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

        if Path(sep, "usr", "share", "bunkerweb", "db").exists():
            from Database import Database  # type: ignore

            self.__logger.info("Getting variables from database")

            if tolerant_db:
                from Database import DatabaseInitError, mask_db_uri  # type: ignore

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
            redis_ssl_verify=(self.__get_variable("REDIS_SSL_VERIFY", "yes") or "yes").lower() == "yes",
            redis_ssl_ca=self.__get_variable("REDIS_SSL_CA", None) or None,
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
        # This is a FALLBACK, not an override: API.from_instance prefers the per-instance
        # credential (`instance.get("credential") or token`), so an instance that carries its
        # own keeps using it.
        api_token = self.__get_variable("API_TOKEN") or None
        self.__api_token = api_token
        api_url = (getenv("BWCLI_API_URL") or "").strip() or None

        if api_url:
            self.apis.append(API.from_url_or_parts(api_url, server_name=self.__get_variable("API_SERVER_NAME", "bwapi") or "bwapi", token=api_token))
        elif self.__db:
            for db_instance in self.__db.get_instances(with_credential=True):
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
            # An enrolled bare instance refuses API_TOKEN (see INSTANCE_CREDENTIAL_FILE above), so
            # prefer its own credential here too; a never-enrolled instance has no such file and
            # keeps using the global token.
            self.apis.append(API(endpoint, server_name, token=self.__instance_credential() or api_token))

    def __get_variable(self, variable: str, default: Optional[Any] = None) -> Optional[str]:
        return getenv(variable, self.__variables.get(variable, default))

    def __instance_credential(self) -> Optional[str]:
        """This instance's own credential, minted by redeem_enrollment_code(). Absence is the
        normal, unenrolled case and stays quiet; a present-but-unreadable file is not, hence the
        one warning."""
        if not INSTANCE_CREDENTIAL_FILE.is_file():
            return None
        try:
            credential = loads(INSTANCE_CREDENTIAL_FILE.read_text(encoding="utf-8")).get("credential")
        except (OSError, ValueError, AttributeError) as e:
            self.__logger.warning(f"Instance credential file {INSTANCE_CREDENTIAL_FILE} is unreadable, falling back to the global API token: {e}")
            return None
        return credential or None

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

    @staticmethod
    def __lease_tools():
        """The modules that classify and unban CrowdSec leases, or None where they are not installed.

        The bunkerweb image ships no database package (`db_methods` carries the one definition of a lease), so
        the import is attempted when needed and its absence is not an error.
        """
        try:
            import crowdsec_unban  # type: ignore
            from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore
        except ImportError:
            return None
        return CrowdSecClient, CrowdSecError, crowdsec_unban

    def __find_leases(self, tools, ip: str, ban_scope: str, service: Optional[str]):
        """(client, runtime, leases, failures): the live CrowdSec leases of one identity, found where the router finds them.

        Runtime first (every instance's `GET /bans`, plus the Redis key), never the database alone: `sync-bans` learns once a
        minute. Without a database the instances are asked through bwcli's own connections and there is no client, so a
        lease can be recognised but not removed. `failures` lists what could not be checked.
        """
        client_class, crowdsec_error, module = tools
        client = None
        if self.__db:
            try:
                client = client_class(self.__db)
                runtime = module.collect_runtime(client)
            except crowdsec_error as e:
                return None, None, [], [str(e)]
        elif not self.apis:
            return None, None, [], []
        else:
            ok, responses = self.send_to_apis("GET", "/bans", response=True)
            rows = {host: reply.get("data") for host, reply in (responses or {}).items() if isinstance(reply, dict)}
            runtime = {"rows": {host: data for host, data in rows.items() if isinstance(data, list)}, "failures": [] if ok else ["instances"]}
        leases, failures = module.find_leases(runtime, ip, ban_scope, service, self.__redis)
        return client, runtime, leases, failures

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
            lines.append(f"{self.ICON_WARNING} A decision covers a range: deleting it unblocks every IP of that range")
        if current["management_missing"]:
            lines.append(f"{self.ICON_WARNING} CrowdSec management credentials are missing on: {', '.join(current['management_missing'])}")
        lines.append("Nothing was changed. Run the command again with -confirm to apply.")
        return "\n".join(lines)

    def __unban_lease(self, tools, client, runtime, ip: str, ban_scope: str, service: Optional[str], confirm: bool) -> Tuple[bool, str]:
        """Preview, then with `confirm` apply, through the module the API router uses. Never `revoke_ban`, never the generic `/unban`."""
        _, crowdsec_error, module = tools
        if client is None:
            return False, self.__format_error(
                f"IP {ip} is banned by CrowdSec. Removing a CrowdSec ban needs the database (run bwcli from the scheduler host): use the Web UI or the API instead"
            )
        try:
            current = module.preview(client, ip, ban_scope, service, runtime, self.__redis)
            if not confirm:
                return False, self.__format_lease_preview(ip, current)
            result = module.execute(
                client,
                ip,
                ban_scope,
                service,
                [decision["key"] for decision in current["decisions"]],
                None,
                db=self.__db,
                redis_client=self.__redis,
                actor="bwcli",
            )
        except crowdsec_error as e:
            return False, self.__format_error(f"Failed to unban {ip} from CrowdSec: {e}")
        if result["status"] == "changed":
            return False, self.__format_error(
                f"The CrowdSec ban of {ip} or its decisions changed since the preview, nothing was removed: run the command again"
            )
        if result["status"] != "success":
            lines = [f"Partial CrowdSec result for {ip}: run the command again to finish"]
            lines += [f"failed {failure.get('key') or failure.get('connection_id')}: {failure['error']}" for failure in result["failed"]]
            lines += [f"ban not removed on {failure['instance']}: {failure['error']}" for failure in result["lease_failed"]]
            lines += [f"database not updated: {failure['error']}" for failure in result["db_failed"]]
            lines += [f"instance down, its ban ends on its own: {host}" for host in result["down"]]
            lines += [f"unavailable: {name}" for name in result["unavailable"]]
            return False, self.__format_error("\n".join(lines))
        return True, self.__format_success(
            f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned from CrowdSec\n"
            f"CrowdSec decisions deleted: {len(result['deleted'])}, already absent: {len(result['already_absent'])}"
        )

    def unban(self, ip: str, service: Optional[str] = None, confirm: bool = False) -> Tuple[bool, str]:
        """Unban an IP address globally or from a specific service.

        A CrowdSec ban (a lease) also has CrowdSec decisions behind it: without `confirm` the CLI prints what would be
        deleted and changes nothing; with it, the unban is applied through `crowdsec_unban`, like the API does.
        """
        try:
            ip = normalize_ip(ip)  # one address is one ban, whatever its spelling
        except ValueError:
            return False, self.__format_error(f"Failed to unban {ip}: not a valid IP address")
        ban_scope = "service" if service else "global"
        failures = []
        tools = self.__lease_tools()
        if tools:
            try:
                client, runtime, leases, failures = self.__find_leases(tools, ip, ban_scope, service)
                if leases:
                    return self.__unban_lease(tools, client, runtime, ip, ban_scope, service, confirm)
            except BaseException as e:
                return False, self.__format_error(f"Failed to unban {ip}: {e}")
        ok, text = self.__unban_explicit(ip, ban_scope, service)
        if failures:
            # Same as the router: the unban ran, but a lease on a connection that could not be asked would come back
            note = (
                f"Could not check every BunkerWeb instance for a CrowdSec ban of {ip}: {'; '.join(failures)}. "
                "If one blocks it, the ban comes back: run the command again once they answer."
            )
            if not ok:
                return False, text + self.__format_error(note)
            # The revoke persisted, so the command succeeded: the incomplete check is a warning, not a failure
            return True, f"{text}{self.YELLOW}{self.ICON_WARNING} {note}{self.RESET}\n"
        return ok, text

    def __unban_explicit(self, ip: str, ban_scope: str, service: Optional[str]) -> Tuple[bool, str]:
        """The unban of an explicit ban: revoke in the database, then push to the instances."""
        # Always use API as the source of truth for unban
        try:
            data = {"ip": ip, "ban_scope": ban_scope}
            if service:
                data["service"] = service
            if self.__db:
                # A revoke that is not durable is refused: without the tombstone the convergence
                # job re-learns the ban from an instance that missed this unban and re-pushes it.
                db_error = self.__db.revoke_ban(ip, ban_scope=ban_scope, service_id=service or "", revoked_by="bwcli")
                if db_error:
                    return False, self.__format_error(f"Failed to unban {ip}: {db_error}")
            else:
                # No database here (this is the BunkerWeb container, which also means self.apis
                # only holds the local instance). The unban is local and NOT durable: the next
                # sync-bans pass will re-learn the ban from the stored row and push it back.
                self.__logger.warning(
                    "No database reachable: this unban applies to the local instance only and will be reverted by the next ban sync. "
                    "Run bwcli from the scheduler, or use the web UI/API, to revoke it for good."
                )
            # With no instance to talk to, send_to_apis never enters its loop and returns
            # ret=True: a vacuous success. Ask the question before sending.
            if not self.apis and not self.__db:
                return False, self.__format_error(f"Failed to unban {ip}: no BunkerWeb instance to send the request to")

            # send_to_apis returns (ok, responses); testing the tuple itself is always truthy
            ok = False
            if self.apis:
                ok, _ = self.send_to_apis("POST", "/unban", data=data)

            # The tombstone above is what makes a revoke durable on 1.7, so a failed push is not a
            # failed unban: sync-bans (core/jobs/jobs/sync-bans.py:214) pushes the revoke to every
            # instance on its next pass. Report what is true rather than what the push returned.
            if ok or self.__db:
                if service:
                    success_msg = (
                        f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned from service {self.CYAN}{service}{self.RESET}"
                    )
                else:
                    success_msg = f"{self.ICON_UNLOCK} IP {self.BOLD}{self.WHITE}{ip}{self.RESET} has been unbanned {self.GREEN}globally{self.RESET}"
                if not ok:
                    success_msg += f"\n{self.ICON_INFO} Revoked in the database; no instance applied it yet, the ban sync will push it."
                return True, self.__format_success(success_msg)
        except BaseException as e:
            return False, self.__format_error(f"Failed to unban {ip}: {e}")
        return False, self.__format_error(f"Failed to unban {ip}")

    def ban(self, ip: str, exp: float, reason: str, service: str = "bwcli") -> Tuple[bool, str]:
        """Ban an IP address globally or from a specific service"""
        try:
            ip = normalize_ip(ip)  # one address is one ban, whatever its spelling
        except ValueError:
            return False, self.__format_error(f"Failed to ban {ip}: not a valid IP address")
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

        persisted = False
        try:
            data = {"ip": ip, "exp": exp, "reason": reason, "service": service or "bwcli", "ban_scope": ban_scope}
            if self.__db:
                # Persist first; a failed write is logged, never a reason to leave the IP unblocked.
                db_error = self.__db.upsert_ban(
                    ip,
                    ban_scope=ban_scope,
                    service_id=service if ban_scope == "service" else "",
                    reason=reason,
                    expires_at=None if not exp else datetime.now(timezone.utc) + timedelta(seconds=exp),
                    origin="bwcli",
                )
                if db_error:
                    self.__logger.error(f"Couldn't persist the ban for {ip}: {db_error}")
                else:
                    persisted = True

            # With no instance to talk to, send_to_apis never enters its loop and returns
            # ret=True: a vacuous success. Ask the question before sending.
            if not self.apis and not persisted:
                return False, self.__format_error(f"Failed to ban {ip}: no BunkerWeb instance to send the request to")

            # send_to_apis returns (ok, responses); testing the tuple itself is always truthy
            ok = False
            if self.apis:
                ok, _ = self.send_to_apis("POST", "/ban", data=data)

            # A persisted ban is already durable on 1.7, and sync-bans
            # (core/jobs/jobs/sync-bans.py:139) pushes it to every instance on its next pass, so a
            # failed push is not a failed ban. Say which of the two happened.
            if ok or persisted:
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
                if not ok:
                    success_msg += f"\n{self.ICON_INFO} Recorded in the database; no instance applied it yet, the ban sync will push it."
                return True, self.__format_success(success_msg)
        except BaseException as e:
            return False, self.__format_error(f"Failed to ban {ip}: {e}")
        return False, self.__format_error(f"Failed to ban {ip}")

    def __collect_redis_bans(self, pattern: str, scope: str) -> list:
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

            if scope == "global":
                ip = key_str.replace("bans_ip_", "")
                service = "unknown"
            else:
                service, ip = key_str.replace("bans_service_", "").rsplit("_ip_", 1)

            if is_cluster(self.__redis):
                service, ip = unescape(service), ban_ip(ip)

            try:
                ban_data = loads(raw_value)
            except (JSONDecodeError, ValueError) as e:
                self.__logger.warning(f"Failed to decode ban data for {ip}, using raw value as reason: {e}")
                ban_data = {"reason": raw_value, "service": service, "date": 0, "country": "unknown", "ban_scope": scope, "permanent": False}

            ban_data["ip"] = ip
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

    def __kind_line(self, ban: dict) -> str:
        """The `Kind:` line of a listed ban, or nothing where the kind cannot be told.

        Database rows carry `kind`; instance and Redis rows do not and are classified with the helper the API uses. An
        install without the database package (the bunkerweb image) has no such helper and shows no kind rather than a guess.
        """
        kind = ban.get("kind")
        if kind is None:
            try:
                from db_methods.bans import ban_kind  # type: ignore
            except ImportError:
                return ""
            kind = ban_kind(ban)
        return f"     {self.ICON_INFO} Kind: {'CrowdSec lease' if kind == 'crowdsec_lease' else 'ban'}\n"

    def bans(self) -> Tuple[bool, str]:
        """Get all bans from the system"""
        servers = {}

        # The database first: it is the source of truth, and it is the only source that still
        # answers when an instance has just restarted (empty shared dict) or is unreachable.
        if self.__db:
            try:
                servers["database"] = self.__db.get_bans()
            except BaseException as e:
                self.__logger.error(f"Failed to get bans from the database: {e}")

        try:
            ret, resp = self.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            return False, self.__format_error(f"Failed to get bans: {e}")
        if not ret:
            if servers.get("database"):
                resp = {}
            else:
                return False, self.__format_error("Failed to retrieve ban information")

        for k, v in resp.items():
            servers[k] = v.get("data", [])

        if self.__redis:
            try:
                servers["redis"] = self.__collect_redis_bans("bans_ip_*", "global") + self.__collect_redis_bans("bans_service_*_ip_*", "service")
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
                    cli_str += self.__kind_line(ban)

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
                    cli_str += self.__kind_line(ban)

                    if ban != service_bans[-1]:
                        cli_str += f"  {self.BLUE}· · · · · · · · · · · · · · · · · · · · · · ·{self.RESET}\n"

            cli_str += f"{self.BLUE}{'─' * width}{self.RESET}\n"

        return True, cli_str

    @staticmethod
    def __summarize_import(lines: List[str]) -> str:
        counts = {"created": 0, "updated": 0, "unchanged": 0, "refused": 0, "deleted": 0}
        for line in lines:
            verdict = line.split(" ", 1)[0]
            if verdict in counts:
                counts[verdict] += 1
        return "Summary: " + ", ".join(f"{count} {label}" for label, count in counts.items())

    def custom_configs_list(self, *, service: Optional[str] = None, config_type: Optional[str] = None) -> Tuple[bool, str]:
        """Table of the control-plane API's current custom configs (GET /configs)."""
        client = CustomConfigsApiClient(self.__get_variable("API_TOKEN") or "")
        try:
            configs = client.list_configs(service=service, config_type=config_type)
        except (ApiClientError, ApiUnavailableError) as e:
            return False, self.__format_error(f"Failed to list custom configs: {e}")

        if not configs:
            return True, f"{self.YELLOW}{self.ICON_INFO} No custom configs found{self.RESET}"

        configs.sort(key=lambda c: (c.get("service") or "global", c.get("type", ""), c.get("name", "")))
        headers = ("SERVICE", "TYPE", "NAME", "METHOD", "DRAFT", "CHECKSUM")
        rows = [
            (
                c.get("service") or "global",
                c.get("type", ""),
                c.get("name", ""),
                c.get("method", ""),
                "yes" if c.get("is_draft") else "no",
                (c.get("checksum") or "")[:12],
            )
            for c in configs
        ]
        widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
        table = ["  ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))]
        table.append("  ".join("-" * w for w in widths))
        table.extend("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))) for row in rows)
        return True, "\n".join(table)

    def custom_configs_import(self, directory: str, *, draft: bool = False, method: str = "api", dry_run: bool = False) -> Tuple[bool, str]:
        """Explicit, portable version of the scheduler's own adoption of manually-placed configs
        (`check_configs_changes` in src/scheduler/main.py): walk `directory` with the same
        canonical layout (`<type>/[<service>/]<name>.conf`) and push it through the control-plane
        API instead of relying on a shared /etc/bunkerweb/configs volume.
        """
        if method not in ("manual", "api"):
            return False, self.__format_error(f"Unknown --method {method!r}: must be 'manual' or 'api'")

        root = Path(directory)
        if not root.is_dir():
            return False, self.__format_error(f"{directory} is not a directory")

        entries: List[Dict[str, Any]] = []
        for file in sorted(root.rglob("*.conf")):
            parts = file.relative_to(root).parts
            rel = "/".join(parts)

            if len(parts) not in (2, 3):
                entries.append({"path": rel, "refusal": f"{rel} is not in the correct path"})
                continue

            ctype = normalize_custom_config_type(parts[0])
            if ctype is None:
                entries.append({"path": rel, "refusal": TYPE_ERROR_MESSAGE})
                continue

            name = Path(parts[-1]).stem
            name_error = validate_custom_config_name(name)
            if name_error:
                entries.append({"path": rel, "refusal": name_error})
                continue

            try:
                content = file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                entries.append({"path": rel, "refusal": f"could not read file: {e}"})
                continue

            entries.append(
                {
                    "path": rel,
                    "service_id": parts[1] if len(parts) == 3 else None,
                    "type": ctype,
                    "name": name,
                    "content": content,
                }
            )

        if not entries:
            return True, f"{self.YELLOW}{self.ICON_INFO} No .conf files found under {directory}{self.RESET}"

        client = CustomConfigsApiClient(self.__get_variable("API_TOKEN") or "")
        try:
            current = client.list_configs()
            known_services = set(client.list_services())
        except (ApiClientError, ApiUnavailableError) as e:
            return False, self.__format_error(f"Failed to reach the API: {e}")

        current_index = {(None if c.get("service") in (None, "", "global") else c.get("service"), c.get("type"), c.get("name")): c for c in current}

        lines: List[str] = []
        had_refusal = False
        valid: List[Dict[str, Any]] = []

        for entry in entries:
            if "refusal" in entry:
                lines.append(f"refused {entry['path']}: {entry['refusal']}")
                had_refusal = True
                continue
            # Pre-checked so one bad reference cannot abort the whole batch: `/configs/bulk`
            # commits `custom_configs` in a single transaction (src/common/db/db_methods/
            # custom_configs.py), and service_id is a FOREIGN KEY -- a dangling one would fail
            # the commit and roll back every other config in this run, not just this one.
            if entry["service_id"] and entry["service_id"] not in known_services:
                lines.append(f"refused {entry['path']}: Service {entry['service_id']} not found, please check your config")
                had_refusal = True
                continue
            existing = current_index.get((entry["service_id"], entry["type"], entry["name"]))
            if method == "manual" and existing and existing.get("method") not in {"manual", "ui", "api"}:
                lines.append(
                    f"refused {entry['path']}: existing config is owned by {existing.get('method')}; import it through the API or change it at its source"
                )
                had_refusal = True
                continue
            valid.append(entry)

        for entry in valid:
            key = (entry["service_id"], entry["type"], entry["name"])
            checksum = bytes_hash(entry["content"], algorithm="sha256")
            existing = current_index.get(key)
            if existing and existing.get("checksum") == checksum and bool(existing.get("is_draft", False)) == draft:
                entry["verdict"] = "unchanged"
            else:
                entry["verdict"] = "updated" if existing else "created"

        # `method == "manual"` is a full replace of every existing method="manual" row: any such
        # row whose key is not in `valid` is about to be deleted (and, downstream, unlinked from
        # disk by the scheduler's regeneration) -- surface that explicitly rather than silently,
        # in both dry-run and the real write.
        deleted_keys = []
        if method == "manual":
            valid_keys = {(entry["service_id"], entry["type"], entry["name"]) for entry in valid}
            deleted_keys = [key for key, c in current_index.items() if c.get("method") == "manual" and key not in valid_keys]

        # A refusal under `--method manual` means `valid` does not carry every config that should
        # survive this import: a full replace with an incomplete set would delete the refused
        # files' existing rows, not just skip them. Checked BEFORE dry-run too, so the preview
        # never promises a deletion that a real run would then refuse to perform.
        if method == "manual" and had_refusal:
            abort_note = "import aborted: refusals present, no changes were written (a full replace with an incomplete set would delete the refused configs' existing rows)"
            lines.extend((abort_note, self.__summarize_import(lines)))
            return False, "\n".join(lines)

        if dry_run:
            lines.extend(f"{entry['verdict']} {entry['path']} (dry-run)" for entry in valid)
            lines.extend(f"deleted {key[0] or 'global'}/{key[1]}/{key[2]} (dry-run)" for key in deleted_keys)
            lines.append(self.__summarize_import(lines))
            return not had_refusal, "\n".join(lines)

        if method == "manual":
            # Full replace of every method="manual" row (matches the scheduler's own adoption of
            # /etc/bunkerweb/configs): `valid` must carry every config that should survive this
            # import, unchanged ones included, or they would be deleted as no longer present.
            if valid:
                payload = [{"value": entry["content"], "exploded": (entry["service_id"], entry["type"], entry["name"]), "is_draft": draft} for entry in valid]
                try:
                    message = client.bulk_save(payload, "manual")
                except (ApiClientError, ApiUnavailableError) as e:
                    return False, self.__format_error(f"Import failed: {e}")
                if message:
                    had_refusal = True
                    lines.append(f"note: {message}")
            lines.extend(f"{entry['verdict']} {entry['path']}" for entry in valid)
            lines.extend(f"deleted {key[0] or 'global'}/{key[1]}/{key[2]}" for key in deleted_keys)
        else:  # api
            for entry in valid:
                if entry["verdict"] == "unchanged":
                    lines.append(f"unchanged {entry['path']}")
                    continue
                try:
                    if entry["verdict"] == "updated":
                        client.update_config(service=entry["service_id"], config_type=entry["type"], name=entry["name"], data=entry["content"], is_draft=draft)
                    else:
                        client.create_config(service=entry["service_id"], config_type=entry["type"], name=entry["name"], data=entry["content"], is_draft=draft)
                    lines.append(f"{entry['verdict']} {entry['path']}")
                except (ApiClientError, ApiUnavailableError) as e:
                    lines.append(f"refused {entry['path']}: {e}")
                    had_refusal = True

        lines.append(self.__summarize_import(lines))
        return not had_refusal, "\n".join(lines)

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
                for row in db.get_instances(with_credential=True):
                    try:
                        api = API.from_instance(row, token=self.__api_token)
                    except ValueError as e:
                        api = e
                    # The decrypted per-instance credential dials the instance and goes no further
                    targets.append(({key: value for key, value in row.items() if key != "credential"}, api))
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

        nginx_path = NGINX_PATH
        if nginx_path.is_dir():
            try:
                parts, size = [], 0
                conf_files = [path for path in sorted(nginx_path.rglob("*.conf")) if not path.is_symlink() and path.is_file()]
                # A `set` or a `map` can sit in another file than the credential header that uses its variable, so the variables are collected over every file first
                # and a file that a `map` block includes holds the entries of that map, so which maps include each file is resolved first, the way nginx does
                includes = {path.as_posix(): nginx_include_statements(path.read_text(encoding="utf-8", errors="replace")) for path in conf_files}
                included = nginx_included_outputs(includes, nginx_path.as_posix())
                secret_variables = nginx_secret_variables(
                    (path.read_text(encoding="utf-8", errors="replace"), included.get(path.as_posix(), ())) for path in conf_files
                )
                for path in conf_files:
                    if size >= SUPPORT_NGINX_CAP:
                        break
                    content = anonymizer.redact(
                        redact_nginx(path.read_text(encoding="utf-8", errors="replace"), secret_variables, included.get(path.as_posix(), ()))
                    )
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
