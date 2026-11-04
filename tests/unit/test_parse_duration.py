from pathlib import Path
from sys import path as sys_path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys_path.insert(0, str(ROOT / "src/common/utils"))

from common_utils import parse_duration, parse_duration_int  # type: ignore  # noqa: E402


class ParseDurationTest(unittest.TestCase):
    def test_duration_suffixes_and_default_units(self):
        self.assertEqual(parse_duration("90", "s"), 90)
        self.assertEqual(parse_duration("2m", "s"), 120)
        self.assertEqual(parse_duration("2s", "ms"), 2000)
        self.assertEqual(parse_duration("500ms", "s"), 0.5)
        self.assertEqual(parse_duration("1w", "d"), 7)
        self.assertEqual(parse_duration("1M", "d"), 30)
        self.assertEqual(parse_duration("0", "s"), 0)

    def test_fractional_durations_preserve_non_whole_results(self):
        self.assertEqual(parse_duration("0.25", "s"), 0.25)
        self.assertEqual(parse_duration("1500ms", "s"), 1.5)
        self.assertEqual(parse_duration("250ms", "s"), 0.25)
        self.assertEqual(parse_duration("1y", "d"), 365)

    def test_integer_durations_never_collapse_to_zero(self):
        self.assertEqual(parse_duration_int("500ms", "s"), 1)
        self.assertEqual(parse_duration_int("1ms", "s"), 1)
        self.assertEqual(parse_duration_int("1500ms", "s"), 1)
        self.assertEqual(parse_duration_int("12h", "d"), 1)
        self.assertEqual(parse_duration_int("2m", "s"), 120)
        self.assertEqual(parse_duration_int("0", "s"), 0)
        self.assertEqual(parse_duration_int("0ms", "s"), 0)
        self.assertIsInstance(parse_duration_int("500ms", "s"), int)
        with self.assertRaises(ValueError):
            parse_duration_int("5x", "s")

    def test_invalid_durations_raise_value_error(self):
        for value in ("", "5x", "-5", "5 m", "m"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value, "s")


if __name__ == "__main__":
    unittest.main()
