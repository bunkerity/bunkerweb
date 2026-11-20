"""Static regression guard for the shared DataTable header ARIA refresh."""

from pathlib import Path
import re
import unittest


class DataTableAriaLanguageTest(unittest.TestCase):
    def test_header_sync_runs_after_initial_and_language_translations(self):
        source = (Path(__file__).resolve().parents[2] / "src/ui/app/static/js/dataTableInit.js").read_text()
        initial, changed = source.split('i18next.on("languageChanged", (lng) => {', 1)
        changed = changed.split("// Column visibility event", 1)[0]
        self.assertIn("syncHeaderAriaTitles();", changed, "language changes must refresh cached header names")
        self.assertLess(changed.index("const translation = t(key);"), changed.index("syncHeaderAriaTitles();"))
        self.assertLess(initial.index("applyTranslations();"), initial.index("syncHeaderAriaTitles();"))
        helper = re.search(r"const syncHeaderAriaTitles = \(\) => \{(.*?)\n  \};", initial, re.S)
        self.assertIsNotNone(helper)
        self.assertIn("markupHeaderColumns.has(column)", helper[1])
        self.assertNotIn("/</.test(column.ariaTitle", helper[1], "cached names are plain text after the first refresh")
        self.assertIn('find(".dt-column-title")', helper[1])
        self.assertIn('sortButton.attr("aria-label").replace(column.ariaTitle, () => text)', helper[1])
        self.assertIn("column.ariaTitle = text;", helper[1])


if __name__ == "__main__":
    unittest.main()
