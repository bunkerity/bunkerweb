from io import StringIO
from json import loads
from glob import glob
from pathlib import Path
from pytablewriter import MarkdownTableWriter
import requests
import zipfile
import shutil
from contextlib import suppress
import os

def print_md_table(settings) -> str:
    writer = MarkdownTableWriter(
        headers=["Setting", "Default", "Context", "Multiple", "Description"],
        value_matrix=[
            [
                f"`{setting}`",
                f"`{data['default']}`" if data["default"] else "",
                data["context"],
                "yes" if "multiple" in data else "no",
                data["help"],
            ]
            for setting, data in settings.items()
        ],
    )
    output = StringIO()
    writer.stream = output
    writer.write_table()
    return output.getvalue()

def stream_support(support) -> str:
    symbols = {"no": ":x:", "yes": ":white_check_mark:"}
    return f"STREAM support {symbols.get(support, ':warning:')}"

def load_json_file(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as file:
        return loads(file.read())

def write_doc_header(doc: StringIO):
    doc.write("# Settings\n\n")
    doc.write(
        '!!! info "Settings generator tool"\n\n'
        "    To help you tune BunkerWeb, we have made an easy-to-use settings generator tool available at "
        "[config.bunkerweb.io](https://config.bunkerweb.io/?utm_campaign=self&utm_source=doc).\n\n"
    )
    doc.write(
        "This section contains the full list of settings supported by BunkerWeb. "
        "If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section. "
        "Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.\n\n"
    )
    doc.write(
        "As a general rule when multisite mode is enabled, prefix settings with the primary server name, e.g., "
        "`www.example.com_USE_ANTIBOT=captcha`.\n\n"
    )
    doc.write(
        'When settings are "multiple", use numbered suffixes, e.g., `REVERSE_PROXY_URL_1`, `REVERSE_PROXY_HOST_1`, etc.\n\n'
    )

def get_plugin_settings(folder_glob: str, is_pro=False) -> dict:
    plugins = {}
    for plugin_path in glob(folder_glob):
        with suppress(Exception):
            plugin_data = load_json_file(plugin_path)
            if plugin_data.get("settings"):
                plugin_data["is_pro"] = is_pro
                plugins[plugin_data["name"]] = plugin_data
    return plugins

def fetch_pro_plugins(version: str) -> str:
    url = f"https://assets.bunkerity.com/bw-pro/preview/v{version}.zip"
    zip_path = Path(f"v{version}.zip")
    extract_path = Path(f"v{version}")
    response = requests.get(url)
    response.raise_for_status()
    zip_path.write_bytes(response.content)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_path)
    return str(extract_path)

def main():
    doc = StringIO()
    write_doc_header(doc)

    doc.write("## Global settings\n\n")
    doc.write(f"{stream_support('partial')}\n\n")
    settings = load_json_file("src/common/settings.json")
    doc.write(print_md_table(settings) + "\n")

    core_plugins = get_plugin_settings("src/common/core/*/plugin.json")
    version = os.getenv("VERSION") or Path("src/VERSION").read_text().strip()
    pro_path = fetch_pro_plugins(version)
    pro_plugins = get_plugin_settings(f"{pro_path}/*/plugin.json", is_pro=True)

    all_plugins = {**core_plugins, **pro_plugins}

    for plugin_name in sorted(all_plugins):
        data = all_plugins[plugin_name]
        pro_label = " <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)" if data.get("is_pro") else ""
        doc.write(f"## {data['name']}{pro_label}\n\n")
        doc.write(f"{stream_support(data.get('stream', 'unknown'))}\n\n")
        doc.write(f"{data['description']}\n\n")
        if data.get("settings"):
            doc.write(print_md_table(data["settings"]) + "\n")

    # Cleanup
    shutil.rmtree(pro_path, ignore_errors=True)
    Path(f"v{version}.zip").unlink(missing_ok=True)

    # Final write
    doc.seek(0)
    final_content = doc.read().replace("\\|", "|")
    Path("docs", "settings.md").write_text(final_content, encoding="utf-8")

main()
