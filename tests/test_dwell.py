"""The dwell build (Zak, 2026-11-18): roam grabs on a tier
loop, a review queue, attention that snaps, an emergency
monitor, and Telegram alerts through the user's own bot.
The pipe never leaks the token, the loop is off until the
user turns it on, and level-only alerts are labelled as
level alerts — never as classified alarms."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import dwell, notify  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class DwellMathTests(unittest.TestCase):
    def test_tier_paces(self):
        self.assertEqual(dwell.dwell_default_s(48), 30)
        self.assertEqual(dwell.dwell_default_s(16), 45)
        self.assertEqual(dwell.dwell_default_s(7.6), 60)

    def test_sound_rose(self):
        self.assertTrue(dwell.sound_rose(-60.0, -20.0))
        self.assertTrue(dwell.sound_rose(None, -20.0))
        self.assertFalse(dwell.sound_rose(-40.0, -38.0))
        self.assertFalse(dwell.sound_rose(-60.0, -30.0))

    def test_frame_changed(self):
        self.assertTrue(dwell.frame_changed(10000, 16000))
        self.assertFalse(dwell.frame_changed(10000, 11000))
        self.assertFalse(dwell.frame_changed(0, 5000))

    def test_loud_sustained_needs_two(self):
        self.assertTrue(dwell.loud_sustained([-30.0, -10.0,
                                              -8.0]))
        self.assertFalse(dwell.loud_sustained([-8.0]))
        self.assertFalse(dwell.loud_sustained([-8.0, -40.0]))

    def test_loop_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "conduit.json")
            self.assertFalse(dwell.load_loop_config(p)["enabled"])
            dwell.save_loop_config(True, 30, p)
            cfg = dwell.load_loop_config(p)
            self.assertTrue(cfg["enabled"])
            self.assertEqual(cfg["dwell_s"], 30)


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.secrets = os.path.join(self.tmp.name, "secrets.json")
        with open(self.secrets, "w") as f:
            json.dump({"telegram-token": "tok-123",
                       "pairing-secret": "keepme"}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def fake_opener(self, payload):
        def opener(req, timeout=0):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return json.dumps(payload).encode()
            # urllib json.load reads via .read on the response
            import io
            return io.BytesIO(json.dumps(payload).encode())
        return opener

    def test_status_reads_token_presence_only(self):
        st = notify.status(self.secrets,
                           opener=self.fake_opener(
                               {"ok": True,
                                "result": {"username": "aicorebot"}}))
        self.assertTrue(st["token"])
        self.assertEqual(st["bot"], "aicorebot")
        self.assertNotIn("tok-123", json.dumps(st))

    def test_send_without_chat_discovers_first(self):
        calls = []

        def opener(req, timeout=0):
            import io
            calls.append(req.full_url)
            if "getUpdates" in req.full_url:
                payload = {"ok": True, "result": [
                    {"message": {"chat": {"id": 4242}}}]}
            else:
                payload = {"ok": True, "result": {}}
            return io.BytesIO(json.dumps(payload).encode())
        out = notify.send("hello", self.secrets, opener=opener)
        self.assertTrue(out["ok"])
        saved = json.load(open(self.secrets))
        self.assertEqual(saved["telegram-chat-id"], 4242)
        # the user's other secret survived the write
        self.assertEqual(saved["pairing-secret"], "keepme")

    def test_no_token_is_an_honest_no(self):
        empty = os.path.join(self.tmp.name, "none.json")
        out = notify.send("hi", empty)
        self.assertFalse(out["ok"])
        self.assertIn("BotFather", out["why"])


class MicPathTests(unittest.TestCase):
    """The laptop mic fix (2026-11-18): the default source
    was an empty port; the real mic is a NAMED source, and
    a muted server must be named, not mistaken for death."""

    def _sound(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mcp_sound2", os.path.join(
                ROOT, "source", "rings", "atmosphere",
                "mcp-sound.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_named_sources_parsed_monitors_skipped(self):
        sound = self._sound()

        class R:
            stdout = ("553\talsa_input.usb.mic\tPipeWire\n"
                      "554\talsa_output.hdmi.monitor\tPipeWire\n"
                      "555\talsa_input.pci.pro-input-1\tP\n")
        names = sound.pipewire_sources(runner=lambda *a, **k: R())
        self.assertEqual(names, ["alsa_input.usb.mic",
                                 "alsa_input.pci.pro-input-1"])

    def test_all_muted_detected(self):
        sound = self._sound()

        class R:
            stdout = ("Source #1\n\tName: alsa_input.a\n"
                      "\tMute: yes\nSource #2\n"
                      "\tName: alsa_output.x.monitor\n"
                      "\tMute: no\n")
        self.assertTrue(sound.sources_muted(
            runner=lambda *a, **k: R()))
        R.stdout = ("Source #1\n\tName: alsa_input.a\n"
                    "\tMute: no\n")
        self.assertFalse(sound.sources_muted(
            runner=lambda *a, **k: R()))


class GovernorTests(unittest.TestCase):
    """Zak's caps (2026-11-18): background dwell may never
    compromise storage, RAM, or the user's busy machine."""

    def test_tier_caps(self):
        from core import governor
        self.assertEqual(governor.budget_for(7.6)["storage_cap_mb"],
                         300)
        self.assertEqual(governor.budget_for(16)["storage_cap_mb"],
                         1024)
        self.assertEqual(governor.budget_for(48)["storage_cap_mb"],
                         2048)

    def test_over_cap_prunes_oldest_first(self):
        from core import governor
        with tempfile.TemporaryDirectory() as d:
            frames = os.path.join(d, "frames")
            os.makedirs(frames)
            old = os.path.join(frames, "old.jpg")
            new = os.path.join(frames, "new.jpg")
            for p in (old, new):
                with open(p, "wb") as f:
                    f.write(b"x" * 600_000)
            os.utime(old, (1000, 1000))
            freed = governor.prune_to_cap(d, 1)
            self.assertGreater(freed, 0)
            self.assertFalse(os.path.exists(old))
            self.assertTrue(os.path.exists(new))

    def test_assess_names_its_throttle(self):
        from core import governor
        with tempfile.TemporaryDirectory() as d:
            v = governor.assess(d, 7.6)
            self.assertIn("used_mb", v)
            self.assertIn("budget", v)


class ClipWiringTests(unittest.TestCase):
    def test_vision_has_clip_and_dwell_uses_it(self):
        vision = open(os.path.join(
            ROOT, "source", "rings", "atmosphere",
            "mcp-vision.py")).read()
        self.assertIn('"clip": clip', vision)
        self.assertIn("def clip_frame", vision)
        svc = open(os.path.join(
            ROOT, "source", "rings", "atmosphere",
            "mcp-dwell.py")).read()
        self.assertIn("governor", svc)
        self.assertIn('clip=(i == 0', svc)


class WiringTests(unittest.TestCase):
    def test_service_and_installer_carry_dwell(self):
        install = open(os.path.join(ROOT, "install.sh")).read()
        self.assertIn('"dwell"', install)
        svc = open(os.path.join(
            ROOT, "source", "rings", "atmosphere",
            "mcp-dwell.py")).read()
        self.assertIn('serve("dwell", "atmosphere", PORT', svc)
        proto = open(os.path.join(
            ROOT, "source", "core", "protocol.py")).read()
        self.assertIn('"dwell": 9109', proto)

    def test_sound_gained_level_and_record(self):
        src = open(os.path.join(
            ROOT, "source", "rings", "atmosphere",
            "mcp-sound.py")).read()
        self.assertIn('"level": level', src)
        self.assertIn('"record": record', src)

    def test_client_surfaces(self):
        client = open(os.path.join(
            ROOT, "source", "app", "ai-client.py")).read()
        self.assertIn("TOOL:dwell:status", client)
        self.assertIn('"record": "quick"', client)
        pages = open(os.path.join(
            ROOT, "source", "app", "conduit_pages.py")).read()
        self.assertIn("Dwell loop — patrol", pages)


if __name__ == "__main__":
    unittest.main()
