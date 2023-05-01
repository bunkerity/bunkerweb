#!/usr/bin/python3

from io import StringIO
from json import loads
from glob import glob
from pytablewriter import MarkdownTableWriter


def print_md_table(settings) -> MarkdownTableWriter:
    writer = MarkdownTableWriter(
        headers=["Setting", "Default", "Context", "Multiple", "Description"],
        value_matrix=[
            [
                f"`{setting}`",
                "" if data["default"] == "" else f"`{data['default']}`",
                data["context"],
                "no" if not "multiple" in data else "yes",
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
    '!!! info "Settings generator tool"\n\n    To help you tune BunkerWeb, we have made an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io).\n',
    file=doc,
)
print(
    "This section contains the full list of settings supported by BunkerWeb. If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section of the documentation. Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.\n",
    file=doc,
)
print(
    "As a general rule when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes` for example.\n",
    file=doc,
)
print(
    'When settings are considered as "multiple", it means that you can have multiple groups of settings for the same feature by adding numbers as suffix like `REVERSE_PROXY_URL_1=/subdir`, `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.\n',
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
        core_plugin = loads(f.read())
        if len(core_plugin["settings"]) > 0:
            core_settings[core_plugin["name"]] = core_plugin

for name, data in dict(sorted(core_settings.items())).items():
    print(f"### {data['name']}\n", file=doc)
    print(f"{stream_support(data['stream'])}\n", file=doc)
    print(f"{data['description']}\n", file=doc)
    print(print_md_table(data["settings"]), file=doc)

doc.seek(0)
content = doc.read()
doc = StringIO(content.replace("\\|", "|"))
doc.seek(0)

with open("docs/settings.md", "w") as f:
    f.write(doc.read())
