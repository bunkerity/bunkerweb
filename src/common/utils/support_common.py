from datetime import datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version as package_version
from io import BytesIO
from ipaddress import ip_address
from json import dumps, loads
from os.path import join, sep
from pathlib import Path
from platform import platform, python_implementation
from re import DOTALL, IGNORECASE, VERBOSE as re_X, compile as re_compile, escape, match, search
from sys import version as python_version
from typing import Any, Dict, Iterable, List, Mapping, Optional, Pattern, Tuple
from urllib.parse import unquote_plus
from zipfile import ZIP_DEFLATED, ZipFile

from logger import FILE_PATH_PATTERN  # type: ignore

# Redaction, size caps, config masking and the zip writer shared by the Web UI support bundle (src/ui/app/support_bundle.py) and `bwcli support`.

FILE_TAIL_CAP = 5 * 1024 * 1024
TOTAL_CAP = 25 * 1024 * 1024
TRUNCATED_MARK = " [truncated]"
LOG_DIR = join(sep, "var", "log", "bunkerweb")
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

    def __init__(self, domains: Iterable[str] = (), anonymize: bool = True):
        names = sorted({domain for domain in domains if domain}, key=len, reverse=True)
        alternatives = "|".join(map(escape, names))
        self._domains = re_compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", IGNORECASE) if names else None
        # A config key is `<service>_<SETTING>`, so `_` may follow the domain there
        self._key_domains = re_compile(rf"(?<![\w-])(?:{alternatives})(?![A-Za-z0-9-])", IGNORECASE) if names else None
        # False keeps IP addresses and domains and still redacts every credential
        self._anonymize = anonymize

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
        if not self._anonymize:
            return text
        text = _IPV6_CANDIDATE.sub(_ipv6_sub, text)
        text = _IPV4.sub(_ipv4_sub, text)
        if self._domains:
            text = self._domains.sub("[ANONYMIZED_DOMAIN]", text)
        return text

    def pseudonymize(self, text: str) -> str:
        """Replace each configured domain by a stable `domain-<hash>` name, so keys that embed one stay distinct and match across files."""
        if not self._anonymize or not self._key_domains:
            return text
        return self._key_domains.sub(lambda m: f"domain-{sha256(m.group(0).lower().encode('utf-8')).hexdigest()[:8]}", text)

    def scrub(self, data: Any) -> Any:
        """Copy of a JSON-like structure with every string value redacted and every key pseudonymized."""
        if isinstance(data, dict):
            return {self.pseudonymize(key) if isinstance(key, str) else key: self.scrub(value) for key, value in data.items()}
        if isinstance(data, (list, tuple)):
            return [self.scrub(item) for item in data]
        return self.redact(data) if isinstance(data, str) else data


def cut_text(text: str, limit: int) -> Tuple[str, bool]:
    """Cut text to limit UTF-8 bytes. Callers redact first, so the cut can never split a credential."""
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text, False
    return raw[:limit].decode("utf-8", errors="ignore") + TRUNCATED_MARK, True


def valid_log_path(path: str) -> bool:
    """Same guard as logger.py: no traversal segment and the log file pattern."""
    return bool(path) and ".." not in path.split("/") and bool(match(FILE_PATH_PATTERN, path))


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


def read_plugin_version(plugin_root: Path) -> Optional[str]:
    try:
        version_ = loads(plugin_root.joinpath("plugin.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    return version_ if isinstance(version_, str) else None


def build_plugins_report(
    db_plugins: Iterable[Mapping[str, Any]],
    plugin_roots: Mapping[str, Path],
    blueprints: Optional[Iterable[Mapping[str, Any]]] = None,
    worker: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Plugin inventory: database and disk versions, and what the Web UI loaded.

    `blueprints` are the plugin blueprints registered in the worker serving the request (name, plugin_priority, root_path, import_path,
    plugin_version recorded at registration). Status is `ok`, `mismatch` (pairs listed) or `unknown` (no recorded load version).
    Without blueprints (`bwcli support`), the status only compares the database and disk versions.
    """
    loaded_by_plugin: Dict[str, List[Mapping[str, Any]]] = {}
    for blueprint in blueprints or ():
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
        elif (blueprints is not None and has_blueprints and not recorded) or not disk_version:
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
    if worker is None:
        return {"plugins": plugins}
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
    worker: Optional[Mapping[str, Any]] = None,
    library_names: Iterable[str] = LIBRARIES,
    pseudonymize_hosts: bool = True,
) -> Dict[str, Any]:
    """Allow-listed environment facts: never the license key, the database URI or any environment variable."""
    libraries = {}
    for name in library_names:
        try:
            libraries[name] = package_version(name)
        except PackageNotFoundError:
            libraries[name] = None
    expire = metadata.get("pro_expire")
    environment = {
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
                "hostname": pseudonym(str(instance.get("hostname", ""))) if pseudonymize_hosts else instance.get("hostname"),
            }
            for instance in instances
        ],
    }
    if worker is not None:
        environment["worker"] = dict(worker)
    return environment


class BundleZip:
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


MULTIPLE_SUFFIX = re_compile(r"_\d+$")
# Scheme and userinfo part of sqlalchemy.engine.url._parse_url, so the password span is the one SQLAlchemy parses
URL_USERINFO = re_compile(
    r"""
    (?P<name>[\w\+]+)://
    (?:
        (?P<username>[^:/]*)
        (?::(?P<password>[^@]*))?
    @)
    """,
    re_X,
)
URI_SETTINGS = ("DATABASE_URI", "DATABASE_URI_READONLY")
# Free-form settings that hold a credential without being typed `password` (API_TOKEN, private key contents). `*_SSL_KEY` is a file path and
# `*_CACHE_KEY` a cache key template, so they stay readable. Flags, selects and numbers (OPENIDC_ACCESS_TOKEN_EXPIRES_IN, ...) never hold one.
SECRET_SETTING = re_compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL_ITEM$|(?<!CACHE)(?<!_SSL)_KEY$|_KEY_DATA$")
NON_TEXT_TYPES = ("check", "select", "multiselect", "number")
# Settings whose value is `Name Value` header lines separated by `;` (REVERSE_PROXY_HEADERS, GRPC_HEADERS, CUSTOM_HEADER, ...)
HEADER_SETTING = re_compile(r"(?:^|_)HEADERS?(?:_CLIENT)?$")
# A header carries a credential when its name says so: Authorization, Proxy-Authorization, Cookie, X-Api-Key, X-Auth-Token, ...
SECRET_HEADER = re_compile(r"auth|token|secret|key|passw|cookie|session|credential|csrf|jwt|signature", IGNORECASE)
# The settings' own regex allows any whitespace (newlines included) between the name and the value, CUSTOM_HEADER a colon
HEADER_ITEM = re_compile(r"(?P<head>\s*(?P<name>[\w\-]+)(?:\s*:\s*|\s+))(?=\S)", DOTALL)


def setting_names(key: str, names) -> set:
    """Return every known setting name a config key (``[service_]SETTING[_N]``) can stand for.

    A service name can contain ``_``, so every ``_`` boundary is a candidate, on the raw key and on the key without its ``_N`` suffix.
    The caller masks when any candidate is sensitive, so the result never depends on which candidate would be the "right" one.
    """
    found = set()
    for base in {key, MULTIPLE_SUFFIX.sub("", key)}:
        found.update(
            candidate for candidate in (base, *(base[index + 1 :] for index, char in enumerate(base) if char == "_")) if candidate in names  # noqa: E203
        )  # noqa: E203
    return found


def mask_uri(uri: str) -> str:
    """Redact the password of a SQLAlchemy URL, keeping every other character as is."""
    parsed = URL_USERINFO.match(uri)
    if not parsed or not parsed["password"]:
        return uri
    # SQLAlchemy ends the password at the first "@", the host part may still hold some, so redact up to the last one before the path or query
    authority_end = min((i for i in (uri.find("/", parsed.end()), uri.find("?", parsed.end())) if i >= 0), default=len(uri))
    end = max(parsed.end(), uri.rfind("@", parsed.end() - 1, authority_end) + 1)
    prefix, suffix = uri[: parsed.start("password")], uri[end - 1 :]  # noqa: E203
    return f"{prefix}{REDACTED}{suffix}"


def is_secret_header(name: str) -> bool:
    return SECRET_HEADER.search(name) is not None and not name.lower().startswith("access-control-")


def mask_header_values(text: str) -> str:
    """Redact the value of every credential header of a `Name Value;Name: Value` list, other items stay as they are."""
    items = []
    for item in text.split(";"):
        header = HEADER_ITEM.match(item)
        items.append(f"{header['head']}{REDACTED}" if header and is_secret_header(header["name"]) else item)
    return ";".join(items)


def mask_config(config: dict, settings: Mapping[str, Any]) -> dict:
    """Redact the value and the default of every credential setting and the password part of the database URIs.

    Credential settings are the `password` typed ones, the free-form ones named like a secret (SECRET_SETTING), and the credential headers
    inside header list settings (HEADER_SETTING). settings maps every known setting name to its definition (type, context, ...).
    """
    for key, data in config.items():
        if not isinstance(data, dict):
            continue

        names = setting_names(key, settings)
        is_secret = any(
            settings[name].get("type") == "password" or (settings[name].get("type") not in NON_TEXT_TYPES and SECRET_SETTING.search(name)) for name in names
        )
        is_uri = any(name in URI_SETTINGS for name in names)
        is_header = any(HEADER_SETTING.search(name) for name in names)
        for field in ("value", "default"):
            content = data.get(field)
            if not content or not isinstance(content, str):
                continue
            if is_uri and not is_secret:
                data[field] = mask_uri(content)
            elif is_secret:
                data[field] = REDACTED
            elif is_header:
                data[field] = mask_header_values(content)
    return config


def service_domains(config: Mapping[str, str]) -> set:
    """Every domain of the SERVER_NAME settings (global and per service) of a config read with filtered_settings=("SERVER_NAME",)."""
    return {domain for key, value in config.items() if key == "SERVER_NAME" or key.endswith("_SERVER_NAME") for domain in value.split()}


def alembic_revision(db) -> Optional[str]:
    # Imported here: SQLAlchemy is not part of the core image, where bwcli still has to start
    from sqlalchemy import text as sql_text

    try:
        with db._db_session() as session:
            row = session.execute(sql_text("SELECT version_num FROM alembic_version")).first()
        return row[0] if row else None
    except Exception:
        return None
