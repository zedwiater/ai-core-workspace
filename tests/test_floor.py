"""Baseline: core.floor — themes, snapshot comparison, monitor beats."""
import json
import os
import unittest

from tests import __init__ as _path  # noqa: F401
from core import floor


def _live_all_ok():
    live = {}
    for name, exp in floor.EXPECTED_SERVICES.items():
        if name == "web":
            live[name] = {"status": "ok", "reachable": True}
        else:
            live[name] = {"status": "ok", "service": name,
                          "ring": exp["ring"], "port": exp["port"],
                          "uptime_s": 12.5}
    return live


class TestThemes(unittest.TestCase):
    def test_five_themes_levels_in_order(self):
        self.assertEqual([t["level"] for t in floor.THEMES],
                         [1, 2, 3, 4, 5])

    def test_default_is_plain(self):
        self.assertEqual(floor.DEFAULT_THEME["level"], 1)
        self.assertEqual(floor.DEFAULT_THEME["name"],
                         "Plain Chatbot & Reminders")

    def test_theme_for_level_clamps(self):
        self.assertEqual(floor.theme_for_level(0)["level"], 1)
        self.assertEqual(floor.theme_for_level(99)["level"], 5)
        self.assertEqual(floor.theme_for_level(3)["level"], 3)

    def test_every_theme_carries_floor_note(self):
        for t in floor.THEMES:
            self.assertIn("wake and dwell", t["floor_note"])


class TestSnapshot(unittest.TestCase):
    def test_all_up_aligned(self):
        snap = floor.build_snapshot("wake", "s", floor.DEFAULT_THEME,
                                    _live_all_ok())
        self.assertTrue(snap["aligned"])
        self.assertEqual(snap["down"], [])
        self.assertEqual(snap["mismatches"], [])
        self.assertEqual(len(snap["up"]), 8)

    def test_down_service_named(self):
        live = _live_all_ok()
        del live["sound"]
        snap = floor.build_snapshot("dwell", "s", None, live)
        self.assertFalse(snap["aligned"])
        self.assertEqual(snap["down"], ["sound"])
        self.assertFalse(snap["services"]["sound"]["up"])

    def test_mismatch_named_plainly(self):
        live = _live_all_ok()
        live["memory"] = dict(live["memory"], ring="atmosphere")
        snap = floor.build_snapshot("wake", "s", None, live)
        self.assertFalse(snap["aligned"])
        self.assertTrue(any("memory" in m and "ring" in m
                            for m in snap["mismatches"]))

    def test_web_ping_note(self):
        live = _live_all_ok()
        live["web"] = {"status": "ok", "via": "ping"}
        snap = floor.build_snapshot("wake", "s", None, live)
        self.assertIn("note", snap["services"]["web"])


class TestThemePersistence(unittest.TestCase):
    def setUp(self):
        self.store = {}
        orig = floor.mcp_call

        def fake(port, payload, timeout=2):
            if payload["action"] == "set":
                self.store[payload["key"]] = payload["value"]
                return {"status": "ok"}
            if payload["action"] == "get":
                return {"status": "ok",
                        "value": self.store.get(payload["key"])}
            return {"status": "error"}

        floor.mcp_call = fake
        self.addCleanup(lambda: setattr(floor, "mcp_call", orig))

    def test_save_load_roundtrip(self):
        theme = floor.theme_for_level(4)
        self.assertTrue(floor.save_theme(theme, "test"))
        loaded, set_by = floor.load_theme()
        self.assertEqual(loaded["level"], 4)
        self.assertEqual(set_by, "test")

    def test_load_falls_back_to_plain(self):
        theme, set_by = floor.load_theme()
        self.assertEqual(theme["level"], 1)
        self.assertEqual(set_by, "default")


class TestMonitor(unittest.TestCase):
    def test_check_records_beats(self):
        mon = floor.FloorMonitor(session_id="t")
        orig_probe, orig_rec = floor.probe_services, floor.record_snapshot
        floor.probe_services = lambda timeout=2: _live_all_ok()
        floor.record_snapshot = lambda snap, port=None: True
        self.addCleanup(lambda: (setattr(floor, "probe_services", orig_probe),
                                 setattr(floor, "record_snapshot", orig_rec)))
        snap = mon.check("wake")
        self.assertEqual(snap["beat_count"], 1)
        self.assertIs(mon.last_snapshot, snap)
        snap2 = mon.check("dwell")
        self.assertEqual(snap2["beat_count"], 2)

    def test_check_never_raises(self):
        mon = floor.FloorMonitor(session_id="t")
        orig = floor.probe_services

        def boom(timeout=2):
            raise RuntimeError("probe exploded")

        floor.probe_services = boom
        self.addCleanup(lambda: setattr(floor, "probe_services", orig))
        self.assertIsNone(mon.check("wake"))

    @unittest.skipUnless(os.path.isdir("/proc"), "needs /proc")
    def test_check_records_process_count(self):
        mon = floor.FloorMonitor(session_id="t")
        orig_probe, orig_rec = floor.probe_services, floor.record_snapshot
        floor.probe_services = lambda timeout=2: _live_all_ok()
        floor.record_snapshot = lambda snap, port=None: True
        self.addCleanup(lambda: (setattr(floor, "probe_services", orig_probe),
                                 setattr(floor, "record_snapshot", orig_rec)))
        snap = mon.check("wake")
        self.assertIsInstance(snap["processes"], int)
        self.assertGreater(snap["processes"], 0)

    def test_companion_rides_the_beat(self):
        seen = []
        mon = floor.FloorMonitor(session_id="t",
                                 companion=seen.append)
        orig_probe, orig_rec = floor.probe_services, floor.record_snapshot
        floor.probe_services = lambda timeout=2: _live_all_ok()
        floor.record_snapshot = lambda snap, port=None: True
        self.addCleanup(lambda: (setattr(floor, "probe_services", orig_probe),
                                 setattr(floor, "record_snapshot", orig_rec)))
        mon.check("dwell")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["beat"], "dwell")

    def test_daughters_probe_lands_in_snapshot(self):
        mon = floor.FloorMonitor(
            session_id="t",
            daughters_probe=lambda: {"pi-lab": {"age_s": 5.0,
                                                "stale": False}})
        orig_probe, orig_rec = floor.probe_services, floor.record_snapshot
        floor.probe_services = lambda timeout=2: _live_all_ok()
        floor.record_snapshot = lambda snap, port=None: True
        self.addCleanup(lambda: (setattr(floor, "probe_services", orig_probe),
                                 setattr(floor, "record_snapshot", orig_rec)))
        snap = mon.check("wake")
        self.assertEqual(snap["daughters"]["pi-lab"]["age_s"], 5.0)


if __name__ == "__main__":
    unittest.main()
