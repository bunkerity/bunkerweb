"""A read-only POST is authorized by its exact endpoint or url_rule, never by a path suffix."""

import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from biscuit_auth import KeyPair
from flask import Blueprint, Flask
from jinja2 import DictLoader

REPO = Path(__file__).resolve().parents[2]
BISCUIT_FILE = REPO / "src" / "ui" / "app" / "models" / "biscuit.py"


def load_biscuit_module():
    def stub(name, **attrs):
        module = ModuleType(name)
        module.__dict__.update(attrs)
        return module

    stubs = {
        "app": stub("app", __path__=[]),
        "app.routes": stub("app.routes", __path__=[]),
        "app.routes.logout": stub("app.routes.logout", logout_page=lambda: "logout"),
        "app.utils": stub("app.utils", BISCUIT_PRIVATE_KEY_FILE=Path("/nonexistent"), is_static_path=lambda path, *extra: path.startswith("/static/")),
        "common_utils": stub("common_utils", get_version=lambda: "test"),
    }
    with patch.dict(sys.modules, stubs):
        spec = spec_from_file_location("biscuit_under_test", BISCUIT_FILE)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


biscuit = load_biscuit_module()


class ReadOnlyPostTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        key_pair = KeyPair()
        public_key_path = Path(cls.tmp.name) / "public"
        public_key_path.write_text(repr(key_pair.public_key))

        app = Flask("biscuit_test")
        app.secret_key = "test"
        app.config.update(BISCUIT_PUBLIC_KEY_PATH=str(public_key_path), CHECK_PRIVATE_IP=True)
        app.jinja_loader = DictLoader({"unauthorized.html": "denied {{ error_code }}"})

        cls.executed = []

        def view(name):
            def handler(**kwargs):
                cls.executed.append(name)
                return name

            handler.__name__ = name
            return handler

        for name in ("home", "logout"):
            blueprint = Blueprint(name, __name__)
            blueprint.add_url_rule(f"/{name}", f"{name}_page", view(f"{name}_page"))
            app.register_blueprint(blueprint)

        reports = Blueprint("reports", __name__)
        reports.add_url_rule("/reports/data", "report_data_fetch", view("report_data_fetch"), methods=["POST"])
        app.register_blueprint(reports)
        app.add_url_rule("/configs/<service>/<config_type>/<name>", "configs_edit", view("configs_edit"), methods=["POST"])

        biscuit.BiscuitMiddleware(app)
        cls.app = app
        cls.factory = biscuit.BiscuitTokenFactory(key_pair.private_key)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        type(self).executed.clear()

    def post(self, role, path):
        with self.app.test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            token = self.factory.create_token_for_role(role, role).to_base64()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["biscuit_token"] = token
        return client.post(path, environ_base={"REMOTE_ADDR": "127.0.0.1"})

    def test_reader_cannot_write_through_a_suffix_lookalike(self):
        response = self.post("reader", "/configs/global/reports/data")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("configs_edit", self.executed)

    def test_reader_keeps_the_real_read_only_post(self):
        response = self.post("reader", "/reports/data")
        self.assertEqual(response.status_code, 200)
        self.assertIn("report_data_fetch", self.executed)

    def test_writer_still_writes_to_the_configs_route(self):
        for role in ("writer", "admin"):
            with self.subTest(role=role):
                self.executed.clear()
                response = self.post(role, "/configs/global/reports/data")
                self.assertEqual(response.status_code, 200)
                self.assertIn("configs_edit", self.executed)

    def test_resolve_operation(self):
        resolve = biscuit.resolve_operation
        self.assertEqual(resolve("POST", "/configs/global/reports/data", "configs.configs_edit", "/configs/<service>/<config_type>/<name>"), "write")
        self.assertEqual(resolve("POST", "/configs/global/bans/fetch", None, None), "write")
        self.assertEqual(resolve("POST", "/reports/data", "reports.report_data_fetch", "/reports/data"), "read")
        self.assertEqual(resolve("POST", "/reports//fetch/", None, "/reports//fetch/"), "read")
        self.assertEqual(resolve("POST", "/bans/fetch", "bans.bans_fetch", "/bans/fetch"), "read")
        self.assertEqual(resolve("GET", "/anything", None, None), "read")
        self.assertEqual(resolve("POST", "/anything", None, None), "write")


if __name__ == "__main__":
    unittest.main()
