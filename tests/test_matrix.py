"""The hardware matrix (Zak, 2026-11-18): an end user pulls
this app onto whatever Linux box they have — a modded
phone, a Chromebook, a Pi, a mid tower with a decade-old
GPU and a USB sound card. The install's DECISIONS are what
must be right on every one of them: which model pairs and
where it sits, how fast dwell patrols, what the governor
caps, which organs the reach map finds, and whether the
mic walk includes the source that actually hears.

VMs cannot fake a codec or a webcam's driver behaviour;
what they CAN exhaust is the decision layer against
hardware lists. These profiles are those lists. The two
real Arch machines (laptop, PC) remain the hardware truth
the fixtures are modelled on."""
import importlib.util
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import dwell, governor, pairing  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "source", rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sound = _load("mcp_sound_matrix", "rings/atmosphere/mcp-sound.py")
census_mod = _load("census_matrix", "core/census.py")


def profile(ram_mb, vram_gb=0, cameras=(), audio=()):
    return {"ram": {"effective_mb": ram_mb},
            "gpus": [{"vram_gb": vram_gb}] if vram_gb else [],
            "cameras": list(cameras),
            "audio": list(audio)}


PROFILES = [
    # name, census, model, mode fragment, dwell_s, cap_mb
    ("modded phone (3 GB, no GPU)",
     profile(3072), "qwen2.5:1.5b", "nominal", 60, 300),
    ("modded Chromebook (4 GB, iGPU)",
     profile(4096), "qwen2.5:1.5b", "CPU seat", 60, 300),
    ("reference laptop (7.6 GB)",
     profile(7782), "qwen2.5:3b", "CPU seat", 60, 300),
    ("Pi-class SBC (8 GB, USB cam)",
     profile(8192, cameras=[{"device": "/dev/video0",
                             "name": "USB Cam"}]),
     "qwen2.5:3b", "CPU seat", 60, 300),
    # largest-first doctrine: 16 GB + a 4 GB card pairs the
    # 14B on a split seat (39% of layers on the GPU) rather
    # than a mostly-GPU 7B — capacity over speed; the user
    # trades down via the comfort gradient, not the pairing
    ("old mid tower (16 GB, 4 GB GPU)",
     profile(16384, vram_gb=4), "qwen2.5:14b", "split", 45, 1024),
    ("rich mid (32 GB, 6 GB GPU)",
     profile(32768, vram_gb=6), "qwen2.5:14b", "split", 30, 2048),
    ("reference PC (48 GB, 8 GB GPU)",
     profile(49152, vram_gb=8), "qwen2.5:14b", "split", 30, 2048),
]


class MatrixTests(unittest.TestCase):
    def test_every_profile_pairs_and_is_governed(self):
        for name, cen, model, mode, dwell_s, cap in PROFILES:
            with self.subTest(profile=name):
                p = pairing.pair(cen)
                self.assertEqual(p["model"], model)
                self.assertIn(mode, p["mode"])
                ram_gb = cen["ram"]["effective_mb"] / 1024.0
                self.assertEqual(dwell.dwell_default_s(ram_gb),
                                 dwell_s)
                self.assertEqual(
                    governor.budget_for(ram_gb)["storage_cap_mb"],
                    cap)

    def test_phone_floor_is_honest(self):
        # below every real fit the pairing still answers —
        # smallest model, nominal seat, script floor leading
        p = pairing.pair(profile(3072))
        self.assertIn("script floor leads", p["tier_basis"])

    def test_headless_box_pairs_and_dwells_safely(self):
        cen = profile(8192)  # no cameras, no audio at all
        p = pairing.pair(cen)
        self.assertEqual(p["model"], "qwen2.5:3b")
        with tempfile.TemporaryDirectory() as d:
            v = governor.assess(d, 8.0)
            self.assertEqual(v["used_mb"], 0.0)
            self.assertEqual(v["budget"]["storage_cap_mb"], 300)


class ChromebookFixtureTests(unittest.TestCase):
    """The reference laptop's two traps, as fixtures: twin
    video nodes under one camera name, and a mic that lives
    on a NAMED PipeWire source while 'default' is an empty
    port."""

    def test_twin_nodes_both_surface(self):
        with tempfile.TemporaryDirectory() as root:
            for node in ("video0", "video1"):
                d = os.path.join(root, node)
                os.makedirs(d)
                with open(os.path.join(d, "name"), "w") as f:
                    f.write("HP Wide Vision HD Camera\n")
            cams = census_mod.camera_probe(root)
            devices = sorted(c["device"] for c in cams)
            self.assertEqual(devices, ["/dev/video0",
                                       "/dev/video1"])

    def test_capture_chain_includes_named_sources(self):
        real = sound.pipewire_sources
        sound.pipewire_sources = lambda *a, **k: [
            "alsa_input.x.pro-input-0",
            "alsa_input.x.pro-input-1",
            "alsa_input.x.pro-input-8"]
        try:
            chain = sound.capture_inputs()
        finally:
            sound.pipewire_sources = real
        self.assertEqual(chain[0], ("pulse", "default"))
        self.assertIn(("pulse", "alsa_input.x.pro-input-1"),
                      chain)
        # the hearing source is walked BEFORE the raw fallbacks
        self.assertLess(
            chain.index(("pulse", "alsa_input.x.pro-input-1")),
            chain.index(("alsa", "default")))


if __name__ == "__main__":
    unittest.main()
