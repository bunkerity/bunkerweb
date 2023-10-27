# -*- coding: utf-8 -*-
# Based on:
# https://pypi.org/project/pydantic-settings-yaml/

from os import getenv
from pathlib import Path
from re import compile as re_compile
from typing import Any, Dict, Literal, Mapping, Optional, Tuple, Type, Union

from pydantic._internal._utils import deep_update
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings.sources import DotenvType, ENV_FILE_SENTINEL
from yaml import safe_load


class YamlSettingsConfigDict(SettingsConfigDict, total=False):
    yaml_file: str


def replace_secrets(secrets_dir: Path, data: str) -> str:
    """
    Replace "<file:xxxx>" secrets in given data

    """
    pattern = re_compile(r"\<file\:([^>]*)\>")

    for match in pattern.findall(data):
        relpath = Path(match)
        path = secrets_dir / relpath

        if not path.exists():
            print(
                f"Secret file referenced in yaml file not found: {path}, settings will not be loaded from secret file.",
                flush=True,
            )
        else:
            data = data.replace(f"<file:{match.upper()}>", path.read_text("utf-8"))
    return data


def yaml_config_settings_source(
    settings: "YamlBaseSettings",
    *,
    yaml_file: Optional[Union[str, Path]] = None,
    secrets_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Loads settings from a YAML file at `Config.yaml_file`

    "<file:xxxx>" patterns are replaced with the contents of file xxxx. The root path
    were to find the files is configured with `secrets_dir`.
    """
    if yaml_file is None:
        yaml_file = settings.model_config.get("yaml_file")
    if secrets_dir is None:
        secrets_dir = settings.model_config.get("secrets_dir")

    assert yaml_file, "Settings.yaml_file not properly configured"
    assert secrets_dir, "Settings.secrets_dir not properly configured"

    path = Path(yaml_file)
    secrets_path = Path(secrets_dir)

    if not path.exists():
        raise FileNotFoundError(f"Could not open yaml settings file at: {path}")

    return safe_load(replace_secrets(secrets_path, path.read_text("utf-8")))


class YamlConfigSettingsSource(DotEnvSettingsSource):
    """
    A simple settings source class that loads variables from a YAML file

    Note: slightly adapted version of JsonConfigSettingsSource from docs.
    """

    def __init__(
        self,
        settings_cls: type[DotEnvSettingsSource],
        bw_service: Optional[Literal["core", "autoconf", "ui"]] = None,
        yaml_file: Optional[str] = None,
        env_file: Optional[DotenvType] = ENV_FILE_SENTINEL,
        env_file_encoding: Optional[str] = None,
        case_sensitive: Optional[bool] = None,
        env_prefix: Optional[str] = None,
        env_nested_delimiter: Optional[str] = None,
        secrets_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self._yaml_data = yaml_config_settings_source(settings_cls, yaml_file=yaml_file, secrets_dir=secrets_dir) or {}

        for k, v in (self._yaml_data.get("global", None) or {}).items():
            self._yaml_data[k.upper()] = v

        for k, v in (self._yaml_data.get(bw_service, None) or {}).items():
            self._yaml_data[k.upper()] = v

        super().__init__(
            settings_cls,
            env_file,
            env_file_encoding,
            case_sensitive,
            env_prefix,
            env_nested_delimiter,
        )

    def _load_env_vars(self) -> Mapping[str, Optional[str]]:
        return self._yaml_data

    def get_field_value(self, field: FieldInfo, field_name: str) -> Tuple[Any, str, bool]:
        field_value = self._yaml_data.get(field_name) if self._yaml_data else None
        return field_value, field_name, False

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        return value

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = super().__call__()

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(field, field_name)
            field_value = self.prepare_field_value(field_name, field, field_value, value_is_complex)
            if field_value is not None:
                d[field_key] = field_value

        return d


class YamlBaseSettings(BaseSettings):
    """Allows to specify a 'yaml_file' path in the Config section.

    Field value priority:

    1. Arguments passed to the Settings class initializer.
    2. Variables from Config.yaml_file (reading secrets at "<file:xxxx>" entries)
    3. Environment variables
    4. Variables loaded from a dotenv (.env) file (if Config.env_file is set)

    Default paths:

    - yaml_file: "/etc/config/config.yaml" or env.SETTINGS_YAML_FILE

    See also:

      https://pydantic-docs.helpmanual.io/usage/settings/
    """

    def __init__(
        __pydantic_self__,
        _bw_service: Optional[Literal["core", "autoconf", "ui"]] = None,
        _yaml_file: Optional[str] = None,
        _case_sensitive: Optional[bool] = None,
        _env_prefix: Optional[str] = None,
        _env_file: Optional[DotenvType] = ENV_FILE_SENTINEL,
        _env_file_encoding: Optional[str] = None,
        _env_nested_delimiter: Optional[str] = None,
        _secrets_dir: Optional[Union[str, Path]] = None,
        **values: Any,
    ) -> None:
        # Uses something other than `self` the first arg to allow "self" as a settable attribute
        super().__init__(
            **__pydantic_self__._settings_build_values(
                values,
                _bw_service=_bw_service,
                _yaml_file=_yaml_file,
                _case_sensitive=_case_sensitive,
                _env_prefix=_env_prefix,
                _env_file=_env_file,
                _env_file_encoding=_env_file_encoding,
                _env_nested_delimiter=_env_nested_delimiter,
                _secrets_dir=_secrets_dir,
            )
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings,
        env_settings,
        yaml_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Define the sources and their order for loading the settings values.

        Args:
            settings_cls: The Settings class.
            init_settings: The `InitSettingsSource` instance.
            env_settings: The `EnvSettingsSource` instance.
            dotenv_settings: The `DotEnvSettingsSource` instance.
            file_secret_settings: The `SecretsSettingsSource` instance.

        Returns:
            A tuple containing the sources and their order for
            loading the settings values.
        """
        return (
            init_settings,
            env_settings,
            yaml_settings,
            dotenv_settings,
            file_secret_settings,
        )

    def _settings_build_values(
        self,
        init_kwargs: dict[str, Any],
        _bw_service: Optional[
            Union[
                Literal["core"],
                Literal["scheduler"],
                Literal["autoconf"],
                Literal["ui"],
            ]
        ] = None,
        _case_sensitive: bool | None = None,
        _yaml_file: Optional[str] = None,
        _env_prefix: Optional[str] = None,
        _env_file: DotenvType | None = None,
        _env_file_encoding: Optional[str] = None,
        _env_nested_delimiter: Optional[str] = None,
        _secrets_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        # Determine settings config values
        case_sensitive = _case_sensitive if _case_sensitive is not None else self.model_config.get("case_sensitive")
        env_prefix = _env_prefix if _env_prefix is not None else self.model_config.get("env_prefix")
        env_file = _env_file if _env_file != ENV_FILE_SENTINEL else self.model_config.get("env_file")
        env_file_encoding = _env_file_encoding if _env_file_encoding is not None else self.model_config.get("env_file_encoding")
        env_nested_delimiter = _env_nested_delimiter if _env_nested_delimiter is not None else self.model_config.get("env_nested_delimiter")
        secrets_dir = _secrets_dir if _secrets_dir is not None else self.model_config.get("secrets_dir")

        # Configure built-in sources
        init_settings = InitSettingsSource(self.__class__, init_kwargs=init_kwargs)
        env_settings = EnvSettingsSource(
            self.__class__,
            case_sensitive=case_sensitive,
            env_prefix=env_prefix,
            env_nested_delimiter=env_nested_delimiter,
        )
        yaml_settings = YamlConfigSettingsSource(self.__class__, bw_service=_bw_service, yaml_file=_yaml_file)
        dotenv_settings = DotEnvSettingsSource(
            self.__class__,
            env_file=env_file,
            env_file_encoding=env_file_encoding,
            case_sensitive=case_sensitive,
            env_prefix=env_prefix,
            env_nested_delimiter=env_nested_delimiter,
        )

        file_secret_settings = SecretsSettingsSource(
            self.__class__,
            secrets_dir=secrets_dir,
            case_sensitive=case_sensitive,
            env_prefix=env_prefix,
        )
        # Provide a hook to set built-in sources priority and add / remove sources
        sources = self.settings_customise_sources(
            self.__class__,
            init_settings=init_settings,
            env_settings=env_settings,
            yaml_settings=yaml_settings,
            dotenv_settings=dotenv_settings,
            file_secret_settings=file_secret_settings,
        )
        if sources:
            return deep_update(*reversed([source() for source in sources]))
        else:
            # no one should mean to do this, but I think returning an empty dict is marginally preferable
            # to an informative error and much better than a confusing error
            return {}

    model_config = SettingsConfigDict(
        secrets_dir=getenv("SETTINGS_SECRETS_DIR", "/etc/secrets"),
        yaml_file=getenv("SETTINGS_YAML_FILE", "/etc/config/config.yaml"),
    )


__ALL__ = (YamlBaseSettings, YamlSettingsConfigDict)
