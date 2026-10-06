from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version as package_version
from io import BytesIO
from ipaddress import ip_address
from json import dumps, loads
from logging import Handler
from operator import itemgetter
from os import getpid, stat
from os.path import basename, join, sep
from pathlib import Path
from platform import platform, python_implementation
from re import IGNORECASE, compile as re_compile, escape, match, search
from stat import S_ISREG
from sys import version as python_version
from typing import Any, Dict, Iterable, List, Mapping, Optional, Pattern, Tuple
from urllib.parse import unquote_plus
from zipfile import ZIP_DEFLATED, ZipFile

from logger import FILE_PATH_PATTERN  # type: ignore

RECORD_CAP = 4096
RING_CAP = 1024 * 1024
FILE_TAIL_CAP = 5 * 1024 * 1024
ERROR_BLOCKS = 20
ERROR_BLOCK_LINES = 200
TOTAL_CAP = 25 * 1024 * 1024
TRUNCATED_MARK = " [truncated]"
LOG_DIR = join(sep, "var", "log", "bunkerweb")
LOG_CONDITIONS = {
    "error log": "CAPTURE_OUTPUT=yes or LOG_TYPES contains file with a valid LOG_FILE_PATH",
    "access log": "CAPTURE_OUTPUT=yes or LOG_TYPES contains file with a valid LOG_FILE_PATH",
    "app logger": "LOG_TYPES contains file with a valid LOG_FILE_PATH",
}
STDERR_COMMANDS = ("docker logs <ui container>", "kubectl logs <ui pod>", "journalctl -u bunkerweb-ui")
LIBRARIES = ("flask", "werkzeug", "flask-login", "flask-session", "flask-wtf", "jinja2", "gunicorn", "sqlalchemy", "requests", "biscuit-python")

REDACTED = "[REDACTED]"
_KEYWORDS = r"(?:token|key|secret|password|passwd|session|csrf|cookie|authorization)"
_KEY = rf"[\w.\-]*{_KEYWORDS}[\w.\-]*"
_URI_USERINFO = re_compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)[^\s/@]+@")
_AUTH_QUOTED = r"\"(?:\\.|[^\"\\\r\n])*\"|'[^'\r\n]*'"
_AUTH_ITEM = rf"(?:{_AUTH_QUOTED}|[^\s&,\"'])+"
_AUTH_NAME = rf"(?:{_AUTH_QUOTED}|[^\s&,\"'=])+"
# The name stops at the first `=` so whitespace on either side of it is matched apart from the value
_AUTH_PARAM = rf"(?:{_AUTH_NAME}(?:[ \t]*=[ \t]*{_AUTH_ITEM})?|{_AUTH_ITEM})"
# The whole value after the header name: an optional scheme word, then the credentials and comma separated parameters (Digest, AWS4, ...)
_AUTH_HEADER = re_compile(
    rf"(?P<head>\b(?:proxy-)?authorization\b[ \t]*[:=][ \t]*(?P<known>(?:bearer|basic|digest|negotiate|token)[ \t]+)?)"
    rf"(?(known)|(?:[A-Za-z][\w\-]*[ \t]+(?={_AUTH_ITEM}))?){_AUTH_PARAM}(?:[ \t]*,[ \t]*{_AUTH_PARAM})*",
    IGNORECASE,
)
_BEARER = re_compile(r"\b(?P<scheme>bearer)[ \t]+[A-Za-z0-9._~+/=\-]{4,}", IGNORECASE)
_BASIC = re_compile(r"\b(?P<scheme>basic)[ \t]+(?=[A-Za-z0-9+/]*[0-9+/=])[A-Za-z0-9+/]{8,}={0,2}", IGNORECASE)
_COOKIE = re_compile(r"(?P<head>\b(?:set-)?cookie\b[ \t]*[:=][ \t]*)[^\r\n]+", IGNORECASE)
_JSON_PAIR = re_compile(rf"(?P<head>[\"'](?:{_KEY})[\"'][ \t]*:\s*)(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,}}\]]+)", IGNORECASE)
_KEY_VALUE = re_compile(
    rf"(?<![\w.\-])(?P<head>{_KEY}[ \t]*[=:][ \t]*)(?!\[REDACTED)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s&;,\"')\]}}]+)",
    IGNORECASE,
)
_ENCODED_KEY_VALUE = re_compile(
    r"(?<![\w.\-])(?P<key>[\w.\-+]*%[0-9A-Fa-f]{2}[\w.\-+%]*)(?P<head>[ \t]*[=:][ \t]*)(?!\[REDACTED)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s&;,\"')\]}]+)"
)
_STRUCTURED_HEAD = re_compile(
    rf"(?<![\w.\-])(?P<head>(?:[\"']?{_KEY}[\"']?|(?P<encoded>[\w.\-+]*%[0-9A-Fa-f]{{2}}[\w.\-+%]*))[ \t]*[:=]\s*)(?=[\[{{(])", IGNORECASE
)
# A secret key that ends its line: the value is every following more indented line, or a list at the key's own indent
_BLOCK_HEAD = re_compile(rf"(?<![\w.\-])[\"']?{_KEY}[\"']?[ \t]*[:=][ \t\r]*$", IGNORECASE)
# A secret key whose value is a YAML block scalar (`|`, `>-`, `|2+`, optional comment): the value is the indented lines below the marker
_BLOCK_SCALAR_HEAD = re_compile(rf"(?<![\w.\-])[\"']?{_KEY}[\"']?[ \t]*[:=][ \t]*[|>][+\-]?[0-9]?[+\-]?[ \t]*(?:#.*)?[ \t\r]*$", IGNORECASE)
_CLOSERS = {"[": "]", "{": "}", "(": ")"}
_IPV6_CANDIDATE = re_compile(r"(?<![\w:.])[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?:%[\w.\-]+)?")
_IPV4 = re_compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\.?\d)")


def _is_secret_key(key: str) -> bool:
    """Whether the key names a secret once percent-decoded (nested encodings included)."""
    for _ in range(4):
        decoded = unquote_plus(key)
        if decoded == key:
            break
        key = decoded
    return search(_KEYWORDS, key, IGNORECASE) is not None


def _one_line(head: str) -> str:
    """The key and separator on one line, so a value that began on the next line no longer leaves the key ending its line."""
    return head.rstrip() + " " if "\n" in head else head


def _json_pair_sub(m) -> str:
    return f'{_one_line(m.group("head"))}"{REDACTED}"'


def _decoded_key_sub(m) -> str:
    return f"{m.group('key')}{m.group('head')}{REDACTED}" if _is_secret_key(m.group("key")) else m.group(0)


def _structure_end(text: str, start: int) -> int:
    """Index after the bracketed value opening at start (quotes respected), or the end of the text when it never closes."""
    stack = []
    quote = ""
    i = start
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\":
                i += 1
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char in _CLOSERS:
            stack.append(_CLOSERS[char])
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                return i + 1
        i += 1
    return len(text)


def _redact_structured(text: str) -> str:
    """Replace a list, mapping or tuple that follows a secret key by one redacted value."""
    out = []
    pos = 0
    search_from = 0
    while (m := _STRUCTURED_HEAD.search(text, search_from)) is not None:
        if m.group("encoded") and not _is_secret_key(m.group("encoded")):
            search_from = m.end("head")
            continue
        head = m.group("head")
        before = text[pos : m.start("head")]  # noqa: E203
        out.append(before + _one_line(head) + (f'"{REDACTED}"' if '"' in head or "'" in head else REDACTED))
        pos = search_from = _structure_end(text, m.end())
    out.append(text[pos:])
    return "".join(out)


def _redact_blocks(text: str, head: Pattern = _BLOCK_HEAD) -> str:
    """Replace the indented lines under a secret key that ends its line (YAML lists, nested mappings, block scalars) by one redacted line."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        if head.search(line) is None:
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        redacted = ""
        while i < len(lines):
            stripped = lines[i].strip()
            depth = len(lines[i]) - len(lines[i].lstrip(" \t"))
            if stripped and depth <= indent and not (depth == indent and stripped[0] == "-"):
                break
            if stripped and not redacted:
                redacted = f"{lines[i][:depth]}{REDACTED}"
                out.append(redacted)
            elif not stripped:
                out.append(lines[i])
            i += 1
    return "\n".join(out)


def _is_ip(text: str, version_: int) -> bool:
    try:
        return ip_address(text).version == version_
    except ValueError:
        return False


def _ipv6_sub(m) -> str:
    candidate = m.group(0)
    base = candidate.partition("%")[0]
    for stop in (len(base), len(base.rstrip(".:"))):
        if stop and _is_ip(base[:stop], 6):
            return "[ANONYMIZED_IPv6]" + ("" if stop == len(base) else candidate[stop:])
    return candidate


def _ipv4_sub(m) -> str:
    return "[ANONYMIZED_IPv4]" if _is_ip(m.group(0), 4) else m.group(0)


class Anonymizer:
    """Redacts credentials, IP addresses and the configured service domains from log text.

    Credentials and IPs are redacted even without domains, so a cut that happens before the domains are known (ring buffer) can never leak.
    """

    def __init__(self, domains: Iterable[str] = ()):
        names = sorted({domain for domain in domains if domain}, key=len, reverse=True)
        self._domains = re_compile(rf"(?<![\w-])(?:{'|'.join(map(escape, names))})(?![\w-])", IGNORECASE) if names else None

    def redact(self, text: str) -> str:
        text = _URI_USERINFO.sub(rf"\g<scheme>{REDACTED}@", text)
        # Before the header and cookie passes, which would turn the block scalar marker into the whole value
        text = _redact_blocks(text, _BLOCK_SCALAR_HEAD)
        text = _redact_structured(text)
        text = _AUTH_HEADER.sub(rf"\g<head>{REDACTED}", text)
        text = _COOKIE.sub(rf"\g<head>{REDACTED}", text)
        text = _BEARER.sub(rf"\g<scheme> {REDACTED}", text)
        text = _BASIC.sub(rf"\g<scheme> {REDACTED}", text)
        text = _JSON_PAIR.sub(_json_pair_sub, text)
        text = _redact_blocks(text)
        text = _ENCODED_KEY_VALUE.sub(_decoded_key_sub, text)
        text = _KEY_VALUE.sub(rf"\g<head>{REDACTED}", text)
        text = _IPV6_CANDIDATE.sub(_ipv6_sub, text)
        text = _IPV4.sub(_ipv4_sub, text)
        if self._domains:
            text = self._domains.sub("[ANONYMIZED_DOMAIN]", text)
        return text


def cut_text(text: str, limit: int) -> Tuple[str, bool]:
    """Cut text to limit UTF-8 bytes. Callers redact first, so the cut can never split a credential."""
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text, False
    return raw[:limit].decode("utf-8", errors="ignore") + TRUNCATED_MARK, True


class RingBufferHandler(Handler):
    """Keeps the most recent formatted log records of this worker, bounded in bytes at ingestion."""

    def __init__(self, record_cap: int = RECORD_CAP, total_cap: int = RING_CAP):
        super().__init__()
        self.record_cap = record_cap
        self.total_cap = total_cap
        self.started = datetime.now(timezone.utc)
        self._records: deque = deque()
        self._size = 0
        self._cut = 0
        self._evicted = 0
        self._guard = Anonymizer()

    def emit(self, record) -> None:
        try:
            text = self.format(record)
            if len(text) * 4 > self.record_cap and len(text.encode("utf-8")) > self.record_cap:
                # Redact before cutting: the domain-less anonymizer still removes every credential form
                text, _ = cut_text(self._guard.redact(text), self.record_cap)
                self._cut += 1
            size = len(text.encode("utf-8"))
            self._records.append((text, size))
            self._size += size
            while self._size > self.total_cap and self._records:
                self._size -= self._records.popleft()[1]
                self._evicted += 1
        except Exception:
            self.handleError(record)

    def snapshot(self) -> Dict[str, Any]:
        self.acquire()
        try:
            return {
                "pid": getpid(),
                "started": self.started.isoformat(),
                "records": [text for text, _ in self._records],
                "bytes": self._size,
                "records_cut": self._cut,
                "records_evicted": self._evicted,
            }
        finally:
            self.release()


RING_HANDLER = RingBufferHandler()


def valid_log_path(path: str) -> bool:
    """Same guard as logger.py: no traversal segment and the log file pattern."""
    return bool(path) and ".." not in path.split("/") and bool(match(FILE_PATH_PATTERN, path))


def _file_outputs(environ: Mapping[str, str], default_name: str) -> List[Tuple[str, str]]:
    """The files one UI process writes, mirroring logger.py and the gunicorn config (gunicorn.conf.py, tmp-gunicorn.conf.py)."""
    log_types = environ.get("LOG_TYPES", "stderr").split()
    capture = environ.get("CAPTURE_OUTPUT", "no").lower() == "yes"
    scheduler_default = join(LOG_DIR, "scheduler.log") if environ.get("SCHEDULER_LOG_TO_FILE", "no") == "yes" else ""
    app_path = environ.get("LOG_FILE_PATH", scheduler_default).strip()
    app_file = "file" in log_types and valid_log_path(app_path)

    outputs = []
    if capture or app_file:
        errorlog = environ.get("LOG_FILE_PATH", join(LOG_DIR, default_name))
        outputs.extend(((errorlog, "error log"), (f"{errorlog.rsplit('.', 1)[0]}-access.log", "access log")))
    if app_file:
        outputs.append((app_path, "app logger"))
    return outputs


def log_sources(environ: Mapping[str, str], integration: str) -> List[Dict[str, Any]]:
    """Log files the main and temporary UI write, deduplicated by path.

    Containers unset LOG_FILE_PATH for the temporary UI (entrypoint.sh), Linux keeps it (bunkerweb-ui.sh), so there both share the main UI's files.
    """
    tmp_environ = {key: value for key, value in environ.items() if not (integration != "Linux" and key == "LOG_FILE_PATH")}
    sources: Dict[str, Dict[str, Any]] = {}
    for process, process_environ, default_name in (("main UI", environ, "ui.log"), ("temporary UI", tmp_environ, "tmp-ui.log")):
        for path, role in _file_outputs(process_environ, default_name):
            sources.setdefault(path, {"path": path, "writers": []})["writers"].append(f"{process} {role}")
    return list(sources.values())


def _drop_first_line(data: bytes) -> bytes:
    _, newline, rest = data.partition(b"\n")
    return rest if newline else b""


def read_log_tail(path: str, cap: int = FILE_TAIL_CAP) -> Tuple[str, int]:
    """Whole lines of the last cap bytes of a regular file, and the file size. A partial first line is dropped."""
    with open(path, "rb") as file:
        size = file.seek(0, 2)
        start = max(size - cap, 0)
        file.seek(max(start - 1, 0))
        before = file.read(1) if start else b"\n"
        data = file.read(cap)
    if before != b"\n":
        data = _drop_first_line(data)
    return data.decode("utf-8", errors="replace"), size


_RECORD_START = re_compile(r"^\[\d{4}-\d{2}-\d{2} ")
_ERROR_MARK = re_compile(r"\[(?:❌|🚨|ERROR|CRITICAL)\]")


def error_blocks(text: str, max_lines: int = ERROR_BLOCK_LINES) -> Tuple[List[List[str]], int]:
    """ERROR or traceback blocks of already redacted text, each cut at max_lines. Returns the blocks and the number of cut blocks."""
    blocks: List[List[str]] = []
    current: Optional[List[str]] = None
    cut = 0
    for line in text.splitlines():
        if _RECORD_START.match(line):
            current = [line] if _ERROR_MARK.search(line) else None
            if current is not None:
                blocks.append(current)
        elif line.startswith("Traceback (most recent call last)") and current is None:
            current = [line]
            blocks.append(current)
        elif current is not None:
            if len(current) < max_lines:
                current.append(line)
            elif len(current) == max_lines:
                current.append(TRUNCATED_MARK.strip())
                cut += 1
    return blocks, cut


def read_plugin_version(plugin_root: Path) -> Optional[str]:
    try:
        version_ = loads(plugin_root.joinpath("plugin.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    return version_ if isinstance(version_, str) else None


def build_plugins_report(
    db_plugins: Iterable[Mapping[str, Any]], plugin_roots: Mapping[str, Path], blueprints: Iterable[Mapping[str, Any]], worker: Mapping[str, Any]
) -> Dict[str, Any]:
    """Plugin inventory as the Web UI sees it.

    `blueprints` are the plugin blueprints registered in the worker serving the request (name, plugin_priority, root_path, import_path,
    plugin_version recorded at registration). Status is `ok`, `mismatch` (pairs listed) or `unknown` (no recorded load version).
    """
    loaded_by_plugin: Dict[str, List[Mapping[str, Any]]] = {}
    for blueprint in blueprints:
        import_path = blueprint.get("import_path")
        if import_path:
            loaded_by_plugin.setdefault(Path(import_path).parents[1].name, []).append(blueprint)

    plugins = []
    for plugin in db_plugins:
        plugin_type = "external" if plugin["type"] == "ui" else plugin["type"]
        root = plugin_roots.get(plugin_type)
        plugin_dir = root.joinpath(plugin["id"]) if root else None
        disk_version = read_plugin_version(plugin_dir) if plugin_dir else None
        has_blueprints = bool(plugin_dir and plugin_dir.joinpath("ui", "blueprints").is_dir())
        loaded = [
            {
                "blueprint": item.get("name"),
                "plugin_priority": item.get("plugin_priority"),
                "root_path": item.get("root_path"),
                "recorded_version": item.get("plugin_version"),
            }
            for item in loaded_by_plugin.get(plugin["id"], [])
        ]
        recorded = {item["recorded_version"] for item in loaded if item["recorded_version"]}

        mismatches = []
        if plugin.get("version") and disk_version and plugin["version"] != disk_version:
            mismatches.append({"pair": "database/disk", "database": plugin["version"], "disk": disk_version})
        for version_ in sorted(recorded):
            if disk_version and version_ != disk_version:
                mismatches.append({"pair": "disk/loaded", "disk": disk_version, "loaded": version_})

        if mismatches:
            status = "mismatch"
        elif (has_blueprints and not recorded) or not disk_version:
            status = "unknown"
        else:
            status = "ok"

        plugins.append(
            {
                "id": plugin["id"],
                "type": plugin_type,
                "database_version": plugin.get("version"),
                "disk_version": disk_version,
                "page": {"database": bool(plugin.get("page")), "filesystem": bool(plugin_dir and plugin_dir.joinpath("ui").is_dir())},
                "loaded": loaded,
                "status": status,
                "mismatches": mismatches,
            }
        )
    return {
        "observed_worker": dict(worker),
        "note": "Load versions are recorded by the worker serving this request only; other workers are not observed.",
        "plugins": plugins,
    }


def pseudonym(value: str) -> str:
    return f"host-{sha256(value.encode('utf-8')).hexdigest()[:8]}"


def build_environment(
    *,
    metadata: Mapping[str, Any],
    integration: str,
    instances: Iterable[Mapping[str, Any]],
    service_count: int,
    db_dialect: str,
    db_revision: Optional[str],
    worker: Mapping[str, Any],
) -> Dict[str, Any]:
    """Allow-listed environment facts: never the license key, the database URI or any environment variable."""
    libraries = {}
    for name in LIBRARIES:
        try:
            libraries[name] = package_version(name)
        except PackageNotFoundError:
            libraries[name] = None
    expire = metadata.get("pro_expire")
    return {
        "bunkerweb_version": metadata.get("version"),
        "integration": integration,
        "pro": {
            "active": bool(metadata.get("is_pro")),
            "status": metadata.get("pro_status"),
            "expire": expire.isoformat() if isinstance(expire, datetime) else None,
            "services_allowed": metadata.get("pro_services"),
            "services_configured": service_count,
        },
        "python": {"version": python_version, "implementation": python_implementation(), "platform": platform()},
        "libraries": libraries,
        "database": {"dialect": db_dialect, "server_version": metadata.get("database_version"), "alembic_revision": db_revision},
        "instances": [
            {
                "name": instance.get("name"),
                "type": instance.get("type"),
                "method": instance.get("method"),
                "status": instance.get("status"),
                "hostname": pseudonym(str(instance.get("hostname", ""))),
            }
            for instance in instances
        ],
        "worker": dict(worker),
    }


class _BundleZip:
    """Zip writer enforcing the total uncompressed cap and listing every file in the manifest."""

    def __init__(self, total_cap: int):
        self.buffer = BytesIO()
        self.zip = ZipFile(self.buffer, "w", ZIP_DEFLATED)
        self.room = total_cap
        self.files: List[Dict[str, Any]] = []
        self.unavailable: List[Dict[str, str]] = []

    def add(self, name: str, text: str, note: str = "", capped: bool = True) -> None:
        data = text.encode("utf-8")
        truncated = capped and len(data) > self.room
        if truncated:
            cut_at = len(data) - max(self.room, 0)
            before_start = max(cut_at - 1, 0)
            before, data = data[before_start:cut_at], data[cut_at:]
            if before != b"\n":
                data = _drop_first_line(data)
        if not data and text:
            self.unavailable.append({"item": name, "reason": "total size cap reached"})
            return
        if capped:
            self.room -= len(data)
        self.zip.writestr(name, data)
        entry: Dict[str, Any] = {"name": name, "bytes": len(data)}
        if truncated:
            entry["truncated"] = "kept the last part, total size cap reached"
        if note:
            entry["note"] = note
        self.files.append(entry)

    def finish(self, manifest: Dict[str, Any]) -> bytes:
        manifest["files"] = self.files
        manifest["unavailable"] = self.unavailable + manifest.get("unavailable", [])
        self.zip.writestr("manifest.json", dumps(manifest, indent=2, default=str))
        self.zip.close()
        return self.buffer.getvalue()


def build_support_bundle(
    *,
    domains: Iterable[str],
    environ: Mapping[str, str],
    integration: str,
    ring: Mapping[str, Any],
    plugins: Mapping[str, Any],
    environment: Mapping[str, Any],
    now: Optional[datetime] = None,
    file_cap: int = FILE_TAIL_CAP,
    total_cap: int = TOTAL_CAP,
) -> bytes:
    """Build the zip of the Web UI support bundle from already collected, allow-listed data."""
    anonymizer = Anonymizer(domains)
    out = _BundleZip(total_cap)
    unavailable: List[Dict[str, str]] = []
    source_report = []
    redacted_texts: List[Tuple[str, str]] = []
    used_names = set()

    for source in log_sources(environ, integration):
        path = source["path"]
        conditions = sorted({LOG_CONDITIONS[writer.split(" UI ", 1)[1]] for writer in source["writers"]})
        report = {"path": path, "writers": source["writers"], "conditions": conditions}
        source_report.append(report)
        if not valid_log_path(path):
            report["status"] = "skipped: path rejected by the log path guard"
            continue
        try:
            if not S_ISREG(stat(path).st_mode):
                report["status"] = "skipped: not a regular file (stream or device)"
                continue
            text, size = read_log_tail(path, file_cap)
        except FileNotFoundError:
            report["status"] = "not found"
            continue
        except OSError as exc:
            report["status"] = f"unreadable: {exc.strerror or type(exc).__name__}"
            continue
        text = anonymizer.redact(text)
        name = f"logs/{basename(path)}"
        if name in used_names:
            name = f"logs/{len(used_names)}-{basename(path)}"
        used_names.add(name)
        report.update(
            {"status": "included", "file_bytes": size, "included_bytes": len(text.encode("utf-8")), "cut_to_last_bytes": file_cap if size > file_cap else None}
        )
        out.add(name, text, note=f"{path} ({', '.join(source['writers'])})")
        redacted_texts.append((name, text))

    ring_records = [anonymizer.redact(record) for record in ring.get("records", [])]
    if ring_records:
        header = f"# worker pid {ring.get('pid')}, ring started {ring.get('started')}, other workers are not included\n"
        ring_text = header + "\n".join(ring_records) + "\n"
        out.add("logs/ui-recent.log", ring_text, note="in-process ring buffer of the worker serving the request")
        redacted_texts.append(("logs/ui-recent.log", ring_text))
    else:
        unavailable.append({"item": "logs/ui-recent.log", "reason": "the ring buffer of this worker is empty"})
    if not any(item.get("status") == "included" for item in source_report):
        unavailable.append({"item": "log files", "reason": "no UI log file found; output goes to stderr, collect it with: " + "; ".join(STDERR_COMMANDS)})

    blocks_seen = set()
    blocks: List[Tuple[str, str, List[str]]] = []
    blocks_cut = 0
    for name, text in redacted_texts:
        found, cut = error_blocks(text)
        blocks_cut += cut
        for block in found:
            key = tuple(block)
            if key not in blocks_seen:
                blocks_seen.add(key)
                blocks.append((block[0][:21] if _RECORD_START.match(block[0]) else "", name, block))
    blocks.sort(key=itemgetter(0))
    kept = blocks[-ERROR_BLOCKS:]
    out.add("errors.txt", "\n\n".join(f"--- {name} ---\n" + "\n".join(block) for _, name, block in kept) + ("\n" if kept else ""))

    out.add("plugins.json", dumps(plugins, indent=2, default=str), capped=False)
    out.add("environment.json", dumps(environment, indent=2, default=str), capped=False)

    return out.finish(
        {
            "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
            "caps": {
                "record_bytes": RECORD_CAP,
                "ring_bytes": RING_CAP,
                "file_tail_bytes": file_cap,
                "error_blocks": ERROR_BLOCKS,
                "error_block_lines": ERROR_BLOCK_LINES,
                "total_bytes": total_cap,
            },
            "log_rules": (
                "File logging is active when CAPTURE_OUTPUT=yes or LOG_TYPES contains file with a valid LOG_FILE_PATH. "
                "Containers give the temporary UI its own tmp-ui.log, Linux shares the main UI files."
            ),
            "log_sources": source_report,
            "ring": {key: ring.get(key) for key in ("pid", "started", "bytes", "records_cut", "records_evicted")},
            "error_blocks": {"found": len(blocks), "kept": len(kept), "cut_at_line_cap": blocks_cut},
            "unavailable": unavailable,
            "anonymization": "Service domains, IP addresses, credentials and instance hostnames are anonymized; the license key and the database URI are never collected.",
        }
    )
