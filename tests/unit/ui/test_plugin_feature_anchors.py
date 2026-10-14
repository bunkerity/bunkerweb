"""Plugin documentation links must target the published feature heading."""

from pathlib import Path
from html import unescape

import pytest
from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader


@pytest.mark.parametrize(
    "plugin_id,name,kind,target",
    [
        ("general", "General", "core", "/features/?utm_campaign=self&amp;utm_source=ui#global-settings"),
        ("letsencrypt", "Let's Encrypt", "core", "/features/?utm_campaign=self&amp;utm_source=ui#lets-encrypt"),
        ("securitytxt", "Security.txt", "core", "/features/?utm_campaign=self&amp;utm_source=ui#securitytxt"),
        ("customcert", "Custom SSL certificate", "core", "/features/?utm_campaign=self&amp;utm_source=ui#custom-ssl-certificate"),
        ("user-manager", "User Manager", "pro", "/features/?utm_campaign=self&amp;utm_source=ui#user-manager-pro"),
        ("example", "External Example", "external", "/plugins/?utm_campaign=self&amp;utm_source=ui"),
    ],
)
def test_plugin_feature_anchor(plugin_id, name, kind, target):
    templates = Path(__file__).resolve().parents[3] / "src/ui/app/templates"
    env = Environment(
        loader=ChoiceLoader([DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}), FileSystemLoader(templates)]),
        autoescape=True,
        undefined=ChainableUndefined,
    )
    env.globals.update(url_for=lambda *args, **kwargs: "/plugins", _=lambda key: key)
    rendered = env.get_template("plugin_page.html").render(
        plugin={"id": plugin_id, "name": name, "type": kind, "version": "1"},
        plugin_types={kind: {}},
        plugin_text=lambda _id, _key, fallback: fallback,
        bw_version="1.7.0~alpha",
        language="fr",
        pro_diamond_url="/pro.svg",
        is_used=False,
    )
    assert unescape(f'href="https://docs.bunkerweb.io/latest/fr{target}"') in unescape(rendered)
