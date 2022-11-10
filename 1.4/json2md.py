#!/usr/bin/python3

from json import loads
from glob import glob
from pytablewriter import MarkdownTableWriter

def print_md_table(settings) :
    values = []
    for setting, data in settings.items() :
        values.append([
            "`" + setting + "`",
            "" if data["default"] == "" else "`" + data["default"] + "`",
            data["context"],
            "no" if not "multiple" in data else "yes",
            data["help"]
        ])
    writer = MarkdownTableWriter(
        headers=["Setting", "Default", "Context", "Multiple", "Description"],
        value_matrix=values
    )
    writer.write_table()
    print("")

print("# Settings\n")
print("!!! info \"Settings generator tool\"\n\n    To help you tune BunkerWeb, we have made an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io).\n")
print("This section contains the full list of settings supported by BunkerWeb. If you are not yet familiar with BunkerWeb, you should first read the [concepts](/1.4/concepts) section of the documentation. Please follow the instructions for your own [integration](/1.4/integrations) on how to apply the settings.\n")
print("As a general rule when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes` for example.\n")
print("When settings are considered as \"multiple\", it means that you can have multiple groups of settings for the same feature by adding numbers as suffix like `REVERSE_PROXY_URL_1=/subdir`, `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.\n")

# Print global settings
print("## Global settings\n")
with open("settings.json", "r") as f :
    print_md_table(loads(f.read()))

# Print core settings
print("## Core settings\n")
core_settings = {}
for core in glob("./core/*/plugin.json") :
    with open(core, "r") as f :
        core_plugin = loads(f.read())
        if len(core_plugin["settings"]) > 0 :
            core_settings[core_plugin["name"]] = core_plugin["settings"]
for name, settings in dict(sorted(core_settings.items())).items() :
    print("### " + name + "\n")
    print_md_table(settings)