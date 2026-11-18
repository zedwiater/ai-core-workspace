"""core.settings — options store: defaults, validation, persistence."""
import json
import unittest

from tests import __init__ as _path  # noqa: F401
from core.settings import Options


def _fake_call(store):
    def call(port, payload, timeout=2):
        if payload["action"] == "set":
            store[payload["key"]] = payload["value"]
            return {"status": "ok"}
        if payload["action"] == "get":
            return {"status": "ok", "value": store.get(payload["key"])}
        return {"status": "error"}
    return call


def _down_call(port, payload, timeout=2):
    return {"status": "error", "message": "down"}


class TestDefaults(unittest.TestCase):
    def test_defaults_when_memory_silent(self):
        opts = Options.load(call=_down_call)
        self.assertEqual(opts.get("patience", "dwell_minutes"), 15)
        self.assertEqual(opts.get("cloud", "policy"), "draft")
        self.assertTrue(opts.sense_live("sound"))

    def test_derived_views(self):
        opts = Options.load(call=_down_call)
        self.assertEqual(opts.dwell_seconds(), 900)
        self.assertEqual(opts.indicator_seconds(), 2.5)


class TestSetAndPersist(unittest.TestCase):
    def test_roundtrip_through_memory(self):
        store = {}
        opts = Options.load(call=_fake_call(store))
        self.assertTrue(opts.set("patience", "dwell_minutes", 30))
        self.assertTrue(opts.persisted())
        again = Options.load(call=_fake_call(store))
        self.assertEqual(again.get("patience", "dwell_minutes"), 30)
        self.assertEqual(again.dwell_seconds(), 1800)

    def test_invalid_value_refused_not_clamped(self):
        opts = Options.load(call=_down_call)
        self.assertFalse(opts.set("patience", "dwell_minutes", 7))
        self.assertEqual(opts.get("patience", "dwell_minutes"), 15)
        self.assertFalse(opts.set("cloud", "policy", "sometimes"))
        self.assertFalse(opts.set("bogus-group", "x", 1))

    def test_set_applies_even_when_write_fails(self):
        opts = Options.load(call=_down_call)
        self.assertTrue(opts.set("cadence", "indicator", "quiet"))
        self.assertEqual(opts.indicator_seconds(), 15.0)
        self.assertFalse(opts.persisted())

    def test_stored_junk_is_ignored(self):
        store = {"app:options": json.dumps(
            {"patience": {"dwell_minutes": 999},
             "cloud": {"policy": "allowed"}, "mystery": {"x": 1}})}
        opts = Options.load(call=_fake_call(store))
        self.assertEqual(opts.get("patience", "dwell_minutes"), 15)
        self.assertEqual(opts.get("cloud", "policy"), "allowed")

    def test_sense_toggle(self):
        opts = Options.load(call=_down_call)
        self.assertTrue(opts.set("senses", "vision", False))
        self.assertFalse(opts.sense_live("vision"))
        self.assertTrue(opts.sense_live("files"))


if __name__ == "__main__":
    unittest.main()
