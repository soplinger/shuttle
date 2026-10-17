import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from shuttle.cli import main  # noqa: E402

EXAMPLE = os.path.join(ROOT, "examples", "striped-towel.shuttle")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def write(self, directory, text):
        path = os.path.join(directory, "project.shuttle")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_check_passes_the_example(self):
        code, out, err = run("check", EXAMPLE)
        self.assertEqual(code, 0, err)
        self.assertIn("OK:", out)
        self.assertIn("280 ends", out)

    def test_check_reports_errors_with_path_and_line_and_exits_2(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, "sett: sixteen\n")
            code, _, err = run("check", path)
        self.assertEqual(code, 2)
        self.assertIn(f"{path}:1: error:", err)

    def test_check_exits_1_for_warnings_only(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(EXAMPLE, encoding="utf-8") as handle:
                text = handle.read().replace("width: 16 in", "width: 30 in")
            path = self.write(directory, text)
            code, _, err = run("check", path)
        self.assertEqual(code, 1)
        self.assertIn("warning", err)

    def test_plan_json_is_machine_readable(self):
        code, out, _ = run("plan", EXAMPLE, "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["ends"], 280)
        self.assertEqual(data["picks"], 640)
        self.assertEqual([yarn["name"] for yarn in data["yarns"]], ["navy", "white"])

    def test_plan_text_lists_each_yarn_and_a_total(self):
        code, out, _ = run("plan", EXAMPLE)
        self.assertEqual(code, 0)
        self.assertIn("navy", out)
        self.assertIn("white", out)
        self.assertIn("Total", out)

    def test_repeat_command_shows_the_current_choice(self):
        code, out, _ = run("repeat", EXAMPLE)
        self.assertEqual(code, 0)
        self.assertIn("14 repeats = 280 ends", out)
        self.assertIn("(current)", out)

    def test_sett_command_computes_ends_per_inch(self):
        code, out, _ = run("sett", "--width", "16in", "--ends", "285", "--shrink", "10%")
        self.assertEqual(code, 0)
        self.assertIn("needs 16.03 ends per inch", out)

    def test_missing_file_exits_2(self):
        code, _, err = run("check", os.path.join(ROOT, "no-such-file.shuttle"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read file", err)


if __name__ == "__main__":
    unittest.main()
