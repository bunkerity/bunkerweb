"""Tests for the secret masking of the /support/config export (src/ui/app/routes/support.py)."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src/ui"), str(REPO_ROOT / "src/common/utils"), str(REPO_ROOT / "src/common/db")]

REDACTED = "[REDACTED]"
SERVICES = "www.example.com my_shop.example.org"

PLUGIN_SETTINGS = {
    "SERVER_NAME": {"type": "text", "context": "multisite"},
    "USE_ANTIBOT": {"type": "select", "context": "multisite"},
    "AUTHBASIC_PASSWORD": {"type": "password", "context": "multisite"},
    "REDIS_PASSWORD": {"type": "password", "context": "global"},
    "TEMPLATE_PASSWORD": {"type": "password", "context": "global"},
    "REDIS_PASSWORD_DEFAULT": {"type": "password", "context": "global"},
    "PRO_TOKEN_SECRET": {"type": "password", "context": "multisite"},
    "REVERSE_PROXY_HOST": {"type": "text", "context": "multisite"},
    "REVERSE_PROXY_PASSWORD": {"type": "password", "context": "multisite"},
    "DATABASE_URI": {"type": "text", "context": "global"},
    "DATABASE_URI_READONLY": {"type": "text", "context": "global"},
    "AUTH_BASIC_PASSWORD": {"type": "password", "context": "multisite"},
    "PASSWORD_1": {"type": "text", "context": "multisite"},
    "X_PASSWORD": {"type": "password", "context": "multisite"},
    "SECRET_DATABASE_URI": {"type": "password", "context": "global"},
}


def entry(value, method="ui", is_global=True):
    return {"value": value, "global": is_global, "method": method, "default": "", "template": None}


def full_config():
    return {
        "SERVER_NAME": entry(SERVICES),
        "USE_ANTIBOT": entry("captcha"),
        "REDIS_PASSWORD": entry("redis-secret"),
        "AUTHBASIC_PASSWORD": entry("global-secret"),
        "PRO_TOKEN_SECRET": entry(""),
        "www.example.com_AUTHBASIC_PASSWORD": entry("www-secret", is_global=False),
        "my_shop.example.org_AUTHBASIC_PASSWORD": entry("shop-secret", is_global=False),
        "my_shop.example.org_REVERSE_PROXY_PASSWORD_1": entry("rp-secret-1", is_global=False),
        "REVERSE_PROXY_PASSWORD_2": entry("rp-secret-2"),
        "REVERSE_PROXY_HOST_1": entry("http://backend"),
        "DATABASE_URI": entry("mariadb+pymysql://bunkerweb:s3cr@t!@db:3306/db"),
        "DATABASE_URI_READONLY": entry("postgresql://reader@db/db"),
        "TEMPLATE_PASSWORD": {**entry("", method="default"), "default": "tpl-secret", "template": "t"},
        "AUTH_BASIC_PASSWORD_1": entry("ext-secret"),
        "www.example.com_AUTH_BASIC_PASSWORD_1": entry("ext-svc-secret", is_global=False),
        "REDIS_PASSWORD_DEFAULT": {**entry("v-secret"), "default": "d-secret"},
        "svc_X_PASSWORD_1": entry("collision-secret", is_global=False),
        "SECRET_DATABASE_URI": entry("postgresql://u:both-secret@db/main"),
    }


def service_config():
    return {
        "AUTHBASIC_PASSWORD": entry("shop-secret", is_global=False),
        "REVERSE_PROXY_PASSWORD_1": entry("rp-secret-1", is_global=False),
        "REVERSE_PROXY_HOST_1": entry("http://backend", is_global=False),
        "USE_ANTIBOT": entry("captcha", is_global=False),
        "AUTH_BASIC_PASSWORD_1": entry("ext-svc-secret", is_global=False),
        "X_PASSWORD_1": entry("collision-secret", is_global=False),
    }


class SupportConfigMaskTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        from flask_login import LoginManager, UserMixin

        dependencies = ModuleType("app.dependencies")
        config = MagicMock()
        config.get_config.return_value = {"SERVER_NAME": SERVICES}
        config.get_plugins_settings.return_value = PLUGIN_SETTINGS
        db = MagicMock()
        db.get_config.side_effect = lambda **kwargs: service_config() if kwargs.get("service") else full_config()
        dependencies.BW_CONFIG, dependencies.DB = config, db
        dependencies.CORE_PLUGINS_PATH = dependencies.EXTERNAL_PLUGINS_PATH = dependencies.PRO_PLUGINS_PATH = Path("/nonexistent")
        cls.previous = sys.modules.get("app.dependencies")
        sys.modules["app.dependencies"] = dependencies
        sys.modules.pop("app.routes.support", None)
        from app.routes.support import support

        class User(UserMixin):
            def __init__(self, name, admin):
                self.id, self.admin = name, admin

        users = {"admin": User("admin", True), "reader": User("reader", False)}
        app = Flask(__name__)
        app.secret_key = "test"
        manager = LoginManager(app)

        @manager.request_loader
        def load(request):
            return users.get(request.headers.get("X-User", ""))

        cls.module = sys.modules["app.routes.support"]
        app.register_blueprint(support)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("app.routes.support", None)
        if cls.previous is None:
            sys.modules.pop("app.dependencies", None)
        else:
            sys.modules["app.dependencies"] = cls.previous

    def export(self, query="", user="admin"):
        response = self.client.get(f"/support/config{query}", headers={"X-User": user})
        self.assertEqual(response.status_code, 200)
        return json.loads(response.data)

    def test_masked_by_default(self):
        data = self.export()
        for key in (
            "REDIS_PASSWORD",
            "AUTHBASIC_PASSWORD",
            "www.example.com_AUTHBASIC_PASSWORD",
            "REVERSE_PROXY_PASSWORD_2",
        ):
            self.assertEqual(data[key]["value"], REDACTED, key)
            self.assertEqual(data[key]["method"], "ui", key)

    def test_service_name_with_underscore(self):
        data = self.export()
        self.assertEqual(data["my_shop.example.org_AUTHBASIC_PASSWORD"]["value"], REDACTED)

    def test_multiple_suffix_with_service_prefix(self):
        data = self.export()
        self.assertEqual(data["my_shop.example.org_REVERSE_PROXY_PASSWORD_1"]["value"], REDACTED)

    def test_non_password_settings_untouched(self):
        data = self.export()
        self.assertEqual(data["USE_ANTIBOT"]["value"], "captcha")
        self.assertEqual(data["REVERSE_PROXY_HOST_1"]["value"], "http://backend")
        self.assertEqual(data["SERVER_NAME"]["value"], SERVICES)

    def test_empty_values_stay_empty(self):
        self.assertEqual(self.export()["PRO_TOKEN_SECRET"]["value"], "")

    def test_database_uri_masks_only_the_password(self):
        data = self.export()
        self.assertEqual(data["DATABASE_URI"]["value"], f"mariadb+pymysql://bunkerweb:{REDACTED}@db:3306/db")
        self.assertEqual(data["DATABASE_URI_READONLY"]["value"], "postgresql://reader@db/db")

    def test_per_service_export_is_masked(self):
        data = self.export("?service=my_shop.example.org")
        self.assertEqual(data["AUTHBASIC_PASSWORD"]["value"], REDACTED)
        self.assertEqual(data["REVERSE_PROXY_PASSWORD_1"]["value"], REDACTED)
        self.assertEqual(data["REVERSE_PROXY_HOST_1"]["value"], "http://backend")

    def test_admin_can_opt_out(self):
        data = self.export("?mask_passwords=no")
        self.assertEqual(data["REDIS_PASSWORD"]["value"], "redis-secret")
        self.assertEqual(data["my_shop.example.org_REVERSE_PROXY_PASSWORD_1"]["value"], "rp-secret-1")
        self.assertEqual(data["DATABASE_URI"]["value"], "mariadb+pymysql://bunkerweb:s3cr@t!@db:3306/db")

    def test_admin_can_opt_out_per_service(self):
        data = self.export("?service=my_shop.example.org&mask_passwords=no")
        self.assertEqual(data["AUTHBASIC_PASSWORD"]["value"], "shop-secret")

    def test_non_admin_cannot_opt_out(self):
        data = self.export("?mask_passwords=no", user="reader")
        self.assertEqual(data["REDIS_PASSWORD"]["value"], REDACTED)
        self.assertEqual(data["DATABASE_URI"]["value"], f"mariadb+pymysql://bunkerweb:{REDACTED}@db:3306/db")
        data = self.export("?service=my_shop.example.org&mask_passwords=no", user="reader")
        self.assertEqual(data["AUTHBASIC_PASSWORD"]["value"], REDACTED)

    def test_other_mask_values_keep_masking(self):
        self.assertEqual(self.export("?mask_passwords=yes")["REDIS_PASSWORD"]["value"], REDACTED)
        self.assertEqual(self.export("?mask_passwords=")["REDIS_PASSWORD"]["value"], REDACTED)

    def test_default_is_masked_independently(self):
        data = self.export()
        self.assertEqual(data["TEMPLATE_PASSWORD"]["value"], "")
        self.assertEqual(data["TEMPLATE_PASSWORD"]["default"], REDACTED)
        self.assertEqual(data["REDIS_PASSWORD_DEFAULT"]["value"], REDACTED)
        self.assertEqual(data["REDIS_PASSWORD_DEFAULT"]["default"], REDACTED)
        self.assertEqual(data["REDIS_PASSWORD"]["default"], "")

    def test_shorter_setting_name_cannot_shadow_the_password(self):
        data = self.export()
        self.assertEqual(data["AUTH_BASIC_PASSWORD_1"]["value"], REDACTED)
        self.assertEqual(data["www.example.com_AUTH_BASIC_PASSWORD_1"]["value"], REDACTED)
        self.assertEqual(self.export("?service=www.example.com")["AUTH_BASIC_PASSWORD_1"]["value"], REDACTED)

    def test_setting_names_collects_every_candidate(self):
        names = {"PASSWORD_1", "AUTH_BASIC_PASSWORD", "FOO_1", "FOO"}
        resolve = self.module.setting_names
        self.assertEqual(resolve("AUTH_BASIC_PASSWORD_1", names), {"AUTH_BASIC_PASSWORD", "PASSWORD_1"})
        self.assertEqual(resolve("svc_AUTH_BASIC_PASSWORD_1", names), {"AUTH_BASIC_PASSWORD", "PASSWORD_1"})
        self.assertEqual(resolve("FOO_1", names), {"FOO_1", "FOO"})
        self.assertEqual(resolve("a.b_FOO_2", names), {"FOO"})
        self.assertEqual(resolve("PASSWORD_1", names), {"PASSWORD_1"})
        self.assertEqual(resolve("NOPE", names), set())

    def test_equal_length_collision_is_masked(self):
        # Same length candidates (X_PASSWORD from the stripped key, PASSWORD_1 from the raw key) must not depend on set order
        self.assertEqual(self.export()["svc_X_PASSWORD_1"]["value"], REDACTED)
        self.assertEqual(self.export("?service=www.example.com")["X_PASSWORD_1"]["value"], REDACTED)

    def test_equal_length_collision_for_every_hash_seed(self):
        for seed in range(11):
            result = subprocess.run(
                [sys.executable, __file__, "SupportConfigMaskTest.test_equal_length_collision_is_masked"],
                env={**os.environ, "PYTHONHASHSEED": str(seed)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"seed {seed}: {result.stderr}")

    def test_uri_and_password_match_redacts_fully(self):
        self.assertEqual(self.export()["SECRET_DATABASE_URI"]["value"], REDACTED)

    def test_database_uri_forms(self):
        cases = {
            "postgresql+psycopg://user@realm:secret@db/main": f"postgresql+psycopg://user@realm:{REDACTED}@db/main",
            "postgresql://u:p@ss@db:5432/main": f"postgresql://u:{REDACTED}@db:5432/main",
            "postgresql://u:pa:ss@db/main": f"postgresql://u:{REDACTED}@db/main",
            "postgresql://u:pa/ss@db/main": f"postgresql://u:{REDACTED}@db/main",
            "postgresql://u:secret@db/main?application_name=ops@company": f"postgresql://u:{REDACTED}@db/main?application_name=ops@company",
            "postgresql://db/main?application_name=ops@company": "postgresql://db/main?application_name=ops@company",
            "postgresql+psycopg://u:sentinel?secret@db/main": f"postgresql+psycopg://u:{REDACTED}@db/main",
            "postgresql+psycopg://u:sentinel#secret@db/main": f"postgresql+psycopg://u:{REDACTED}@db/main",
            "postgresql://u:secret@db/main#frag@x": f"postgresql://u:{REDACTED}@db/main#frag@x",
            "postgresql://user@db/main": "postgresql://user@db/main",
            "postgresql://user:@db/main": "postgresql://user:@db/main",
            "postgresql://db:5432/main": "postgresql://db:5432/main",
            "sqlite:////var/lib/bunkerweb/db.sqlite3": "sqlite:////var/lib/bunkerweb/db.sqlite3",
            "sqlite:///C:/data/a@b.db": "sqlite:///C:/data/a@b.db",
            "sqlite:////data/a:b@c.db": "sqlite:////data/a:b@c.db",
        }
        for source, expected in cases.items():
            config = self.module.mask_config({"DATABASE_URI": entry(source), "DATABASE_URI_READONLY": {**entry(""), "default": source}})
            self.assertEqual(config["DATABASE_URI"]["value"], expected, source)
            self.assertEqual(config["DATABASE_URI_READONLY"]["default"], expected, source)
            self.assertEqual(config["DATABASE_URI_READONLY"]["value"], "")


class TemplateAndLocalesTest(unittest.TestCase):
    def test_checkbox_is_admin_only_and_links_are_tagged(self):
        template = REPO_ROOT.joinpath("src/ui/app/templates/support.html").read_text(encoding="utf-8")
        start = template.index('id="mask-passwords"')
        before = template.rindex("{% if current_user.admin %}", 0, start)
        self.assertNotIn("{% endif %}", template[before:start])
        self.assertEqual(template.count("support-config-link"), 2)

    def test_locale_keys_exist_everywhere(self):
        locales = sorted(REPO_ROOT.joinpath("src/ui/app/static/locales").glob("*.json"))
        self.assertEqual(len(locales), 19)
        for path in locales:
            card = json.loads(path.read_text(encoding="utf-8"))["support"]["card"]["extract_config"]
            for key in ("hide_passwords", "hide_passwords_warning"):
                self.assertTrue(card.get(key), f"{path.name} lacks {key}")
            self.assertNotIn("\u2014", card["hide_passwords_warning"], path.name)


if __name__ == "__main__":
    unittest.main()
