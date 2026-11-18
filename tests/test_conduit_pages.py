"""Headless tests for the Conduit pages' data layer.

The widget builders need a display; the data layer must not. These
tests run anywhere — including CI and a bare VM — and pin the honesty
rules: absent things are said plainly, the greeting carries this
machine's real budget, and the FAQ search understands 'refused'.
"""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source", "app"))

import conduit_pages as cp


def fake_crawl():
    return {
        "census": {
            "host": "testbox", "os": "Linux 6.x", "ts": "2026-11-17T00:00:00-0500",
            "cpu": {"logical_threads": 8, "effective_threads": 8.0,
                    "effective_source": "nominal", "load1": 0.5},
            "ram": {"effective_mb": 16384, "effective_source": "nominal"},
            "gpus": [], "disk_free_gb": 100,
            "expectations": {
                "budget": {"max_parallel_model_tasks": 2,
                           "conversation_seat": 1,
                           "parallel_model_task_seats": 1,
                           "basis": "test basis"},
                "tiers": [
                    {"tier": "conversation", "status": "resident (CPU seat, pinned)",
                     "expectation": "conversational pace"},
                    {"tier": "knowledge (web)", "status": "available (free-tier search script)",
                     "expectation": "network speed"},
                ]}},
        "pipes_found": [{"id": "ollama-door", "name": "Ollama model door",
                         "kind": "model", "feeds_plugin": "brains/conversation+deep",
                         "lane": "SERVICE"}],
        "pipes_not_found": ["usb-webcam"],
        "script_tier_offers": [],
    }


class TestGreeting(unittest.TestCase):
    def test_greeting_carries_budget_and_host(self):
        lines = cp.greeting_lines(fake_crawl())
        joined = "\n".join(lines)
        self.assertIn("testbox", joined)
        self.assertIn("2 model task(s)", joined)
        self.assertIn("Conversation: resident", joined)

    def test_tables_render(self):
        self.assertIn("Expectation table", cp.expectation_table_text(fake_crawl()))
        self.assertIn("ollama-door", cp.pipes_table_text(fake_crawl()))
        self.assertIn("not promised", cp.pipes_table_text(fake_crawl()))


class TestHonestAbsence(unittest.TestCase):
    def test_nodes_empty_state_says_so(self):
        self.assertIn("No sibling nodes", cp.nodes_text(fake_crawl(), []))

    def test_watch_empty_state_says_so(self):
        self.assertIn("No watch has run", cp.watch_text(None, None))

    def test_dwell_empty_state_says_so(self):
        self.assertIn("No node social", cp.dwell_text(None, None, fake_crawl()))


class TestComfort(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            cp.STATE_DIR = td
            cp.CONDUIT_JSON = os.path.join(td, "conduit.json")
            self.assertEqual(cp.load_comfort(), "balanced")
            cp.save_comfort("deep")
            self.assertEqual(cp.load_comfort(), "deep")


class TestModelAdvice(unittest.TestCase):
    """Zak's rule: existing models are advised on, never overwritten.
    A tuned resident (george-14) must earn a KEEP verdict."""

    def test_tuned_resident_is_kept(self):
        a = cp.model_advice(fake_crawl(), [{"name": "george-14"}])
        self.assertEqual(a["state"], "keep")
        self.assertEqual(a["resident"], "george-14")

    def test_small_resident_gets_upgrade_advice(self):
        a = cp.model_advice(fake_crawl(), [{"name": "qwen2.5:3b"}])
        self.assertEqual(a["state"], "upgrade")
        self.assertEqual(a["fitted"], "qwen3.5:9b")

    def test_empty_shelf_offers_the_fit(self):
        a = cp.model_advice(fake_crawl(), [])
        self.assertEqual(a["state"], "none")

    def test_silent_door_says_so(self):
        a = cp.model_advice(fake_crawl(), None)
        self.assertEqual(a["state"], "door-silent")


class TestFaq(unittest.TestCase):
    def test_synonym_search_finds_refusal(self):
        hits = cp.faq_filter("refused")
        self.assertTrue(any("connection refused" in q.lower() for q, _ in hits))

    def test_empty_query_returns_all(self):
        self.assertEqual(len(cp.faq_filter("")), len(cp.FAQ))


if __name__ == "__main__":
    unittest.main()
