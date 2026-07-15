from ipaddress import ip_address
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, RootModel, BeforeValidator
from typing import Optional, List, Dict, Union, Literal, Annotated, Any
from re import compile as re_compile

# Shared helpers for Configs
NAME_RX = re_compile(r"^[\w_-]{1,255}$")


def normalize_config_type(t: str) -> str:
    return t.strip().replace("-", "_").lower()


def validate_config_name(name: str) -> Optional[str]:
    if not name or not NAME_RX.match(name):
        return "Invalid name: must match ^[\\w_-]{1,255}$"
    return None


# Accepted config types - Literal includes both underscore and hyphen variants for OpenAPI docs
# Normalized form uses underscores internally
ConfigTypeLiteral = Literal[
    # HTTP-level
    "http",
    "server_http",
    "server-http",
    "default_server_http",
    "default-server-http",
    # ModSecurity
    "modsec_crs",
    "modsec-crs",
    "modsec",
    # Stream
    "stream",
    "server_stream",
    "server-stream",
    # CRS plugins
    "crs_plugins_before",
    "crs-plugins-before",
    "crs_plugins_after",
    "crs-plugins-after",
]

# Set of normalized config types for validation
CONFIG_TYPES = {
    # HTTP-level
    "http",
    "server_http",
    "default_server_http",
    # ModSecurity
    "modsec_crs",
    "modsec",
    # Stream
    "stream",
    "server_stream",
    # CRS plugins
    "crs_plugins_before",
    "crs_plugins_after",
}


def _normalize_and_validate_config_type(v: str) -> str:
    """Normalize and validate config type, raising ValueError if invalid."""
    if not isinstance(v, str):
        raise ValueError("type must be a string")
    normalized = normalize_config_type(v)
    if normalized not in CONFIG_TYPES:
        raise ValueError(f"Invalid type: must be one of {', '.join(sorted(CONFIG_TYPES))}")
    return normalized


# Annotated type that normalizes input and validates against CONFIG_TYPES
ConfigType = Annotated[ConfigTypeLiteral, BeforeValidator(_normalize_and_validate_config_type)]


class BanRequest(BaseModel):
    ip: str
    exp: int = Field(86400, description="Expiration in seconds (0 means permanent)")
    reason: str = Field("api", description="Reason for ban")
    service: Optional[str] = Field(None, description="Service name if service-specific ban")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v):
        v = v.strip()
        ip_address(v)  # Raises ValueError for invalid IPs
        return v

    @field_validator("exp")
    @classmethod
    def validate_exp(cls, v):
        if v < 0:
            raise ValueError("exp must be non-negative")
        return v


class UnbanRequest(BaseModel):
    ip: str
    service: Optional[str] = Field(None, description="Service name if service-specific unban")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v):
        v = v.strip()
        ip_address(v)  # Raises ValueError for invalid IPs
        return v


# Instances
class InstanceCreateRequest(BaseModel):
    hostname: str
    name: Optional[str] = Field(None, description="Friendly name for the instance")
    port: Optional[int] = Field(None, description="API HTTP port; defaults from settings if omitted")
    listen_https: Optional[bool] = Field(None, description="If true, instance API listens over HTTPS")
    https_port: Optional[int] = Field(None, description="API HTTPS port; defaults from settings if omitted")
    server_name: Optional[str] = Field(None, description="API server_name/Host header; defaults if omitted")
    method: Optional[str] = Field("ui", description='Source method tag (defaults to "ui")')


class InstancesDeleteRequest(BaseModel):
    instances: List[str]


class InstanceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Friendly name for the instance")
    port: Optional[int] = Field(None, description="API HTTP port")
    listen_https: Optional[bool] = Field(None, description="If true, instance API listens over HTTPS")
    https_port: Optional[int] = Field(None, description="API HTTPS port")
    server_name: Optional[str] = Field(None, description="API server_name/Host header")
    method: Optional[str] = Field(None, description="Source method tag")


# Services
class ServiceCreateRequest(BaseModel):
    server_name: str = Field(..., description="Service server_name (first token used as ID)")
    is_draft: bool = Field(False, description="Create as draft service")
    variables: Optional[Dict[str, str]] = Field(None, description="Unprefixed settings for the service")


class ServiceUpdateRequest(BaseModel):
    server_name: Optional[str] = Field(None, description="Rename the service (first token used as ID)")
    is_draft: Optional[bool] = Field(None, description="Set draft flag")
    variables: Optional[Dict[str, str]] = Field(None, description="Unprefixed settings to upsert for the service")


# Configs
class ConfigCreateRequest(BaseModel):
    service: Optional[str] = Field(None, description='Service id; use "global" or leave empty for global')
    type: ConfigType = Field(..., description="Config type")
    name: str = Field(..., description=r"Config name (^[\\w_-]{1,255}$)")
    data: str = Field(..., description="Config content as UTF-8 string")
    is_draft: bool = Field(False, description="Mark custom config as draft")

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        err = validate_config_name(v)
        if err:
            raise ValueError(err)
        return v


def _normalize_optional_config_type(v: Optional[str]) -> Optional[str]:
    """Normalize and validate optional config type."""
    if v is None:
        return None
    return _normalize_and_validate_config_type(v)


# Optional ConfigType for update requests
OptionalConfigType = Annotated[Optional[ConfigTypeLiteral], BeforeValidator(_normalize_optional_config_type)]


class ConfigUpdateRequest(BaseModel):
    service: Optional[str] = Field(None, description='New service id; use "global" or leave empty for global')
    type: OptionalConfigType = Field(None, description="New config type")
    name: Optional[str] = Field(None, description="New config name")
    data: Optional[str] = Field(None, description="New config content as UTF-8 string")
    is_draft: Optional[bool] = Field(None, description="Update draft flag")

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        err = validate_config_name(v)
        if err:
            raise ValueError(err)
        return v


class ConfigKey(BaseModel):
    service: Optional[str] = Field(None, description='Service id; use "global" or leave empty for global')
    type: ConfigType
    name: str

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        err = validate_config_name(v)
        if err:
            raise ValueError(err)
        return v


class ConfigsDeleteRequest(BaseModel):
    configs: List[ConfigKey] = Field(..., min_length=1)


# Cache
class CacheFileKey(BaseModel):
    service: Optional[str] = Field(None, description='Service id; use "global" or leave empty for global')
    plugin: str
    jobName: str
    fileName: str

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("plugin", "jobName", "fileName")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must be a non-empty string")
        return v


class CacheFilesDeleteRequest(BaseModel):
    cache_files: List[CacheFileKey] = Field(..., min_length=1)


# Web cache (proxy_cache) management
class WebCachePurgeUrl(BaseModel):
    url: str = Field(..., description="Absolute URL whose cached response should be purged")
    key: Optional[str] = Field(None, description="Custom PROXY_CACHE_KEY template if the service overrides the default")

    @field_validator("url")
    @classmethod
    def _non_empty_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must be a non-empty string")
        return v


class WebCachePurgeRequest(BaseModel):
    scope: Literal["all", "url"] = Field("url", description='"all" clears the whole proxy cache; "url" purges specific URLs')
    urls: Optional[List[WebCachePurgeUrl]] = Field(None, description="URLs to purge when scope is 'url'")
    service: Optional[str] = Field(None, description="Reserved for future per-service purge (currently informational)")

    @model_validator(mode="after")
    def _require_urls_for_url_scope(self):
        if self.scope == "url" and not self.urls:
            raise ValueError("scope 'url' requires a non-empty 'urls' list")
        return self


# Jobs
class JobItem(BaseModel):
    plugin: str
    name: Optional[str] = Field(None, description="Job name (optional; not required to trigger)")

    @field_validator("plugin")
    @classmethod
    def _non_empty_plugin(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("plugin must be a non-empty string")
        return v


class RunJobsRequest(BaseModel):
    jobs: List[JobItem] = Field(..., min_length=1)


# Global settings
Scalar = Union[str, int, float, bool, None]


class GlobalSettingsUpdate(RootModel[Dict[str, Scalar]]):
    @field_validator("root")
    @classmethod
    def _validate_scalars(cls, v: Dict[str, Scalar]) -> Dict[str, Scalar]:
        if not isinstance(v, dict):
            raise ValueError("Body must be a JSON object")
        for k, val in v.items():
            if isinstance(val, (dict, list)):
                raise ValueError(f"Invalid value for {k}: must be scalar")
        return v


class ValidateSettingRequest(BaseModel):
    setting: str = Field(..., description="Setting name to validate")
    value: Optional[str] = Field(None, description="Value to validate against the setting regex")
    multisite: bool = Field(False, description="Whether to validate as a multisite setting")
    extra_services: Optional[List[str]] = Field(None, description="Additional service names for context")


_ALLOWED_BULK_METHODS = {"autoconf", "scheduler", "manual", "ui", "wizard"}


def _validate_bulk_method(v: str) -> str:
    """Only allow known bulk methods — prevents overwriting UI/API-managed records."""
    if v not in _ALLOWED_BULK_METHODS:
        raise ValueError(f"Method '{v}' is not allowed for bulk operations. Allowed: {', '.join(sorted(_ALLOWED_BULK_METHODS))}")
    return v


class SaveConfigRequest(BaseModel):
    config: Dict[str, str] = Field(..., description="Full config environment dict")
    method: str = Field(..., description="Source method (e.g. 'autoconf')")
    changed: bool = Field(False, description="Whether to immediately signal changes")
    disable_cleanup: bool = Field(False, description="Whether to cleanup or convert to draft any existing services not in the provided config dict")

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: str) -> str:
        return _validate_bulk_method(v)


class BulkUpdateInstancesRequest(BaseModel):
    instances: List[Dict[str, Any]] = Field(..., description="List of instance dicts to persist")
    method: str = Field(..., description="Source method (e.g. 'autoconf')")
    changed: bool = Field(False, description="Whether to signal instance changes")

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: str) -> str:
        return _validate_bulk_method(v)


class BulkSaveCustomConfigsRequest(BaseModel):
    custom_configs: List[Dict[str, Any]] = Field(..., description="List of custom config dicts")
    method: str = Field(..., description="Source method (e.g. 'autoconf')")
    changed: bool = Field(False, description="Whether to signal custom config changes")
    disable_cleanup: bool = Field(False, description="Whether to cleanup or convert to draft any existing configs not in the list")

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: str) -> str:
        return _validate_bulk_method(v)


# Plugins (external/pro bulk update)
class UpdateExternalPluginsRequest(BaseModel):
    plugins: list = Field(..., min_length=0)
    plugin_type: str = Field("external", alias="_type", pattern="^(external|pro)$")
    delete_missing: bool = True

    model_config = ConfigDict(populate_by_name=True)


# Instance status
class InstanceStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(up|down|failover)$")


# Job dispatch
class DispatchJobItem(BaseModel):
    name: str = Field(..., pattern=r"^[\w.-]{1,128}$")
    plugin_id: str = Field(..., pattern=r"^[\w.-]{2,64}$")
    file: str = Field(..., pattern=r"^[\w.-]{1,128}\.py$")
    path: str
    every: str = Field(..., pattern="^(once|minute|hour|day|week)$")
    reload: bool = False
    run_async: bool = Field(False, alias="async")

    model_config = ConfigDict(populate_by_name=True)


class DispatchJobsRequest(BaseModel):
    jobs: List[DispatchJobItem] = Field(..., min_length=1, max_length=100)
