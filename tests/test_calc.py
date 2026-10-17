import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shuttle import calc  # noqa: E402
from shuttle.parse import parse_text  # noqa: E402

BASE = """\
title: Test towel
sett: 16
ppi: 24
width: 16 in
length: 24 in
shrink: 10%
takeup: 10%
hems: 2 in
loom_waste: 36 in
waste: 10%
shafts: 4
warp: navy 8, white 4, navy 8
repeats: 14
threading: 1 2 3 4
treadling: 1 2 3 4
weft: white
yarn navy: 2400 ypl 14.50
yarn white: 2400 ypl 13.00
"""


def load(text=BASE):
    result = parse_text(text)
    assert result.ok, result.issues
    return result.project


class CalcTests(unittest.TestCase):
    def test_ends_come_from_the_warp_pattern_and_repeats(self):
        project = load()
        self.assertEqual(calc.repeat_ends(project), 20)
        self.assertEqual(calc.total_ends(project), 280)

    def test_target_ends_for_the_finished_width(self):
        # 16 in after 10% shrink is 17.78 in on the loom, times 16 ends per inch, rounded up.
        self.assertEqual(calc.target_ends(load()), 285)

    def test_predicted_finished_width_applies_shrinkage(self):
        self.assertEqual(calc.predicted_width(load()), Decimal("15.75"))

    def test_warp_length_adds_hems_take_up_and_waste(self):
        # (26.67 + 2 * 2) / 0.9 + 36 = 70.07 inches
        self.assertAlmostEqual(float(calc.warp_length(load())), 70.07, places=2)

    def test_picks_round_up_without_float_noise(self):
        # 24 / 0.9 * 24 is 640 exactly; division noise must not push it to 641.
        self.assertEqual(calc.picks(load()), 640)

    def test_plan_counts_ends_per_yarn(self):
        plan = calc.make_plan(load())
        ends = {line.name: line.ends for line in plan.lines}
        self.assertEqual(ends, {"navy": 224, "white": 56})
        self.assertEqual(plan.ends, 280)

    def test_costs_are_rounded_to_cents(self):
        plan = calc.make_plan(load())
        for line in plan.lines:
            self.assertEqual(line.cost.as_tuple().exponent, -2)
        self.assertEqual(plan.total_cost, sum(line.cost for line in plan.lines))

    def test_weft_yardage_is_added_to_the_weft_yarn(self):
        plan = calc.make_plan(load())
        white = next(line for line in plan.lines if line.name == "white")
        navy = next(line for line in plan.lines if line.name == "navy")
        # Navy: 224 ends * 70.07 in / 36 * 1.1 waste. White also carries about 351.6 yards of weft.
        self.assertAlmostEqual(float(navy.yards), 479.6, places=0)
        self.assertAlmostEqual(float(white.yards), 506.7, places=0)

    def test_repeat_options_bracket_the_target_width(self):
        options = calc.repeat_options(load())
        self.assertEqual([option.repeats for option in options], [14, 15])
        self.assertEqual([option.ends for option in options], [280, 300])
        self.assertEqual(options[1].width.quantize(Decimal("0.01")), Decimal("16.88"))

    def test_sett_for_a_width_after_shrinkage(self):
        epi = calc.sett_for(Decimal(16), 285, Decimal("0.1"))
        self.assertAlmostEqual(float(epi), 16.03, places=2)

    def test_width_mismatch_produces_a_warning(self):
        project = load(BASE.replace("width: 16 in", "width: 20 in"))
        messages = [issue.message for issue in calc.warnings(project)]
        self.assertTrue(any("finished width" in message for message in messages), messages)

    def test_unused_yarn_and_unthreaded_shaft_are_warnings(self):
        project = load(BASE.replace("yarn white: 2400 ypl 13.00", "yarn white: 2400 ypl 13.00\nyarn rust: 1000 ypl 9")
                       .replace("threading: 1 2 3 4", "threading: 1 2 3"))
        messages = [issue.message for issue in calc.warnings(project)]
        self.assertIn("shaft 4 is never threaded", messages)
        self.assertIn("yarn 'rust' is defined but never used", messages)


if __name__ == "__main__":
    unittest.main()
