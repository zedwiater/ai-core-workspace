"""The senses must connect to THIS machine (field failure,
Zak, 2026-11-18): the vision service shipped with one
household's RTSP cameras hardcoded — it offered cameras that
did not exist and could not see the laptop's webcam — and
the sound service swallowed a dead capture path into
'heard: ""' while claiming to be listening. These tests pin
discovery, honest errors, and honest capabilities."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import wave

ROOT = os.path.join(os.path.dirname(__file__), "..", "source")


def load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(ROOT))
    spec.loader.exec_module(mod)
    return mod


vision = load("mcp_vision", "rings/atmosphere/mcp-vision.py")
sound = load("mcp_sound", "rings/atmosphere/mcp-sound.py")


class VisionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys_root = os.path.join(self.tmp.name, "v4l")
        self.dev_root = os.path.join(self.tmp.name, "dev")
        os.makedirs(os.path.join(self.sys_root, "video0"))
        os.makedirs(self.dev_root)
        with open(os.path.join(self.sys_root, "video0", "name"),
                  "w") as f:
            f.write("HP Wide Vision HD Camera")
        open(os.path.join(self.dev_root, "video0"), "w").close()
        self.config = os.path.join(self.tmp.name, "cameras.json")
        with open(self.config, "w") as f:
            json.dump({"hillbilly-front":
                       "rtsp://192.168.68.97:8554/hillbilly-front"},
                      f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_local_webcam_discovered_with_alias(self):
        cmap = vision.camera_map(self.sys_root, self.config,
                                 self.dev_root)
        self.assertIn("webcam", cmap)
        self.assertEqual(cmap["webcam"]["kind"], "local")
        self.assertIn("webcam (HP Wide Vision HD Camera)", cmap)

    def test_configured_cameras_merge_as_data(self):
        cmap = vision.camera_map(self.sys_root, self.config,
                                 self.dev_root)
        self.assertEqual(cmap["hillbilly-front"]["kind"], "rtsp")

    def test_no_hardcoded_house_cameras(self):
        src = open(os.path.join(
            ROOT, "rings", "atmosphere", "mcp-vision.py")).read()
        self.assertNotIn("192.168.68.97", src)
        self.assertNotIn("under-back-porch", src)

    def test_unknown_camera_names_the_real_ones(self):
        cmap = vision.camera_map(self.sys_root, self.config,
                                 self.dev_root)
        out = vision.grab_frame("nope", cmap)
        self.assertEqual(out["status"], "error")
        self.assertIn("webcam", out["message"])

    def test_list_reports_kinds(self):
        cmap = vision.camera_map(self.sys_root, self.config,
                                 self.dev_root)
        out = vision.list_cameras(cmap)
        self.assertEqual(out["details"]["webcam"], "local")
        self.assertEqual(out["details"]["hillbilly-front"],
                         "rtsp")


class SoundHonestyTests(unittest.TestCase):
    def test_microphone_present_from_sound_class(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "pcmC0D0c"), "w").close()
            open(os.path.join(d, "pcmC0D0p"), "w").close()
            self.assertTrue(sound.microphone_present(d))
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "pcmC0D0p"), "w").close()
            self.assertFalse(sound.microphone_present(d))

    def test_clip_level_measures_a_real_wav(self):
        with tempfile.NamedTemporaryFile(suffix=".wav",
                                         delete=False) as f:
            path = f.name
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x40" * 1600)  # ~ -12 dBFS tone
        level = sound.clip_level_db(path)
        self.assertIsNotNone(level)
        self.assertGreater(level, -20)
        self.assertLess(level, -5)

    def test_capture_failure_names_itself(self):
        # ffmpeg pointed at a nonexistent input path shape is
        # hard to fake portably; instead pin the contract: the
        # module no longer contains the silent-swallow pattern
        src = open(os.path.join(
            ROOT, "rings", "atmosphere", "mcp-sound.py")).read()
        self.assertIn("microphone capture failed", src)
        self.assertIn("no speech-to-text is", src)
        self.assertIn("installed on this machine", src)
        self.assertNotIn('"listening": LISTENING', src)


if __name__ == "__main__":
    unittest.main()
