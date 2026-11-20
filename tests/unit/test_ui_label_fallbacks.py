"""Server-rendered fallbacks must equal the English translation, and the home map must not call an undefined control."""

import json
import re
import unittest
from pathlib import Path

from jinja2 import Environment

UI = Path(__file__).resolve().parents[2] / "src" / "ui" / "app"
LOCALES = sorted((UI / "static" / "locales").glob("*.json"))
EN = json.loads((UI / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
TEMPLATES = UI / "templates"


def read(rel: str) -> str:
    return (TEMPLATES / rel).read_text(encoding="utf-8")


class LabelFallbacks(unittest.TestCase):
    def test_home_js_has_no_undefined_info_control(self):
        js = (UI / "static" / "js" / "pages" / "home.js").read_text(encoding="utf-8")
        assert not re.search(r"\binfo\.update\(", js)

    def test_templates_delete_modal_has_own_wording(self):
        html = read("templates.html")
        js = (UI / "static" / "js" / "pages" / "templates.js").read_text(encoding="utf-8")
        assert "modal.body.delete_confirmation_alert" not in html
        assert "modal.body.delete_confirmation_alert" not in js
        for key in ("confirm_templates_deletion_alert", "confirm_templates_deletion_alert_plural"):
            assert "template" in EN["modal"]["body"][key]
            assert key in js

    def test_templates_delete_keys_in_every_locale(self):
        for locale in LOCALES:
            with self.subTest(locale=locale.stem):
                body = json.loads(locale.read_text(encoding="utf-8"))["modal"]["body"]
                assert body["confirm_templates_deletion_alert"] and body["confirm_templates_deletion_alert_plural"]

    def test_jobs_interval_fallback_matches_en(self):
        html = read("jobs.html")
        tpl = Environment().from_string(re.search(r"<span data-i18n=\"interval\.[^>]*>.*?</span>", html).group(0))
        for every, label in EN["interval"].items():
            out = tpl.render(job_data={"every": every})
            assert f">{label}<" in out, (every, out)

    def test_plugin_type_fallback_matches_en(self):
        html = read("plugins.html")
        tpl = Environment().from_string(re.search(r"<span data-i18n=\"plugin\.type\.[^>]*>.*?</span>", html).group(0))
        for ptype, label in EN["plugin"]["type"].items():
            if ptype == "all":
                continue
            out = tpl.render(plugin_data={"type": ptype})
            assert f">{label}<" in out, (ptype, out)

    def test_status_and_pro_fallbacks_match_en(self):
        easy = " ".join(read("models/plugins_settings_easy.html").split())
        assert ' This service currently uses the "{{ selected_template }}" template which is managed via "{{ template_method }}". ' in easy
        pro = " ".join(read("pro.html").split())
        assert "{{ online_services }} Online Service(s) / {{ pro_services }} PRO Service(s)" in pro
        assert "{{ draft_services }} Draft service(s)" in pro

    def test_breadcrumb_fallback_uses_english_labels(self):
        html = read("breadcrumb.html")
        names = {m.group(1) for m in re.finditer(r'"(\w+)": "([^"]+)"', html)}
        assert {"crowdsec", "global_config", "more"} <= names
        for key, label in re.findall(r'"(\w+)": "([^"]+)"', html):
            assert EN["breadcrumb"][key].strip() == label

    def test_breadcrumb_renders_english_text_for_i18n_segments(self):
        from types import SimpleNamespace

        tpl = Environment().from_string(read("breadcrumb.html"))
        endpoints = {"home", "bans", "global-settings", "crowdsec", "plugins", "pro"}

        def url_for(name, **kwargs):
            return "/" + name if name in endpoints else "#"

        for path, endpoint, expected in (
            ("/home", "home", "Home"),
            ("/bans", "bans", "Bans"),
            ("/global-settings", "global-settings", "Global Settings"),
            ("/crowdsec", "crowdsec", "CrowdSec"),
            ("/pro", "pro", "Pro"),
        ):
            with self.subTest(path=path):
                out = tpl.render(request=SimpleNamespace(path=path), url_for=url_for, current_endpoint=endpoint, extra_pages=[], breadcrumbs_url="/" + endpoint)
                m = re.search(r'data-i18n="breadcrumb\.(\w+)"[^>]*>([^<]*)</a>', out)
                assert m, out
                assert m.group(2) == expected == EN["breadcrumb"][m.group(1)].strip(), out


if __name__ == "__main__":
    unittest.main()
