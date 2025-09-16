from pydantic import BaseModel, Field, field_validator, RootModel
from typing import Optional, List, Dict, Union
from re import compile as re_compile

# Shared helpers for Configs
NAME_RX = re_compile(r"^[\w_-]{1,64}$")


def normalize_config_type(t: str) -> str:
    return t.strip().replace("-", "_").lower()


def validate_config_name(name: str) -> Optional[str]:
    if not name or not NAME_RX.match(name):
        return "Invalid name: must match ^[\\w_-]{1,64}$"
    return None


# Accepted config types (normalized form)
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


class BanRequest(BaseModel):
    ip: str
    exp: int = Field(86400, description="Expiration in seconds (0 means permanent)")
    reason: str = Field("api", description="Reason for ban")
    service: Optional[str] = Field(None, description="Service name if service-specific ban")


class UnbanRequest(BaseModel):
    ip: str
    service: Optional[str] = Field(None, description="Service name if service-specific unban")


# Instances
class InstanceCreateRequest(BaseModel):
    hostname: str
    name: Optional[str] = Field(None, description="Friendly name for the instance")
    port: Optional[int] = Field(None, description="API HTTP port; defaults from settings if omitted")
    server_name: Optional[str] = Field(None, description="API server_name/Host header; defaults if omitted")
    method: Optional[str] = Field("ui", description='Source method tag (defaults to "ui")')


class InstancesDeleteRequest(BaseModel):
    instances: List[str]


class InstanceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Friendly name for the instance")
    port: Optional[int] = Field(None, description="API HTTP port")
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
    type: str = Field(..., description="Config type, e.g., http, server_http, modsec, ...")
    name: str = Field(..., description=r"Config name (^[\\w_-]{1,64}$)")
    data: str = Field(..., description="Config content as UTF-8 string")

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("type")
    @classmethod
    def _normalize_and_check_type(cls, v: str) -> str:
        t = normalize_config_type(v)
        if t not in CONFIG_TYPES:
            raise ValueError("Invalid type")
        return t

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        err = validate_config_name(v)
        if err:
            raise ValueError(err)
        return v


class ConfigUpdateRequest(BaseModel):
    service: Optional[str] = Field(None, description='New service id; use "global" or leave empty for global')
    type: Optional[str] = Field(None, description="New config type")
    name: Optional[str] = Field(None, description="New config name")
    data: Optional[str] = Field(None, description="New config content as UTF-8 string")

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("type")
    @classmethod
    def _normalize_and_check_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        t = normalize_config_type(v)
        if t not in CONFIG_TYPES:
            raise ValueError("Invalid type")
        return t

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
    type: str
    name: str

    @field_validator("service")
    @classmethod
    def _normalize_service(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "", "global") else v

    @field_validator("type")
    @classmethod
    def _normalize_and_check_type(cls, v: str) -> str:
        t = normalize_config_type(v)
        if t not in CONFIG_TYPES:
            raise ValueError("Invalid type")
        return t

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


# Global config
Scalar = Union[str, int, float, bool, None]


class GlobalConfigUpdate(RootModel[Dict[str, Scalar]]):
    @field_validator("root")
    @classmethod
    def _validate_scalars(cls, v: Dict[str, Scalar]) -> Dict[str, Scalar]:
        if not isinstance(v, dict):
            raise ValueError("Body must be a JSON object")
        for k, val in v.items():
            if isinstance(val, (dict, list)):
                raise ValueError(f"Invalid value for {k}: must be scalar")
        return v
