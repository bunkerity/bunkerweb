import unittest
from importlib import import_module
from os import environ
from pathlib import Path

from jinja2 import Template

REPO_ROOT = Path(__file__).resolve().parents[2]
# MODSEC_CRS_TEMPLATE lets a reviewer point the test at a copy of the template from another revision.
TEMPLATE_PATH = Path(environ.get("MODSEC_CRS_TEMPLATE", REPO_ROOT / "src/common/core/ui/confs/http/ui.modsec-crs"))


def has_variable(all_vars: dict, variable: str, value: str) -> bool:
    """Mirror of Templator.has_variable (src/common/gen/Templator.py)."""
    if all_vars.get(variable) == value:
        return True
    if all_vars.get("MULTISITE", "no") == "yes":
        return any(all_vars.get(f"{name}_{variable}") == value for name in all_vars.get("SERVER_NAME", "").split())
    return False


def render(services: dict) -> str:
    """services maps a service id to (USE_UI, SERVER_NAME)."""
    all_vars = {"MULTISITE": "yes", "SERVER_NAME": " ".join(services)}
    for service_id, (use_ui, names) in services.items():
        all_vars[f"{service_id}_USE_UI"] = use_ui
        all_vars[f"{service_id}_SERVER_NAME"] = names
    return Template(TEMPLATE_PATH.read_text()).render(
        all=all_vars, SERVER_NAME=all_vars["SERVER_NAME"], MULTISITE="yes", has_variable=has_variable, **{"import": import_module}
    )


def host_rules(rendered: str) -> list:
    return [line for line in rendered.splitlines() if line.startswith("SecRule REQUEST_HEADERS:Host")]


class UiModsecCrsHostsTest(unittest.TestCase):
    def test_every_server_name_of_a_ui_service_is_listed(self):
        rules = host_rules(render({"app.example.com": ("yes", "app.example.com UI.Example.com"), "other.com": ("no", "other.com")}))

        self.assertTrue(rules)
        for rule in rules:
            self.assertIn("app\\.example\\.com|ui\\.example\\.com", rule)
            self.assertNotIn("other", rule)

    def test_ip_names_go_to_the_ip_rule_only(self):
        rules = host_rules(render({"app.example.com": ("yes", "app.example.com 10.0.0.5")}))

        ip_rules = [rule for rule in rules if "10\\.0\\.0\\.5" in rule]
        self.assertEqual(len(ip_rules), 1)
        self.assertNotIn("app", ip_rules[0])
        for rule in rules:
            if rule not in ip_rules:
                self.assertIn("app\\.example\\.com", rule)
                self.assertNotIn("10", rule)

    def test_non_ui_service_names_are_ignored(self):
        self.assertEqual(host_rules(render({"other.com": ("no", "other.com www.other.com")})), [])


if __name__ == "__main__":
    unittest.main()
