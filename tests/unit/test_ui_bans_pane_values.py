"""Bans filter panes: values with & < > ' " , ; round-trip from the pane option to the filter."""

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from flask import Flask  # imported before the sys.modules patch so the route module shares this flask

REPO = Path(__file__).resolve().parents[2]
for path in ("src/ui", "src/common/utils", "src/common/db", "src/common/api"):
    sys.path.insert(0, str(REPO / path))

# app.dependencies builds the database at import time: replace it for the import only
deps = ModuleType("app.dependencies")
for name in ("BW_CONFIG", "BW_INSTANCES_UTILS", "DB", "DATA", "CONFIG_TASKS_EXECUTOR"):
    setattr(deps, name, MagicMock())
with patch.dict(sys.modules, {"app.dependencies": deps}):
    import app.models.instance as instance_module  # noqa: E402
    import app.routes.bans as bans_module  # noqa: E402

VALUES = ["x,y", "p;q", "a&b", "<s>", "'\"", "plain"]


def make_bans():
    bans = []
    for idx, value in enumerate(VALUES):
        bans.append(
            {
                "ip": f"10.0.0.{idx}",
                "country": "FR",
                "reason": value,
                "ban_scope": "service",
                "service": f"svc-{value}",
                "date": 1,
                "exp": 100,
                "permanent": False,
                "kind": "ban",
            }
        )
    return bans


class BansPaneValuesTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.bans = make_bans()
        patcher = patch.object(bans_module, "_collect_all_bans", lambda: self.bans)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fetch = bans_module.bans_fetch
        while hasattr(self.fetch, "__wrapped__"):
            self.fetch = self.fetch.__wrapped__

    def post(self, panes):
        form = {"draw": "1", "start": "0", "length": "100"}
        for field, values in panes.items():
            for idx, value in enumerate(values):
                form[f"searchPanes[{field}][{idx}]"] = value
        with self.app.test_request_context("/bans/fetch", method="POST", data=form):
            return self.fetch().get_json()

    def test_pane_values_are_raw_and_labels_escaped(self):
        options = self.post({})["searchPanes"]["options"]
        for field, prefix in (("reason", ""), ("service", "svc-")):
            by_value = {option["value"]: option["label"] for option in options[field]}
            self.assertEqual(set(by_value), {prefix + value for value in VALUES}, field)
            self.assertEqual(by_value[prefix + "<s>"], prefix + "&lt;s&gt;")

    def test_selecting_an_option_returns_its_row(self):
        options = self.post({})["searchPanes"]["options"]
        for field in ("reason", "service", "ip"):
            for option in options[field]:
                with self.subTest(field=field, value=option["value"]):
                    data = self.post({field: [option["value"]]})
                    self.assertEqual(data["recordsFiltered"], 1)
                    self.assertEqual(len(data["data"]), 1)

    def test_filtered_report_bans_use_the_encoded_wire_format(self):
        captured = {}

        def get_reports_query(**kwargs):
            captured.update(kwargs)
            return {"data": []}

        utils = MagicMock()
        utils.get_reports_query = get_reports_query
        form = {"searchPanes[url][0]": "x,y", "searchPanes[url][1]": "p;q", "searchPanes[user_agent][0]": "a&b"}
        with patch.object(bans_module, "BW_INSTANCES_UTILS", utils), patch.object(bans_module, "BW_CONFIG", None):
            bans_module._get_filtered_report_bans(form)
        self.assertEqual(
            instance_module.decode_search_panes(captured["search_panes"]),
            {"url": ["x,y", "p;q"], "user_agent": ["a&b"]},
        )


if __name__ == "__main__":
    unittest.main()
