from functools import cached_property
from os import sep
from os.path import join
from sys import path as sys_path

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)


class UiConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: str = "7000"
    API_ADDR: str = ""
    API_TOKEN: str = ""
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    # The reading order is:
    # 1. Environment variables
    # 2. YAML file
    # 3. .env file
    # 4. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=join(sep, "etc", "bunkerweb", "config.yaml"),
        env_file=join(sep, "etc", "bunkerweb", "ui.conf"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


if __name__ == "__main__":
    from json import dumps
    from os import _exit, environ
    from regex import match as regex_match

    ui_config = UiConfig("ui", **environ)

    if not regex_match(
        r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]).{8,}$",
        ui_config.ADMIN_PASSWORD,
    ):
        _exit(1)

    data = {
        "listen_addr": ui_config.LISTEN_ADDR,
        "listen_port": ui_config.LISTEN_PORT,
        "api_addr": ui_config.API_ADDR,
        "api_token": ui_config.API_TOKEN,
        "admin_username": ui_config.ADMIN_USERNAME,
        "admin_password": ui_config.ADMIN_PASSWORD,
    }

    print(dumps(data), flush=True)
    _exit(0)
