#!/usr/bin/env python3

from io import StringIO
from json import loads
from glob import glob
from pathlib import Path
from pytablewriter import MarkdownTableWriter
import requests
import zipfile
import shutil
from contextlib import suppress
from os import getenv, path


def print_md_table(settings) -> MarkdownTableWriter:
    writer = MarkdownTableWriter(
        headers=["Setting", "Default", "Context", "Multiple", "Description"],
        value_matrix=[
            [
                f"`{setting}`",
                "" if data["default"] == "" else f"`{data['default']}`",
                data["context"],
                "no" if "multiple" not in data else "yes",
                data["help"],
            ]
            for setting, data in settings.items()
        ],
    )
    return writer


def stream_support(support) -> str:
    md = "STREAM support "
    if support == "no":
        md += ":x:"
    elif support == "yes":
        md += ":white_check_mark:"
    else:
        md += ":warning:"
    return md


def pro_title(title: str) -> str:
    return f"## {title} <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'>\n"


def get_readme_content(plugin_dir):
    """Read README.md content from plugin directory if it exists."""
    readme_path = Path(plugin_dir, "README.md")
    if readme_path.exists():
        with readme_path.open("r") as f:
            return f.read()
    return None


def get_global_readme_content():
    """Read README.md content for global settings if it exists."""
    readme_path = Path("src/common/README.md")
    if readme_path.exists():
        with readme_path.open("r") as f:
            return f.read()
    return None


doc = StringIO()

print("# Features\n", file=doc)
print(
    '!!! info "Settings generator tool"\n\n    To help you tune BunkerWeb, we have made an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io/?utm_campaign=self&utm_source=doc).\n',
    file=doc,
)
print(
    "This section contains the full list of settings supported by BunkerWeb."
    + " If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section of the documentation."
    + " Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.\n",
    file=doc,
)
# print(
#     "As a general rule when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary"
#     + " (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes` for example.\n",
#     file=doc,
# )
# print(
#     'When settings are considered as "multiple", it means that you can have multiple groups of settings for the same feature by adding numbers as suffix like `REVERSE_PROXY_URL_1=/subdir`,'
#     + " `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.\n",
#     file=doc,
# )

# Print global settings
print("## Global settings\n", file=doc)
print(f"\n{stream_support('partial')}\n", file=doc)
# Check if README.md exists for global settings and use its content instead
global_readme = get_global_readme_content()
if global_readme:
    print(global_readme, file=doc)
else:
    with open("src/common/settings.json", "r") as f:
        print(print_md_table(loads(f.read())), file=doc)
        print(file=doc)

# Get core plugins
core_settings = {}
for core in glob("src/common/core/*/plugin.json"):
    plugin_dir = path.dirname(core)
    with open(core, "r") as f:
        with suppress(Exception):
            core_plugin = loads(f.read())
            if len(core_plugin["settings"]) > 0:
                core_plugin["dir"] = plugin_dir
                core_settings[core_plugin["name"]] = core_plugin

# Get PRO plugins
if getenv("VERSION"):
    version = getenv("VERSION")
else:
    with open("src/VERSION", "r") as f:
        version = f.read().strip()
url = f"https://assets.bunkerity.com/bw-pro/preview/v{version}.zip"
response = requests.get(url)
response.raise_for_status()
Path(f"v{version}.zip").write_bytes(response.content)
with zipfile.ZipFile(f"v{version}.zip", "r") as zip_ref:
    zip_ref.extractall(f"v{version}")
pro_settings = {}
for pro in glob(f"v{version}/*/plugin.json"):
    plugin_dir = path.dirname(pro)
    with open(pro, "r") as f:
        with suppress(Exception):
            pro_plugin = loads(f.read())
            pro_plugin["dir"] = plugin_dir
            core_settings[pro_plugin["name"]] = pro_plugin
            core_settings[pro_plugin["name"]]["is_pro"] = True

# Print plugins and their settings
for data in dict(sorted(core_settings.items())).values():
    pro_crown = ""
    if "is_pro" in data:
        pro_crown = " <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)\n"
    print(f"## {data['name']}{pro_crown}\n", file=doc)
    print(f"{stream_support(data['stream'])}\n", file=doc)

    # Check if README.md exists and use its content instead
    readme_content = get_readme_content(data["dir"])
    if readme_content:
        print(readme_content, file=doc)
    else:
        print(f"{data['description']}\n", file=doc)
        if data["settings"]:
            print(print_md_table(data["settings"]), file=doc)

# Remove zip file
Path(f"v{version}.zip").unlink()
# Remove folder using shutil
shutil.rmtree(f"v{version}")

doc.seek(0)
content = doc.read()
doc = StringIO(content.replace("\\|", "|"))
doc.seek(0)

Path("docs", "features.md").write_text(doc.read(), encoding="utf-8")
