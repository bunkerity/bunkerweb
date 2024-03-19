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


doc = StringIO()

print("# Settings\n", file=doc)
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
print(
    "As a general rule when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary"
    + " (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes` for example.\n",
    file=doc,
)
print(
    'When settings are considered as "multiple", it means that you can have multiple groups of settings for the same feature by adding numbers as suffix like `REVERSE_PROXY_URL_1=/subdir`,'
    + " `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.\n",
    file=doc,
)

# Print global settings
print("## Global settings\n", file=doc)
print(f"\n{stream_support('partial')}\n", file=doc)
with open("src/common/settings.json", "r") as f:
    print(print_md_table(loads(f.read())), file=doc)
    print(file=doc)

# Print core settings
print("## Core settings\n", file=doc)
core_settings = {}
for core in glob("src/common/core/*/plugin.json"):
    with open(core, "r") as f:
        with suppress(Exception):
            core_plugin = loads(f.read())
            if len(core_plugin["settings"]) > 0:
                core_settings[core_plugin["name"]] = core_plugin

for name, data in dict(sorted(core_settings.items())).items():
    print(f"### {data['name']}\n", file=doc)
    print(f"{stream_support(data['stream'])}\n", file=doc)
    print(f"{data['description']}\n", file=doc)
    print(print_md_table(data["settings"]), file=doc)


def pro_title(head_num: str, title: str) -> str:
    markdown_header = "##" if head_num == "2" else "###"
    return f"""
{markdown_header} {title}

<div style="display:flex; align-items:center">
    <h{head_num} data-custom-header id="{title.lower().replace(" ", "-")}">{title}</h{head_num}>

    <svg style="height:1.25rem; width:1.25rem; margin-top: 0.70rem; margin-left: 0.5rem"
            viewBox="0 0 48 46"
            fill="none"
            xmlns="http://www.w3.org/2000/svg">
        <path style="fill:#eab308"  d="M43.218 28.2327L43.6765 23.971C43.921 21.6973 44.0825 20.1957 43.9557 19.2497L44 19.25C46.071 19.25 47.75 17.5711 47.75 15.5C47.75 13.4289 46.071 11.75 44 11.75C41.929 11.75 40.25 13.4289 40.25 15.5C40.25 16.4366 40.5935 17.2931 41.1613 17.9503C40.346 18.4535 39.2805 19.515 37.6763 21.1128C36.4405 22.3438 35.8225 22.9593 35.1333 23.0548C34.7513 23.1075 34.3622 23.0532 34.0095 22.898C33.373 22.6175 32.9485 21.8567 32.0997 20.335L27.6262 12.3135C27.1025 11.3747 26.6642 10.5889 26.2692 9.95662C27.89 9.12967 29 7.44445 29 5.5C29 2.73857 26.7615 0.5 24 0.5C21.2385 0.5 19 2.73857 19 5.5C19 7.44445 20.11 9.12967 21.7308 9.95662C21.3358 10.589 20.8975 11.3746 20.3738 12.3135L15.9002 20.335C15.0514 21.8567 14.627 22.6175 13.9905 22.898C13.6379 23.0532 13.2487 23.1075 12.8668 23.0548C12.1774 22.9593 11.5595 22.3438 10.3238 21.1128C8.71968 19.515 7.6539 18.4535 6.83882 17.9503C7.4066 17.2931 7.75 16.4366 7.75 15.5C7.75 13.4289 6.07107 11.75 4 11.75C1.92893 11.75 0.25 13.4289 0.25 15.5C0.25 17.5711 1.92893 19.25 4 19.25L4.04428 19.2497C3.91755 20.1957 4.07905 21.6973 4.32362 23.971L4.782 28.2327C5.03645 30.5982 5.24802 32.849 5.50717 34.875H42.4928C42.752 32.849 42.9635 30.5982 43.218 28.2327Z" fill="#1C274C" />
        <path style="fill:#eab308"  d="M21.2803 45.5H26.7198C33.8098 45.5 37.3545 45.5 39.7198 43.383C40.7523 42.4588 41.4057 40.793 41.8775 38.625H6.1224C6.59413 40.793 7.24783 42.4588 8.2802 43.383C10.6454 45.5 14.1903 45.5 21.2803 45.5Z" fill="#1C274C" />
    </svg>
</div>
        """


# Read VERSION as file with permissions to read from src/
with open("src/VERSION", "r") as f:
    version = f.read().strip()

# Get zip file from https://assets.bunkerity.com/bw-pro/preview/v{version}
url = f"https://assets.bunkerity.com/bw-pro/preview/v{version}.zip"

# Download zip
response = requests.get(url)
response.raise_for_status()
Path(f"v{version}.zip").write_bytes(response.content)

# Unzip file
with zipfile.ZipFile(f"v{version}.zip", "r") as zip_ref:
    zip_ref.extractall(f"v{version}")

# Print pro settings
print("## Pro plugins", file=doc)
pro_settings = {}
for pro in glob(f"v{version}/*/plugin.json"):
    with open(pro, "r") as f:
        with suppress(Exception):
            pro_plugin = loads(f.read())
            if len(pro_plugin["settings"]) > 0:
                pro_settings[pro_plugin["name"]] = pro_plugin

for name, data in dict(sorted(pro_settings.items())).items():
    print(pro_title("3", data["name"]), file=doc)
    print(f"{stream_support(data['stream'])}\n", file=doc)
    print(f"{data['description']}\n", file=doc)
    print(print_md_table(data["settings"]), file=doc)

# Remove zip file
Path(f"v{version}.zip").unlink()
# Remove folder using shutil
shutil.rmtree(f"v{version}")

doc.seek(0)
content = doc.read()
doc = StringIO(content.replace("\\|", "|"))
doc.seek(0)

Path("docs", "settings.md").write_text(doc.read(), encoding="utf-8")
