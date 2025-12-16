from contextlib import suppress
from csv import Sniffer, reader as csv_reader
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from json import dumps, loads
from typing import Iterable, List, Optional, Set, Tuple, Dict, Any, Union
from io import StringIO
from pathlib import Path

from fastapi import Depends, Request
from fastapi.responses import Response

from regex import compile as regex_compile, Pattern, escape, fullmatch, search, split
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from yaml import safe_load

from .config import api_config
from os import getenv
from .utils import LOGGER, get_db

_enabled: bool = False
_limiter: Optional[Limiter] = None
_base_limits: List[str] = []
_auth_limit: Optional[str] = None
_exempt_networks: List[Union[IPv4Network, IPv6Network]] = []

DEFAULT_RATE = (100, 60)  # 100 requests per minute
DEFAULT_AUTH_RATE = (10, 60)


class _Rule:
    __slots__ = ("methods", "pattern", "times", "seconds", "raw")

    def __init__(self, methods: Set[str], pattern: Pattern[str], times: int, seconds: int, raw: str):
        self.methods = methods
        self.pattern = pattern
        self.times = times
        self.seconds = seconds
        self.raw = raw

    @property
    def limit_string(self) -> str:
        return _limit_string(self.times, self.seconds)


_rules: List[_Rule] = []


def _normalize_method(m: str) -> str:
    return m.strip().upper()


def _compile_pattern(path: str) -> Pattern[str]:
    p = path.strip()
    if p.startswith("re:"):
        return regex_compile(p[3:])
    if "*" in p:
        return regex_compile("^" + escape(p).replace("\\*", ".*") + "$")
    return regex_compile("^" + escape(p) + "$")


def _parse_rate(rate: str) -> Tuple[int, int]:
    """Parse a rate limit item from a string.

    Supported forms (mirrors limits' rate string notation):
      [count] [per|/] [n optional] [second|minute|hour|day|month|year]

    Examples:
      10/hour, 10 per hour, 100/day, 500/7days, 200 per 30 minutes, 100/60
      NGINX-style: 3r/s, 40r/m, 200r/h
    """
    compact = "".join(rate.strip().lower().split())
    m_nginx = fullmatch(r"(\d+)r?/([smhd])", compact)
    if m_nginx:
        times = int(m_nginx.group(1))
        unit = m_nginx.group(2)
        unit_seconds_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return times, unit_seconds_map[unit]

    r = rate.strip().lower().replace("per ", "/")
    if "/" not in r:
        raise ValueError("rate must be like '10/hour', '10 per hour', '10/60', '100/day', '500/7days'")
    left, right = r.split("/", 1)
    times = int(left.strip())
    right = right.strip()

    # Fast path: plain integer seconds
    with suppress(Exception):
        seconds = int(right)
        return times, seconds

    # Accept forms like "hour", "1 hour", "7days", "30 minutes", etc.
    m = fullmatch(r"(?:(\d+)\s*)?([a-z]+)", right)
    if not m:
        raise ValueError(f"invalid rate unit '{right}'")
    mult_str, unit = m.groups()
    mult = int(mult_str) if mult_str else 1

    unit_seconds_map = {
        # seconds
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        # minutes
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        # hours
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
        # days
        "d": 86400,
        "day": 86400,
        "days": 86400,
        # months (30 days)
        "mo": 2592000,
        "mon": 2592000,
        "month": 2592000,
        "months": 2592000,
        # years (365 days)
        "y": 31536000,
        "yr": 31536000,
        "yrs": 31536000,
        "year": 31536000,
        "years": 31536000,
    }
    if unit not in unit_seconds_map:
        raise ValueError(f"unknown time unit '{unit}' in rate '{rate}'")
    seconds = mult * unit_seconds_map[unit]
    return times, seconds


def _try_json(s: str):
    try:
        return loads(s)
    except Exception:
        return None


def _parse_methods(value: Any) -> Set[str]:
    if isinstance(value, str):
        return {_normalize_method(x) for x in value.split("|") if x}
    if isinstance(value, Iterable):
        return {_normalize_method(str(x)) for x in value if str(x).strip()}
    return set()


def _resolve_rate(raw: Optional[str], fallback_times: int, fallback_seconds: int, *, label: str, allow_disable: bool = False) -> Optional[Tuple[int, int]]:
    if raw is None:
        return fallback_times, fallback_seconds
    val = str(raw).strip()
    if not val:
        return fallback_times, fallback_seconds
    lowered = val.lower()
    if allow_disable and lowered in ("off", "disabled", "none", "no", "false", "0"):
        return None
    try:
        return _parse_rate(val)
    except Exception as exc:
        LOGGER.warning(f"Invalid {label} '{val}', falling back to {fallback_times}/{fallback_seconds}: {exc}")
        return fallback_times, fallback_seconds


def _rule_from_dict(it: Dict[str, Any]) -> Optional[_Rule]:
    path = str(it.get("path", "/")).strip() or "/"
    methods = _parse_methods(it.get("methods"))
    rate_raw = it.get("rate")
    if rate_raw is not None:
        times, seconds = _parse_rate(str(rate_raw))
    else:
        times = int(it.get("times", DEFAULT_RATE[0]))
        seconds = int(it.get("seconds", DEFAULT_RATE[1]))
    try:
        raw_repr = dumps(it)
    except Exception:
        raw_repr = str(it)
    return _Rule(methods, _compile_pattern(path), times, seconds, raw_repr)


def _rule_from_mapping_key(key: str, value: Any) -> Optional[_Rule]:
    rate = str(value)
    parts = key.split()
    if len(parts) == 1:
        methods: Set[str] = set()
        path = parts[0]
    else:
        methods = {_normalize_method(x) for x in parts[0].split("|") if x}
        path = " ".join(parts[1:])
    times, seconds = _parse_rate(rate)
    return _Rule(methods, _compile_pattern(path), times, seconds, f"{key}={value}")


def _rules_from_sequence(data: Iterable[Any]) -> List[_Rule]:
    rules: List[_Rule] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        rule = _rule_from_dict(it)
        if rule:
            rules.append(rule)
    return rules


def _rules_from_string(raw: str) -> List[_Rule]:
    rules: List[_Rule] = []
    for chunk in _csv_items(raw):
        s = chunk.strip()
        if not s:
            continue
        tail = search(r"(\S+)$", s)
        if not tail:
            continue
        rate = tail.group(1)
        try:
            times, seconds = _parse_rate(rate)
        except Exception:
            continue
        head = s[: -len(rate)].strip()
        toks = head.split()
        if not toks:
            continue
        if "/" in toks[0]:
            methods: Set[str] = set()
            path = head
        else:
            methods = {_normalize_method(x) for x in toks[0].split("|") if x}
            path = " ".join(toks[1:]).strip()
        if not path:
            path = "/"
        rules.append(_Rule(methods, _compile_pattern(path), times, seconds, s))
    return rules


def _load_rules(value: Optional[Union[str, Iterable[Any], Dict[str, Any]]]) -> List[_Rule]:
    """Load rules from any supported source: inline string, path, JSON/YAML data."""
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        path = Path(raw)
        if path.is_file():
            try:
                file_content = path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                LOGGER.warning(f"Cannot read rate limit rules file {path}: {exc}")
                return []
            if not file_content:
                return []
            # Allow JSON/YAML or CSV-like content inside the file
            return _load_rules(file_content)
        parsed = _try_json(raw)
        if parsed is not None:
            return _load_rules(parsed)
        with suppress(Exception):
            yaml_data = safe_load(raw)
            if isinstance(yaml_data, (dict, list)):
                return _load_rules(yaml_data)
        return _rules_from_string(raw)

    if isinstance(value, dict):
        rules: List[_Rule] = []
        for k, v in value.items():
            rule = _rule_from_mapping_key(str(k), v)
            if rule:
                rules.append(rule)
        return rules

    if isinstance(value, Iterable):
        return _rules_from_sequence(value)

    return []


def _client_identifier(request: Request) -> str:
    """Return the client IP address."""
    return request.client.host if request.client else "0.0.0.0"


def _limit_string(times: int, seconds: int) -> str:
    # Prefer friendly units when we can express exactly
    if seconds in (1, 60, 3600, 86400, 2592000, 31536000):
        unit_map = {1: "second", 60: "minute", 3600: "hour", 86400: "day", 2592000: "month", 31536000: "year"}
        unit = unit_map[seconds]
        return f"{times}/{unit}"

    for base, name in ((31536000, "year"), (2592000, "month"), (86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds % base == 0:
            n = seconds // base
            plural = name + ("s" if n != 1 else "")
            return f"{times}/{n}{plural}"

    return f"{times} per {seconds} seconds"


def _csv_items(s: str) -> List[str]:
    """Parse a CSV-like string of items using csv module.

    - Detects delimiter between comma and semicolon.
    - Handles quoted items and newlines.
    - Trims whitespace and drops empty fields.
    """
    if not s:
        return []
    sample = s
    try:
        dialect = Sniffer().sniff(sample, delimiters=",;")
        delimiter = dialect.delimiter
    except Exception:
        # Fallback: prefer comma when present
        delimiter = "," if ("," in s or ";" not in s) else ";"
    items: List[str] = []
    reader = csv_reader(StringIO(s), delimiter=delimiter, skipinitialspace=True)
    for row in reader:
        for field in row:
            val = field.strip()
            if val:
                items.append(val)
    return items


def _build_key_func():
    sel = (api_config.API_RATE_LIMIT_KEY or "ip").strip().lower()
    if sel == "ip":
        return _client_identifier
    if sel in ("ip_ua", "ip-user-agent", "ip-useragent"):

        def _key(req: Request) -> str:  # type: ignore[return-type]
            ip = _client_identifier(req)
            ua = req.headers.get("user-agent", "")
            return f"{ip}|{ua}"

        return _key
    if sel.startswith("header:"):
        header_name = sel.split(":", 1)[1].strip()

        def _key(req: Request) -> str:  # type: ignore[return-type]
            val = req.headers.get(header_name) or req.headers.get(header_name.title()) or ""
            return val or _client_identifier(req)

        return _key
    return _client_identifier


def _parse_exempt_ips(env_val: Optional[str]) -> List[Union[IPv4Network, IPv6Network]]:
    nets: List[Union[IPv4Network, IPv6Network]] = []
    if not env_val:
        return nets
    for tok in split(r"[\s,]+", env_val.strip()):
        if not tok:
            continue
        try:
            if "/" in tok:
                nets.append(ip_network(tok, strict=False))
            else:
                # single IP
                ip = ip_address(tok)
                nets.append(ip_network(ip.exploded + ("/32" if ip.version == 4 else "/128"), strict=False))
        except Exception:
            continue
    return nets


def is_enabled() -> bool:
    return _enabled


def _is_exempt(request: Request) -> bool:
    with suppress(Exception):
        cip = _client_identifier(request)
        ipobj = ip_address(cip)
        for net in _exempt_networks:
            if ipobj in net:
                return True
    return False


def _build_storage(cfg: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    # Optional storage options (JSON), can be augmented by Redis settings
    storage_options: Dict[str, Any] = {}
    so_raw = api_config.API_RATE_LIMIT_STORAGE_OPTIONS
    if so_raw:
        so = _try_json(so_raw)
        if isinstance(so, dict):
            storage_options = {str(k): v for k, v in so.items()}

    def _env_or_cfg(name: str, default: str | None = None) -> str | None:
        val = getenv(name)
        if val is not None:
            return val
        return cfg.get(name, default)  # type: ignore[return-value]

    storage: Optional[str] = None
    use_redis = str(_env_or_cfg("USE_REDIS", "no") or "no").lower() == "yes"
    if use_redis:
        sentinels = str(_env_or_cfg("REDIS_SENTINEL_HOSTS", "") or "").strip()
        sentinel_master = str(_env_or_cfg("REDIS_SENTINEL_MASTER", "") or "").strip()
        username = str(_env_or_cfg("REDIS_USERNAME", "") or "").strip()
        password = str(_env_or_cfg("REDIS_PASSWORD", "") or "").strip()
        redis_ssl = str(_env_or_cfg("REDIS_SSL", "no") or "no").lower() == "yes"
        # timeouts are in ms; convert to seconds for redis client options
        try:
            timeout_ms = float(str(_env_or_cfg("REDIS_TIMEOUT", "1000") or "1000"))
        except Exception:
            timeout_ms = 1000.0
        try:
            keepalive_pool = int(str(_env_or_cfg("REDIS_KEEPALIVE_POOL", "10") or "10"))
        except Exception:
            keepalive_pool = 10

        # Build options common to redis storages
        storage_options.setdefault("socket_timeout", timeout_ms / 1000.0)
        storage_options.setdefault("socket_connect_timeout", timeout_ms / 1000.0)
        storage_options.setdefault("socket_keepalive", True)
        storage_options.setdefault("max_connections", keepalive_pool)

        if sentinels and sentinel_master:
            # redis sentinel URI: redis+sentinel://[user:pass@]h1:26379,h2:26379/master
            auth = ""
            if username or password:
                auth = f"{username}:{password}@"
            # ensure ports on sentinels (default 26379)
            parts = []
            for item in sentinels.split():
                host, _, port = item.partition(":")
                parts.append(f"{host}:{port or '26379'}")
            hostlist = ",".join(parts)
            storage = f"redis+sentinel://{auth}{hostlist}/{sentinel_master}"
            # pass SSL and auth to sentinel via options
            storage_options.setdefault("ssl", redis_ssl)
            sent_user = str(_env_or_cfg("REDIS_SENTINEL_USERNAME", "") or "").strip()
            sent_pass = str(_env_or_cfg("REDIS_SENTINEL_PASSWORD", "") or "").strip()
            if sent_user or sent_pass:
                storage_options.setdefault("sentinel_kwargs", {"username": sent_user, "password": sent_pass})
        else:
            # Direct redis connection
            host = str(_env_or_cfg("REDIS_HOST", "") or "").strip()
            port = str(_env_or_cfg("REDIS_PORT", "6379") or "6379").strip()
            db = str(_env_or_cfg("REDIS_DATABASE", "0") or "0").strip()
            scheme = "rediss" if redis_ssl else "redis"
            auth = ""
            if username or password:
                auth = f"{username}:{password}@"
            if host:
                storage = f"{scheme}://{auth}{host}:{port}/{db}"

    # Final fallback
    if not storage:
        storage = "memory://"

    return storage, storage_options


def _path_variants(path: str) -> List[str]:
    paths = [path]
    rp = (api_config.API_ROOT_PATH or "").rstrip("/")
    if rp and path.startswith(rp + "/"):
        paths.append(path[len(rp) :])  # noqa: E203
    return paths


def _match_rule(method: str, path: str) -> Optional[str]:
    if not _rules:
        return None
    m = _normalize_method(method)
    paths = _path_variants(path)
    for rule in _rules:
        if rule.methods and m not in rule.methods and "*" not in rule.methods:
            continue
        for p in paths:
            if rule.pattern.match(p):
                return rule.limit_string
    return None


def _auth_default_limit(method: str, path: str) -> Optional[str]:
    if _normalize_method(method) != "POST":
        return None
    if _auth_limit is None:
        return None
    for candidate in _path_variants(path):
        if candidate.rstrip("/") == "/auth":
            return _auth_limit
    return None


def limiter_dep_dynamic():
    async def _dep(request: Request):  # pragma: no cover
        if not _enabled or _limiter is None:
            return None
        if _is_exempt(request):
            return None

        match = _match_rule(request.method, request.scope.get("path", "/"))
        if match is None:
            match = _auth_default_limit(request.method, request.scope.get("path", "/"))

        async def _noop(request: Request, response: Response | None = None):
            return None

        for lstr in _base_limits if match is None else [match]:
            await _limiter.limit(lstr)(_noop)(request, response=Response())  # type: ignore[arg-type]
        return None

    return Depends(_dep)


def setup_rate_limiter(app) -> None:
    if not api_config.rate_limit_enabled:
        LOGGER.info("API rate limiting disabled by configuration")
        return

    global _limiter, _enabled, _rules, _base_limits, _exempt_networks, _auth_limit

    _rules = _load_rules(getattr(api_config, "API_RATE_LIMIT_RULES", None))

    # Base/default limits (new simple string form wins over legacy split knobs)
    _base_limits = []
    default_rate = _resolve_rate(getattr(api_config, "API_RATE_LIMIT", None), DEFAULT_RATE[0], DEFAULT_RATE[1], label="API_RATE_LIMIT")
    if default_rate:
        _base_limits.append(_limit_string(*default_rate))

    auth_rate = _resolve_rate(
        getattr(api_config, "API_RATE_LIMIT_AUTH", None),
        DEFAULT_AUTH_RATE[0],
        DEFAULT_AUTH_RATE[1],
        label="API_RATE_LIMIT_AUTH",
        allow_disable=True,
    )
    _auth_limit = _limit_string(*auth_rate) if auth_rate else None

    # Auto-derive Redis settings, preferring environment variables first, then database
    try:
        cfg = get_db(log=False).get_config(
            global_only=True,
            methods=False,
            filtered_settings=(
                "USE_REDIS",
                "REDIS_HOST",
                "REDIS_PORT",
                "REDIS_DATABASE",
                "REDIS_TIMEOUT",
                "REDIS_KEEPALIVE_POOL",
                "REDIS_SSL",
                "REDIS_SSL_VERIFY",
                "REDIS_USERNAME",
                "REDIS_PASSWORD",
                "REDIS_SENTINEL_HOSTS",
                "REDIS_SENTINEL_USERNAME",
                "REDIS_SENTINEL_PASSWORD",
                "REDIS_SENTINEL_MASTER",
            ),
        )
    except Exception:
        cfg = {}

    storage, storage_options = _build_storage(cfg)

    _exempt_networks = _parse_exempt_ips(api_config.API_RATE_LIMIT_EXEMPT_IPS)

    # Normalize strategy names to SlowAPI/limits canonical values
    orig_strategy = (api_config.API_RATE_LIMIT_STRATEGY or "fixed-window").strip().lower()
    strategy = orig_strategy
    if strategy in ("fixed", "fixed-window", "fixed_window"):
        strategy = "fixed-window"
    elif strategy in ("moving", "moving-window", "moving_window"):
        strategy = "moving-window"
    elif strategy in ("sliding", "sliding-window", "sliding_window", "sliding-window-counter", "sliding_window_counter"):
        strategy = "sliding-window-counter"
    else:
        # Fallback to fixed-window if unknown
        strategy = "fixed-window"
        LOGGER.warning(f"Unknown API rate limit strategy '{orig_strategy}'; falling back to '{strategy}'")

    _limiter = Limiter(
        key_func=_build_key_func(),
        default_limits=_base_limits,  # type: ignore[arg-type]
        storage_uri=storage,
        storage_options=storage_options,
        strategy=strategy,
        headers_enabled=api_config.rate_limit_headers_enabled,
        key_prefix="bwapi-rl-",
    )
    app.state.limiter = _limiter

    # Use slowapi's default handler to include useful headers
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    _enabled = True
    LOGGER.info(
        f"Rate limiting enabled with storage={storage}; strategy={api_config.API_RATE_LIMIT_STRATEGY}; headers={api_config.rate_limit_headers_enabled}; defaults={len(_base_limits)}; rules={len(_rules)}; auth_limit={'on' if _auth_limit else 'off'}"
    )
