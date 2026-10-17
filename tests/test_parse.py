import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shuttle.parse import parse_length, parse_percent, parse_text  # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "striped-towel.shuttle")

BASE = """\
sett: 16
ppi: 24
width: 16 in
length: 24 in
shafts: 4
warp: navy 8, white 4, navy 8
threading: 1 2 3 4
treadling: 1 2 3 4
weft: white
yarn navy: 2400 ypl 14.50
yarn white: 2400 ypl 13.00
"""


def messages(result):
    return [(issue.line, issue.message) for issue in result.issues]


class ParseTests(unittest.TestCase):
    def test_example_file_parses_cleanly(self):
        with open(EXAMPLE, encoding="utf-8") as handle:
            result = parse_text(handle.read())
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.project.sett, Decimal(16))
        self.assertEqual(result.project.shafts, 4)
        self.assertEqual(result.project.warp, [("navy", 8), ("white", 4), ("navy", 8)])
        self.assertEqual(result.project.repeats, 14)

    def test_glued_and_spaced_lengths_both_parse(self):
        self.assertEqual(parse_length("16in"), Decimal(16))
        self.assertEqual(parse_length("16 in"), Decimal(16))
        self.assertEqual(parse_length("  2 in "), Decimal(2))

    def test_centimetres_convert_to_inches(self):
        self.assertAlmostEqual(float(parse_length("40 cm")), 15.7480, places=3)

    def test_length_without_unit_is_reported_with_its_line(self):
        result = parse_text(BASE.replace("width: 16 in", "width: 16"))
        self.assertIn((3, "length needs a number and a unit (in or cm), got '16'"), messages(result))

    def test_percent_requires_a_sign(self):
        self.assertEqual(parse_percent("10%"), Decimal("0.1"))
        with self.assertRaises(ValueError):
            parse_percent("10")

    def test_shrink_of_100_percent_or_more_is_rejected(self):
        result = parse_text(BASE + "shrink: 100%\n")
        self.assertTrue(any(issue.line == 12 and "below 100%" in issue.message for issue in result.issues))

    def test_duplicate_setting_points_at_the_first_line(self):
        result = parse_text(BASE + "sett: 18\n")
        self.assertIn((12, "'sett' is already set on line 1"), messages(result))

    def test_missing_required_setting_is_reported(self):
        result = parse_text(BASE.replace("ppi: 24\n", ""))
        self.assertIn((None, "missing required setting 'ppi'"), messages(result))

    def test_unknown_setting_is_reported_with_its_line(self):
        result = parse_text(BASE + "colour: red\n")
        self.assertIn((12, "unknown setting 'colour'"), messages(result))

    def test_undefined_warp_yarn_is_reported_at_the_warp_line(self):
        result = parse_text(BASE.replace("yarn white: 2400 ypl 13.00", ""))
        self.assertIn((6, "warp uses 'white', but there is no 'yarn white:' line"), messages(result))

    def test_threading_shaft_above_shafts_is_an_error(self):
        result = parse_text(BASE.replace("threading: 1 2 3 4", "threading: 1 2 5"))
        self.assertIn((7, "threading uses shaft 5, but shafts is 4"), messages(result))

    def test_yarn_needs_ypl_and_price(self):
        result = parse_text(BASE.replace("yarn navy: 2400 ypl 14.50", "yarn navy: 2400 14.50"))
        self.assertTrue(any(issue.line == 10 and "ypl" in issue.message for issue in result.issues))

    def test_line_without_colon_is_reported(self):
        result = parse_text(BASE + "this is not a setting\n")
        self.assertEqual(result.issues[0].line, 12)
        self.assertIn("expected 'key: value'", result.issues[0].message)

    def test_comments_blank_lines_and_inline_comments_are_ignored(self):
        text = "# header comment\n\n" + BASE.replace("sett: 16", "sett: 16   # ends per inch")
        self.assertTrue(parse_text(text).ok)

    def test_yarn_names_are_case_and_spacing_insensitive(self):
        text = BASE.replace("yarn navy: 2400 ypl 14.50", "yarn  Dark   Navy: 2400 ypl 14.50").replace(
            "warp: navy 8, white 4, navy 8", "warp: dark navy 8, white 4, DARK NAVY 8")
        result = parse_text(text)
        self.assertTrue(result.ok, result.issues)
        self.assertIn("dark navy", result.project.yarns)


if __name__ == "__main__":
    unittest.main()
