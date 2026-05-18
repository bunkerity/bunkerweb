from os import getenv, sep
from os.path import join
from sys import path as sys_path
from typing import Optional, Union
from warnings import filterwarnings

# Ensure shared libs are importable when running in container
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)


# Suppress pydantic_settings warning about missing secrets directory in dev environments
filterwarnings("ignore", message=r'.*directory ".*" does not exist', category=UserWarning, module="pydantic_settings")

from .yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore


class ApiConfig(YamlBaseSettings):
    """API runtime configuration loaded from YAML/env/secrets with sensible defaults.

    Reading order:
    1. Environment variables
    2. Secrets files
    3. YAML file
    4. .env file
    5. Defaults below
    """

    # Biscuit
    CHECK_PRIVATE_IP: bool | str = "yes"  # allow "yes"/"no" in YAML
    # Biscuit token lifetime (seconds). 0 or "off" disables expiry.
    API_BISCUIT_TTL_SECONDS: int | str = 3600

    # FastAPI runtime toggles
    API_DOCS_URL: Optional[str] = "/docs"
    API_REDOC_URL: Optional[str] = "/redoc"
    API_OPENAPI_URL: Optional[str] = "/openapi.json"
    API_ROOT_PATH: Optional[str] = None

    # Auth: simple Bearer token fallback
    API_TOKEN: Optional[str] = None

    # Whitelist
    API_WHITELIST_ENABLED: bool | str = "yes"
    API_WHITELIST_IPS: str = "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"

    # Rate limiting
    API_RATE_LIMIT_ENABLED: bool | str = "yes"
    API_RATE_LIMIT: Optional[str] = "100r/m"
    API_RATE_LIMIT_AUTH: Optional[str] = "10r/m"
    API_RATE_LIMIT_STORAGE_OPTIONS: Optional[str] = None
    API_RATE_LIMIT_STRATEGY: str = "fixed-window"
    API_RATE_LIMIT_HEADERS_ENABLED: bool | str = "yes"
    API_RATE_LIMIT_RULES: Optional[Union[str, object]] = None
    API_RATE_LIMIT_KEY: str = "ip"
    API_RATE_LIMIT_EXEMPT_IPS: Optional[str] = None

    model_config = YamlSettingsConfigDict(  # type: ignore
        yaml_file=getenv("SETTINGS_YAML_FILE", "/etc/bunkerweb/api.yml"),
        env_file=getenv("SETTINGS_ENV_FILE", "/etc/bunkerweb/api.env"),
        secrets_dir=getenv("SETTINGS_SECRETS_DIR", "/run/secrets"),
        env_file_encoding="utf-8",
        extra="allow",
    )

    # --- Properties mapped to old Settings interface ---
    @property
    def check_private_ip(self) -> bool:
        val = str(self.CHECK_PRIVATE_IP).strip().lower()
        return val in ("1", "true", "yes", "on")

    @staticmethod
    def _maybe_url(value: Optional[str], default: Optional[str]) -> Optional[str]:
        if value is None:
            return default
        lowered = value.strip().lower()
        return None if lowered in ("", "no", "none", "disabled", "off", "false", "0") else value

    @property
    def docs_url(self) -> Optional[str]:
        return self._maybe_url(self.API_DOCS_URL, "/docs")

    @property
    def redoc_url(self) -> Optional[str]:
        return self._maybe_url(self.API_REDOC_URL, "/redoc")

    @property
    def openapi_url(self) -> Optional[str]:
        return self._maybe_url(self.API_OPENAPI_URL, "/openapi.json")

    @property
    def whitelist_enabled(self) -> bool:
        v = str(self.API_WHITELIST_ENABLED).strip().lower()
        return v in ("1", "true", "yes", "on")

    @property
    def biscuit_ttl_seconds(self) -> int:
        """Return Biscuit token TTL in seconds; 0 means disabled."""
        raw = str(self.API_BISCUIT_TTL_SECONDS).strip().lower()
        if raw in ("off", "disabled", "none", "false", "no", ""):
            return 0
        try:
            v = int(float(raw))  # allow strings/numeric
            return max(0, v)
        except Exception:
            return 3600

    # Rate limiting mapped properties
    @property
    def rate_limit_enabled(self) -> bool:
        v = str(self.API_RATE_LIMIT_ENABLED).strip().lower()
        return v in ("1", "true", "yes", "on")

    @property
    def rate_limit_headers_enabled(self) -> bool:
        v = str(self.API_RATE_LIMIT_HEADERS_ENABLED).strip().lower()
        return v in ("1", "true", "yes", "on")

    # Internal API resolution, keeping DB-sourced fallbacks
    @property
    def internal_api_port(self) -> str:
        try:
            from .utils import get_db  # late import to avoid cycles

            cfg = get_db(log=False).get_config(global_only=True, methods=False, filtered_settings=("API_HTTP_PORT",))
            return str(cfg.get("API_HTTP_PORT", "5000"))
        except Exception:
            return "5000"

    @property
    def internal_api_host_header(self) -> str:
        try:
            from .utils import get_db  # late import to avoid cycles

            cfg = get_db(log=False).get_config(global_only=True, methods=False, filtered_settings=("API_SERVER_NAME",))
            return str(cfg.get("API_SERVER_NAME", "bwapi"))
        except Exception:
            return "bwapi"

    @property
    def internal_endpoint(self) -> str:
        return f"http://127.0.0.1:{self.internal_api_port}"


api_config = ApiConfig()
