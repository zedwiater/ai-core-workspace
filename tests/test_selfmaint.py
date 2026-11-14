"""core.selfmaint — census detection, safe fills, proposals.

Detection tests seed synthetic mismatches in temp trees; fill
tests prove backup creation + idempotence; proposal tests prove
behavior-class findings are filed, never applied.
"""
import json
import tempfile
import unittest
from pathlib import Path

from tests import __init__ as _path  # noqa: F401
from core import selfmaint

SERVICE = '''from core.ring_service import serve

def ping(req): return {"status": "pong"}
def get(req): return {"status": "ok"}
def set_(req): return {"status": "ok"}
def lst(req): return {"status": "ok", "entries": []}

if __name__ == "__main__":
    serve("memory", "state", 9108,
          {"ping": ping, "get": get, "set": set_, "list": lst})
'''


def _mini_tree(td, client_tokens, config=None):
    root = Path(td)
    (root / "source" / "app").mkdir(parents=True)
    (root / "source" / "rings" / "state").mkdir(parents=True)
    (root / "source" / "core").mkdir(parents=True)
    (root / "source" / "app" / "ai-client.py").write_text(
        "INSTR = '''\n" + "\n".join(client_tokens) + "\n'''\n")
    (root / "source" / "rings" / "state"
     / "mcp-memory.py").write_text(SERVICE)
    (root / "source" / "config.json").write_text(
        json.dumps(config or {}))
    (root / "README.md").write_text("# x\n")
    return root


def _ids(findings):
    return {f["id"] for f in findings}


class TestCensusDetection(unittest.TestCase):
    def test_detects_all_four_known_classes(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [
                'TOOL:memory:store:{"key":"k","value":"v"}',
                'TOOL:memory:recall:{"key":"k"}',
                'TOOL:memory:list_keys:{}',
            ], config={"max_loops": 5, "timeout": 30})
            findings = selfmaint.census(root)
            ids = _ids(findings)
            self.assertIn("gap-client-memory-store", ids)
            self.assertIn("gap-client-memory-recall", ids)
            self.assertIn("gap-client-memory-list-keys", ids)
            self.assertIn("gloss-config-max-loops-unread", ids)
            self.assertIn("gloss-config-timeout-unread", ids)
            by_id = {f["id"]: f for f in findings}
            self.assertEqual(
                by_id["gap-client-memory-store"]["class"], "safe")
            self.assertEqual(
                by_id["gloss-config-max-loops-unread"]["class"],
                "proposal")

    def test_unknown_mismatch_is_proposal_not_safe(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, ['TOOL:memory:explode:{}'])
            findings = selfmaint.census(root)
            f = next(f for f in findings
                     if f["id"] == "gap-client-memory-explode")
            self.assertEqual(f["class"], "proposal")

    def test_response_key_gloss_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [])
            coding = root / "source" / "rings" / "state" \
                / "mcp-coding.py"
            coding.write_text(
                'from core.ring_service import serve\n'
                'def ev(req): return {"status": "ok", '
                '"return": None}\n'
                'if __name__ == "__main__":\n'
                '    serve("coding", "state", 9107, '
                '{"eval": ev})\n')
            findings = selfmaint.census(root)
            self.assertIn("gloss-coding-eval-response-result",
                          _ids(findings))

    def test_aligned_tree_is_quiet_on_advertising(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [
                'TOOL:memory:set:{"key":"k","value":"v"}',
                'TOOL:memory:get:{"key":"k"}',
                'TOOL:memory:list:{}'])
            findings = selfmaint.census(root)
            self.assertFalse(any(
                f["id"].startswith("gap-client-memory")
                for f in findings))


class TestSafeFills(unittest.TestCase):
    def test_fill_aligns_with_backup_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [
                'TOOL:memory:store:{"key":"k","value":"v"}',
                'TOOL:memory:list_keys:{}'])
            state = Path(td) / "selfmaint"
            findings = selfmaint.census(root)
            receipts = selfmaint.apply_safe_fills(
                root, state, findings, ts="T1")
            aligns = [r for r in receipts
                      if r["action"] == "align-advertisement"]
            # Both tokens align — list_keys included (its id is
            # slugged with a hyphen; the fill must not lose it).
            self.assertEqual(len(aligns), 2)
            client = root / "source" / "app" / "ai-client.py"
            self.assertIn("TOOL:memory:set:", client.read_text())
            self.assertIn("TOOL:memory:list:", client.read_text())
            self.assertNotIn("TOOL:memory:store:",
                             client.read_text())
            self.assertNotIn("TOOL:memory:list_keys:",
                             client.read_text())
            self.assertTrue(Path(aligns[0]["backup"]).exists())
            # Second beat: census quiet, nothing redone.
            again = selfmaint.apply_safe_fills(
                root, state, selfmaint.census(root), ts="T2")
            self.assertEqual(again, [])

    def test_proposals_filed_once_never_applied(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, ['TOOL:memory:explode:{}'],
                              config={"max_loops": 5})
            state = Path(td) / "selfmaint"
            findings = selfmaint.census(root)
            receipts = selfmaint.apply_safe_fills(
                root, state, findings, ts="T1")
            # Only safe-class work happened (the label backfill);
            # the proposal-class mismatch was NOT applied.
            self.assertTrue(all(
                r["action"] == "backfill-label" for r in receipts))
            filed = selfmaint.file_proposals(
                state, findings, ts="now")
            self.assertTrue(filed)
            self.assertEqual(
                selfmaint.file_proposals(state, findings,
                                         ts="later"), [])
            client = root / "source" / "app" / "ai-client.py"
            self.assertIn("TOOL:memory:explode",
                          client.read_text())  # untouched
            waiting = selfmaint.waiting_proposals(state)
            self.assertTrue(any("explode" in w for w in waiting))


class TestRealTree(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_census_finds_the_coding_eval_gloss_here(self):
        findings = selfmaint.census(self.ROOT)
        self.assertIn("gloss-coding-eval-response-result",
                      _ids(findings))
        self.assertIn("gloss-web-legacy-health", _ids(findings))


class TestLabelsRoutesLimits(unittest.TestCase):
    def test_unlabeled_service_is_a_safe_finding(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [])
            findings = selfmaint.census(root)
            f = next(f for f in findings
                     if f["id"] == "gap-label-memory")
            self.assertEqual(f["class"], "safe")

    def test_label_backfill_applies_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [])
            state = Path(td) / "selfmaint"
            receipts = selfmaint.apply_safe_fills(
                root, state, selfmaint.census(root), ts="T1")
            self.assertTrue(any(r["action"] == "backfill-label"
                                for r in receipts))
            svc = root / "source" / "rings" / "state" \
                / "mcp-memory.py"
            from core.ring_service import (label_complete,
                                           parse_label)
            self.assertTrue(label_complete(
                parse_label(svc.read_text())))
            again = selfmaint.apply_safe_fills(
                root, state, selfmaint.census(root), ts="T2")
            self.assertFalse(any(r["action"] == "backfill-label"
                                 for r in again))

    def test_unrouted_service_is_a_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(td, [])
            extra = root / "source" / "rings" / "state" \
                / "mcp-extra.py"
            extra.write_text(
                'from core.ring_service import serve, label_block\n'
                + 'serve("extra", "state", 9999, {"ping": None})\n')
            # label it by hand so only the route finding fires
            from core.ring_service import label_block
            extra.write_text(label_block(
                "extra", "test", "1", "a test organ")
                + "\n" + extra.read_text())
            findings = selfmaint.census(root)
            f = next(f for f in findings
                     if f["id"] == "gloss-route-extra-unregistered")
            self.assertEqual(f["class"], "proposal")

    def test_limits_drift_needs_measured_shortfall(self):
        with tempfile.TemporaryDirectory() as td:
            root = _mini_tree(
                td, [], config={"model": "qwen2.5:32b"})
            small = {"ram_gb": 8, "gpu": {}}
            big = {"ram_gb": 64, "gpu": {}}
            self.assertIn("gloss-limits-declared-vs-actual",
                          _ids(selfmaint.census(root,
                                                profile=small)))
            self.assertNotIn("gloss-limits-declared-vs-actual",
                             _ids(selfmaint.census(root,
                                                   profile=big)))
            # No profile → the check stays silent.
            self.assertNotIn("gloss-limits-declared-vs-actual",
                             _ids(selfmaint.census(root)))


if __name__ == "__main__":
    unittest.main()
