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

DOCS_LANG = getenv("DOCS_LANG", "en")
LANG = DOCS_LANG.split("-")[0].lower()

I18N = {
    "en": {
        "features_title": "# Features",
        "intro_text": "This section contains the full list of settings supported by BunkerWeb. If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section of the documentation. Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.",
        "global_settings": "## Global settings",
        "stream_support": "STREAM support",
        # Table headers
        "header_setting": "Setting",
        "header_default": "Default",
        "header_context": "Context",
        "header_multiple": "Multiple",
        "header_description": "Description",
        # Yes/No
        "yes": "yes",
        "no": "no",
        # Badge
        "pro_badge": " (PRO)",
        # PRO plugins links
        "pro_yt_links": {
            "user_manager": {
                "url": "https://www.youtube-nocookie.com/embed/EIohiUf9Fg4",
                "title": "User Manager",
            },
            "loadbalancer": {
                "url": "https://www.youtube-nocookie.com/embed/cOVp0rAt5nw",
                "title": "Load Balancer",
            },
        },
    },
    "fr": {
        "features_title": "# Fonctionnalités",
        "intro_text": "Cette section contient la liste complète des paramètres pris en charge par BunkerWeb. Si vous n’êtes pas encore familier avec BunkerWeb, commencez par lire la section [concepts](concepts.md) de la documentation. Suivez ensuite les instructions de votre [intégration](integrations.md) pour appliquer les paramètres.",
        "global_settings": "## Paramètres globaux",
        "stream_support": "Prise en charge STREAM",
        # Table headers
        "header_setting": "Paramètre",
        "header_default": "Valeur par défaut",
        "header_context": "Contexte",
        "header_multiple": "Multiple",
        "header_description": "Description",
        # Yes/No
        "yes": "oui",
        "no": "non",
        # Badge
        "pro_badge": " (PRO)",
        # PRO plugins links
        "pro_yt_links": {
            "user_manager": {
                "url": "https://www.youtube-nocookie.com/embed/EIohiUf9Fg4",
                "title": "Gestionnaire d'utilisateurs",
            },
            "loadbalancer": {
                "url": "https://www.youtube-nocookie.com/embed/cOVp0rAt5nw",
                "title": "Équilibreur de charge",
            },
        },
    },
    "de": {
        "features_title": "# Funktionen",
        "intro_text": "Dieser Abschnitt enthält die vollständige Liste der von BunkerWeb unterstützten Einstellungen. Wenn Sie mit BunkerWeb noch nicht vertraut sind, lesen Sie zuerst den Abschnitt [Konzepte](concepts.md) der Dokumentation. Befolgen Sie anschließend die Anweisungen für Ihre [Integration](integrations.md), um die Einstellungen anzuwenden.",
        "global_settings": "## Globale Einstellungen",
        "stream_support": "STREAM-Unterstützung",
        "header_setting": "Einstellung",
        "header_default": "Standardwert",
        "header_context": "Kontext",
        "header_multiple": "Mehrfach",
        "header_description": "Beschreibung",
        "yes": "ja",
        "no": "nein",
        "pro_badge": " (PRO)",
        # PRO plugins links
        "pro_yt_links": {
            "user_manager": {
                "url": "https://www.youtube-nocookie.com/embed/EIohiUf9Fg4",
                "title": "Benutzer-Manager",
            },
            "loadbalancer": {
                "url": "https://www.youtube-nocookie.com/embed/cOVp0rAt5nw",
                "title": "Load Balancer",
            },
        },
    },
    "es": {
        "features_title": "# Características",
        "intro_text": "Esta sección contiene la lista completa de ajustes admitidos por BunkerWeb. Si aún no está familiarizado con BunkerWeb, primero lea la sección de [conceptos](concepts.md) de la documentación. Siga las instrucciones de su [integración](integrations.md) para aplicar los ajustes.",
        "global_settings": "## Configuración global",
        "stream_support": "Compatibilidad con STREAM",
        "header_setting": "Parámetro",
        "header_default": "Valor predeterminado",
        "header_context": "Contexto",
        "header_multiple": "Múltiple",
        "header_description": "Descripción",
        "yes": "sí",
        "no": "no",
        "pro_badge": " (PRO)",
        # PRO plugins links
        "pro_yt_links": {
            "user_manager": {
                "url": "https://www.youtube-nocookie.com/embed/EIohiUf9Fg4",
                "title": "Página del Administrador de usuarios",
            },
            "loadbalancer": {
                "url": "https://www.youtube-nocookie.com/embed/cOVp0rAt5nw",
                "title": "Balanceador de carga",
            },
        },
    },
    "zh": {
        "features_title": "# 功能",
        "intro_text": "本节包含 BunkerWeb 支持的完整设置列表。若尚未熟悉 BunkerWeb，建议先阅读文档中的[概念](concepts.md)部分。请根据您的[集成](integrations.md)说明应用相应的设置。",
        "global_settings": "## 全局设置",
        "stream_support": "STREAM 支持",
        "header_setting": "参数",
        "header_default": "默认值",
        "header_context": "上下文",
        "header_multiple": "可重复",
        "header_description": "描述",
        "yes": "是",
        "no": "否",
        "pro_badge": " (PRO)",
        # PRO plugins links
        "pro_yt_links": {
            "user_manager": {
                "url": "https://www.youtube-nocookie.com/embed/EIohiUf9Fg4",
                "title": "用户管理器页面",
            },
            "loadbalancer": {
                "url": "https://www.youtube-nocookie.com/embed/cOVp0rAt5nw",
                "title": "负载均衡器",
            },
        },
    },
}


def tr(key: str):
    base = I18N.get("en", {})
    return I18N.get(LANG, base).get(key, base.get(key, key))


def generate_docs_for_lang(lang: str):
    """Generate documentation for a specific language."""
    global LANG
    LANG = lang

    def tr_lang(key: str):
        base = I18N.get("en", {})
        return I18N.get(lang, base).get(key, base.get(key, key))

    doc = StringIO()

    print(f"{tr_lang('features_title')}\n", file=doc)
    print(f"{tr_lang('intro_text')}\n", file=doc)

    # Print global settings
    print(f"{tr_lang('global_settings')}\n", file=doc)
    print(f"\n{stream_support('partial')}\n", file=doc)
    # Check if README.md exists for global settings and use its content instead
    global_readme = get_global_readme_content(lang)
    if global_readme:
        print(global_readme, file=doc)
    else:
        with open("src/common/settings.json", "r") as f:
            print(print_md_table(loads(f.read()), tr_lang), file=doc)
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

    # Download and extract PRO plugins if not already done
    pro_zip_path = Path(f"v{version}.zip")
    pro_dir_path = Path(f"v{version}")

    if not pro_zip_path.exists():
        url = f"https://assets.bunkerity.com/bw-pro/preview/v{version}.zip"
        response = requests.get(url)
        response.raise_for_status()
        pro_zip_path.write_bytes(response.content)

    if not pro_dir_path.exists():
        with zipfile.ZipFile(pro_zip_path, "r") as zip_ref:
            zip_ref.extractall(pro_dir_path)

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
            pro_crown = (
                f" <img src='{'../' if lang != 'en' else ''}../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'>"
                + tr_lang("pro_badge")
                + "\n"
            )
        print(f"## {data['name']}{pro_crown}\n", file=doc)

        if "is_pro" in data and data["id"] in tr_lang("pro_yt_links"):
            yt_info = tr_lang("pro_yt_links")[data["id"]]
            print(
                f"<p align='center'><iframe style='display: block;' width='560' height='315' data-src='{yt_info['url']}' title='{yt_info['title']}' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>\n",
                file=doc,
            )

        print(f"{stream_support(data['stream'])}\n", file=doc)

        # Check if README.md exists and use its content instead
        readme_content = get_readme_content(data["dir"], lang)
        if readme_content:
            print(readme_content, file=doc)
        else:
            print(f"{data['description']}\n", file=doc)
            if data["settings"]:
                print(print_md_table(data["settings"], tr_lang), file=doc)

    # Finalize content
    doc.seek(0)
    content = doc.read()
    doc = StringIO(content.replace("\\|", "|"))
    doc.seek(0)

    # Ensure output directory per language
    out_dir = Path("docs") if lang == "en" else Path("docs", lang)
    out_dir.mkdir(parents=True, exist_ok=True)
    Path(out_dir, "features.md").write_text(doc.read(), encoding="utf-8")
    print(f"Generated features.md for language: {lang}")


def print_md_table(settings, tr_func=None) -> MarkdownTableWriter:
    writer = MarkdownTableWriter(
        headers=[
            tr("header_setting"),
            tr("header_default"),
            tr("header_context"),
            tr("header_multiple"),
            tr("header_description"),
        ],
        value_matrix=[
            [
                f"`{setting}`",
                "" if data["default"] == "" else f"`{data['default']}`",
                data["context"],
                tr("no") if "multiple" not in data else tr("yes"),
                data["help"],
            ]
            for setting, data in settings.items()
        ],
    )
    return writer


def stream_support(support) -> str:
    md = f"{tr('stream_support')} "
    if support == "no":
        md += ":x:"
    elif support == "yes":
        md += ":white_check_mark:"
    else:
        md += ":warning:"
    return md


def get_readme_content(plugin_dir, lang: str = "en"):
    """Read README.md content from plugin directory. Supports <lang>/README.md."""
    if lang:
        lang_path = Path(plugin_dir, f"README.{lang}.md")
        if lang_path.exists():
            with lang_path.open("r") as f:
                return f.read()
    readme_path = Path(plugin_dir, "README.md")
    if readme_path.exists():
        with readme_path.open("r") as f:
            return f.read()
    return None


def get_global_readme_content(lang: str = "en"):
    """Read README.md content for global settings with language support."""
    if lang:
        lang_path = Path("src/common", f"README.{lang}.md")
        if lang_path.exists():
            with lang_path.open("r") as f:
                return f.read()
    readme_path = Path("src/common/README.md")
    if readme_path.exists():
        with readme_path.open("r") as f:
            return f.read()
    return None


# Generate documentation for all available languages
available_languages = list(I18N.keys())

for lang in available_languages:
    print(f"Generating documentation for language: {lang}")
    generate_docs_for_lang(lang)

# Clean up downloaded files after generating all languages
if getenv("VERSION"):
    version = getenv("VERSION")
else:
    with open("src/VERSION", "r") as f:
        version = f.read().strip()

# Remove zip file and folder if they exist
pro_zip_path = Path(f"v{version}.zip")
pro_dir_path = Path(f"v{version}")

if pro_zip_path.exists():
    pro_zip_path.unlink()
if pro_dir_path.exists():
    shutil.rmtree(pro_dir_path)

print("Documentation generation complete for all languages!")
