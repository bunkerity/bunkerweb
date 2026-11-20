"""Reports filter panes: values with & < > ' " , ; reach the matcher unchanged."""

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[2]
for path in ("src/ui", "src/common/utils", "src/common/db", "src/common/api"):
    sys.path.insert(0, str(REPO / path))

# app.dependencies builds the database at import time: replace it for the import only
deps = ModuleType("app.dependencies")
for name in ("BW_CONFIG", "BW_INSTANCES_UTILS", "DB", "DATA", "CONFIG_TASKS_EXECUTOR"):
    setattr(deps, name, MagicMock())
with patch.dict(sys.modules, {"app.dependencies": deps}):
    import app.models.instance as instance_module  # noqa: E402
    import app.routes.reports as reports_module  # noqa: E402

VALUES = ["a&b", "x,y", "p;q", "it's", "<x>", 'say "hi"', "100%", "a+b", "plain"]


def legacy_join(panes):
    return ";".join(f"{field}:{','.join(values)}" for field, values in panes.items())


# the route's transport; before the fix the route joined the raw values itself
encode = getattr(instance_module, "encode_search_panes", legacy_join)


class PaneValuesTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(reports_module, "url_for", lambda endpoint, **kwargs: "/static/img/flags")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.utils = instance_module.InstancesUtils.__new__(instance_module.InstancesUtils)
        self.reports = [{"url": value, "user_agent": value} for value in VALUES]

    def test_option_value_is_raw_and_label_escaped(self):
        options = reports_module.build_search_panes_options({"url": {value: {"total": 1, "count": 1} for value in VALUES}})["url"]
        by_value = {option["value"]: option["label"] for option in options}
        self.assertEqual(set(by_value), set(VALUES))
        self.assertEqual(by_value["<x>"], "&lt;x&gt;")

    def test_server_name_option_value_is_raw(self):
        option = reports_module.build_search_panes_options({"server_name": {"a&b.example.com": {"total": 1, "count": 1}}})["server_name"][0]
        self.assertEqual(option["value"], "a&b.example.com")

    def test_each_value_matches_exactly_itself(self):
        for value in VALUES:
            with self.subTest(value=value):
                # the same string goes through the API call quoting in Instance.reports_query
                wire = encode({"url": [value]})
                kept = self.utils._apply_report_filters(self.reports, "", wire)
                self.assertEqual([report["url"] for report in kept], [value])

    def test_multiple_values_and_fields(self):
        wire = encode({"url": ["x,y", "p;q"], "user_agent": ["x,y"]})
        kept = self.utils._apply_report_filters(self.reports, "", wire)
        self.assertEqual([report["url"] for report in kept], ["x,y"])

    def test_wire_format_keeps_separators_unambiguous(self):
        wire = encode({"url": ["x,y", "p;q"]})
        self.assertEqual(wire.count(";"), 0)
        self.assertEqual(wire.count(","), 1)


if __name__ == "__main__":
    unittest.main()
