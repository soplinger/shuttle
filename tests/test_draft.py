import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shuttle import draft  # noqa: E402
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


class DraftTests(unittest.TestCase):
    def test_threading_cycles_through_the_shafts(self):
        self.assertEqual(draft.end_shafts(load())[:6], [1, 2, 3, 4, 1, 2])

    def test_end_colors_follow_the_warp_stripes(self):
        colors = draft.end_colors(load())
        self.assertEqual(len(colors), 280)
        self.assertEqual(colors[:8], ["navy"] * 8)
        self.assertEqual(colors[8:12], ["white"] * 4)

    def test_threading_chart_has_one_row_per_shaft_per_block(self):
        chart = draft.threading_chart(load())
        self.assertIn("ends 1-60", chart)
        self.assertIn("ends 241-280", chart)
        self.assertEqual(chart.count("shaft  4"), 5)
        self.assertIn("shaft  1  x...x...", chart)

    def test_threading_chart_marks_each_end_on_exactly_one_shaft(self):
        chart = draft.threading_chart(load(), per_row=20).split("\n\n")[0]
        rows = [line for line in chart.splitlines() if line.startswith("shaft")]
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(row[-20:].count("x") for row in rows), 20)

    def test_treadling_counts_split_evenly_over_full_repeats(self):
        summary = draft.treadling_summary(load())
        self.assertEqual(summary.picks, 640)
        self.assertEqual(summary.full_repeats, 160)
        self.assertEqual(summary.leftover, 0)
        self.assertEqual(summary.counts, {1: 160, 2: 160, 3: 160, 4: 160})

    def test_leftover_picks_go_to_the_first_treadles(self):
        project = load()
        project.treadling = [1, 2, 3]
        summary = draft.treadling_summary(project)
        self.assertEqual(summary.full_repeats, 213)
        self.assertEqual(summary.leftover, 1)
        self.assertEqual(summary.counts, {1: 214, 2: 213, 3: 213})

    def test_pick_sequence_repeats_the_treadling(self):
        self.assertEqual(draft.pick_sequence(load(), 6), [1, 2, 3, 4, 1, 2])


if __name__ == "__main__":
    unittest.main()
