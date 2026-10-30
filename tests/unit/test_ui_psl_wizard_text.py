"""The setup wizard switch LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES: enabled skips the Public Suffix List check.

The label and tooltip must say so in every locale and in the template fallback.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCALES = sorted((ROOT / "src/ui/app/static/locales").glob("*.json"))
KEY = "lets_encrypt_disable_public_suffixes"


def load(name):
    return json.loads((ROOT / "src/ui/app/static/locales" / name).read_text(encoding="utf-8"))


class PslWizardText(unittest.TestCase):
    def test_every_locale_has_both_values(self):
        self.assertEqual(len(LOCALES), 19)
        for path in LOCALES:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["form"]["label"].get(KEY, "").strip(), path.name)
            self.assertTrue(data["tooltip"].get(KEY, "").strip(), path.name)

    def test_english_tooltip_says_check_is_skipped_when_enabled(self):
        tooltip = load("en.json")["tooltip"][KEY].lower()
        self.assertIn("not checked", tooltip)
        self.assertNotIn("recommended", tooltip)
        self.assertFalse(tooltip.startswith("disable certificate requests"))

    def test_template_fallback_matches_english(self):
        html = (ROOT / "src/ui/app/templates/setup.html").read_text(encoding="utf-8")
        en = load("en.json")
        self.assertIn(en["tooltip"][KEY], html)
        self.assertIn(en["form"]["label"][KEY], html)


if __name__ == "__main__":
    unittest.main()
