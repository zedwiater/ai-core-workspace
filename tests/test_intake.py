"""Baseline: core.intake — Joy Calculator depth math + progress markers."""
import json
import unittest

from tests import __init__ as _path  # noqa: F401
from core import intake


def _answers(value):
    return {s["id"]: {"answer": value} for s in intake.STATEMENTS}


class TestDepthMath(unittest.TestCase):
    def test_empty_is_level_one(self):
        d = intake.compute_depth({})
        self.assertEqual(d["answered"], 0)
        self.assertEqual(d["percent"], 0)
        self.assertEqual(d["level"], 1)

    def test_all_agree(self):
        d = intake.compute_depth(_answers("Agree"))
        self.assertEqual(d["score"], 24)
        self.assertEqual(d["max_score"], 27)
        self.assertEqual(d["percent"], 89)
        self.assertEqual(d["level"], 5)

    def test_all_disagree(self):
        d = intake.compute_depth(_answers("Disagree"))
        self.assertEqual(d["score"], 3)
        self.assertEqual(d["level"], 1)

    def test_closers_open_by_disagreeing(self):
        closers = [s for s in intake.STATEMENTS
                   if s["disagree_pts"] > s["agree_pts"]]
        answers = {s["id"]: {"answer": "Disagree"} for s in closers}
        d = intake.compute_depth(answers)
        self.assertEqual(d["percent"], 100)
        self.assertEqual(d["level"], 5)

    def test_statement_points_sides(self):
        stmt = intake.STATEMENT_BY_ID["not-just-app"]
        self.assertEqual(intake.statement_points(stmt, "Agree"), 3)
        self.assertEqual(intake.statement_points(stmt, "Disagree"), 0)
        self.assertEqual(intake.statement_points(stmt, "skipped"), 0)

    def test_depth_level_bands(self):
        cases = [(0, 1), (19, 1), (20, 2), (39, 2), (40, 3),
                 (60, 4), (79, 4), (80, 5), (100, 5)]
        for percent, level in cases:
            self.assertEqual(intake.depth_level(percent)["level"], level,
                             f"percent={percent}")

    def test_lines_list_contributions(self):
        d = intake.compute_depth(
            {"it-remembers": {"answer": "Agree"}})
        self.assertEqual(len(d["lines"]), 1)
        self.assertIn("+3 depth", d["lines"][0])


class TestUnfinished(unittest.TestCase):
    def _patch(self, resp):
        orig = intake.mcp_call
        intake.mcp_call = lambda *a, **k: resp
        self.addCleanup(lambda: setattr(intake, "mcp_call", orig))

    def test_none_when_no_marker(self):
        self._patch({"status": "ok", "value": None})
        self.assertIsNone(intake.find_unfinished())

    def test_none_when_done(self):
        self._patch({"status": "ok", "value": json.dumps(
            {"session": "s1", "done": True, "page_index": 3,
             "answers": {}})})
        self.assertIsNone(intake.find_unfinished())

    def test_returns_open_run(self):
        self._patch({"status": "ok", "value": json.dumps(
            {"session": "s1", "done": False, "page_index": 4,
             "answers": {"it-remembers": "Agree"}})})
        got = intake.find_unfinished()
        self.assertEqual(got["session"], "s1")
        self.assertEqual(got["page_index"], 4)
        self.assertEqual(got["answers"], {"it-remembers": "Agree"})


if __name__ == "__main__":
    unittest.main()
