# -*- coding: utf-8 -*-
# Based on:
# https://pypi.org/project/pydantic-settings-yaml/

from contextlib import suppress
from os import getenv
from pathlib import Path
from re import compile as re_compile
from typing import Any, Dict, Mapping, Optional, Tuple, Type, Union

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, InitSettingsSource, SecretsSettingsSource, SettingsConfigDict
from pydantic_settings.sources import DotenvType, ENV_FILE_SENTINEL
from yaml import safe_load


class YamlSettingsConfigDict(SettingsConfigDict):
    # Keep compatibility with older custom config while aligning with upstream keys
    yaml_file: str
    yaml_file_encoding: Optional[str]
    yaml_config_section: Optional[str]


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
            # Replace the exact token as it appears (do not uppercase)
            data = data.replace(f"<file:{match}>", path.read_text("utf-8"))
    return data


def yaml_config_settings_source(
    settings: "YamlBaseSettings",
    *,
    yaml_file: Optional[Union[str, Path]] = None,
    secrets_dir: Optional[Union[str, Path]] = None,
    yaml_file_encoding: Optional[str] = None,
    yaml_config_section: Optional[str] = None,
) -> Dict[str, Any]:
    """Loads settings from a YAML file at `Config.yaml_file`

    "<file:xxxx>" patterns are replaced with the contents of file xxxx. The root path
    were to find the files is configured with `secrets_dir`.
    """
    if yaml_file is None:
        yaml_file = settings.model_config.get("yaml_file")
    if secrets_dir is None:
        secrets_dir = settings.model_config.get("secrets_dir")
    if yaml_file_encoding is None:
        yaml_file_encoding = settings.model_config.get("yaml_file_encoding")
    if yaml_config_section is None:
        yaml_config_section = settings.model_config.get("yaml_config_section")

    assert yaml_file, "Settings.yaml_file not properly configured"
    assert secrets_dir, "Settings.secrets_dir not properly configured"

    path = Path(yaml_file)
    secrets_path = Path(secrets_dir)

    if not path.exists():
        raise FileNotFoundError(f"Could not open yaml settings file at: {path}")

    encoding = yaml_file_encoding or "utf-8"
    loaded = safe_load(replace_secrets(secrets_path, path.read_text(encoding))) or {}
    if yaml_config_section:
        # Allow nested section selection when file contains multiple configs
        with suppress(Exception):
            section = loaded.get(yaml_config_section)
            if isinstance(section, dict):
                return section
    return loaded


class YamlConfigSettingsSource(DotEnvSettingsSource):
    """
    A simple settings source class that loads variables from a YAML file

    Note: slightly adapted version of JsonConfigSettingsSource from docs.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        yaml_file: Optional[str] = None,
        env_file: Optional[DotenvType] = ENV_FILE_SENTINEL,
        env_file_encoding: Optional[str] = None,
        case_sensitive: Optional[bool] = None,
        env_prefix: Optional[str] = None,
        env_nested_delimiter: Optional[str] = None,
        secrets_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self._yaml_data: dict = yaml_config_settings_source(
            settings_cls,
            yaml_file=yaml_file,
            secrets_dir=secrets_dir,
            yaml_file_encoding=settings_cls.model_config.get("yaml_file_encoding"),  # type: ignore[attr-defined]
            yaml_config_section=settings_cls.model_config.get("yaml_config_section"),  # type: ignore[attr-defined]
        )  # type: ignore

        for k, v in self._yaml_data.items():
            self._yaml_data[k.upper()] = v

        super().__init__(settings_cls, env_file, env_file_encoding, case_sensitive, env_prefix, env_nested_delimiter)  # type: ignore

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
    """Extend BaseSettings to also read from a YAML file.

    Precedence (high → low): init kwargs, env, secrets, YAML, dotenv, defaults.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: SecretsSettingsSource,
    ):
        """Insert YAML source between env and dotenv with values from model_config."""
        yaml_source = YamlConfigSettingsSource(
            settings_cls,
            yaml_file=settings_cls.model_config.get("yaml_file"),  # type: ignore[attr-defined]
            env_file=settings_cls.model_config.get("env_file"),  # type: ignore[attr-defined]
            env_file_encoding=settings_cls.model_config.get("env_file_encoding"),  # type: ignore[attr-defined]
            case_sensitive=settings_cls.model_config.get("case_sensitive"),  # type: ignore[attr-defined]
            env_prefix=settings_cls.model_config.get("env_prefix"),  # type: ignore[attr-defined]
            env_nested_delimiter=settings_cls.model_config.get("env_nested_delimiter"),  # type: ignore[attr-defined]
            secrets_dir=settings_cls.model_config.get("secrets_dir"),  # type: ignore[attr-defined]
        )

        # Keep project logic: env → secrets → YAML → dotenv (then defaults)
        return (init_settings, env_settings, file_secret_settings, yaml_source, dotenv_settings)

    # Baseline defaults; models can override via their own model_config
    model_config = SettingsConfigDict(
        secrets_dir=getenv("SETTINGS_SECRETS_DIR", "/etc/secrets"),
        yaml_file=getenv("SETTINGS_YAML_FILE", "/etc/bunkerweb/config.yml"),
    )  # type: ignore


__ALL__ = (YamlBaseSettings, YamlSettingsConfigDict)
