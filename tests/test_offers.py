"""The command-offering layer (Zak, 2026-11-18): diagnosis
must end in a prescription — the exact command, offered in
the app, re-checked by the app after the user runs it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import offers  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class FakeRunner:
    def __init__(self, table):
        self.table = table

    def __call__(self, cmd, **kw):
        class R:
            pass
        r = R()
        r.returncode, r.stdout, r.stderr = self.table.get(
            cmd[0], (1, "", ""))
        return r


def no_ollama(url, timeout=0):
    raise OSError("down")


def ok_ollama(url, timeout=0):
    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return Resp()


class DetectTests(unittest.TestCase):
    def base(self, **over):
        kw = dict(
            runner=FakeRunner({"ffmpeg": (0, "ffmpeg version 6", ""),
                               "docker": (0, "", "")}),
            which=lambda name: f"/usr/bin/{name}",
            globber=lambda pat: [],
            access=lambda p, m: True,
            opener=ok_ollama)
        kw.update(over)
        return kw

    def test_healthy_machine_offers_nothing(self):
        self.assertEqual(offers.detect(**self.base()), [])

    def test_broken_ffmpeg_on_arch_offers_full_update(self):
        kw = self.base(runner=FakeRunner(
            {"ffmpeg": (127, "", "error while loading shared "
                                 "libraries: libplacebo.so.387"),
             "docker": (0, "", "")}))
        found = offers.detect(**kw)
        self.assertEqual([o["id"] for o in found], ["ffmpeg"])
        self.assertEqual(found[0]["commands"],
                         ["sudo pacman -Syu"])
        self.assertEqual(found[0]["check"], "ffmpeg_ok")

    def test_missing_ffmpeg_on_debian_offers_install(self):
        kw = self.base(
            which=lambda name: (None if name == "ffmpeg"
                                else f"/usr/bin/{name}"))
        kw["runner"] = FakeRunner({"docker": (0, "", "")})
        # pacman absent in this world: apt rules
        kw["which"] = lambda name: (
            None if name in ("ffmpeg", "pacman")
            else f"/usr/bin/{name}")
        found = offers.detect(**kw)
        self.assertEqual(found[0]["commands"],
                         ["sudo apt update && "
                          "sudo apt install -y ffmpeg"])

    def test_docker_denied_offers_group_command(self):
        kw = self.base(runner=FakeRunner(
            {"ffmpeg": (0, "v", ""),
             "docker": (1, "", "permission denied while trying "
                              "to connect")}))
        found = offers.detect(**kw)
        self.assertEqual([o["id"] for o in found],
                         ["docker-group"])
        self.assertEqual(found[0]["commands"],
                         ["sudo usermod -aG docker $USER"])
        self.assertEqual(found[0]["reach"], "docker")

    def test_video_denied_and_ollama_down(self):
        kw = self.base(
            globber=lambda pat: ["/dev/video0"],
            access=lambda p, m: False,
            opener=no_ollama)
        found = offers.detect(**kw)
        self.assertEqual({o["id"] for o in found},
                         {"video-group", "ollama-down"})
        vid = offers.for_reach(found, "cameras")
        self.assertEqual(vid["commands"],
                         ["sudo usermod -aG video $USER"])

    def test_every_offer_carries_explainer_and_disclaimer(self):
        scenarios = [
            self.base(runner=FakeRunner(
                {"ffmpeg": (127, "", "libplacebo.so.387"),
                 "docker": (1, "", "permission denied")})),
            self.base(globber=lambda p: ["/dev/video0"],
                      access=lambda p, m: False,
                      opener=no_ollama),
            self.base(update_probe=lambda: {"state": "behind",
                                            "behind": 3}),
        ]
        seen = set()
        for kw in scenarios:
            for offer in offers.detect(**kw):
                seen.add(offer["id"])
                self.assertTrue(offer["explainer"])
                self.assertIn("never runs these commands",
                              offer["disclaimer"])
        self.assertEqual(seen, {"ffmpeg", "docker-group",
                                "video-group", "ollama-down",
                                "app-update"})

    def test_library_is_history_grounded_and_complete(self):
        lib = offers.library(src="/home/x/ai-core-workspace")
        ids = {e["id"] for e in lib}
        self.assertIn("merge-escape", ids)
        self.assertIn("manual-update", ids)
        self.assertIn("auto-update-off", ids)
        for entry in lib:
            self.assertTrue(entry["when"])
            self.assertTrue(entry["commands"])
            self.assertTrue(entry["explainer"])
        merge = next(e for e in lib if e["id"] == "merge-escape")
        # the backup comes FIRST — nothing is lost
        self.assertIn("cp /etc/systemd", merge["commands"][0])
        refresh = next(e for e in lib
                       if e["id"] == "manual-refresh")
        self.assertIn("/home/x/ai-core-workspace",
                      refresh["commands"][0])
        text = offers.library_text(src="/home/x")
        self.assertIn("double-check it online", text)
        self.assertIn("sudo ai-core-update", text)

    def test_run_check(self):
        self.assertTrue(offers.run_check(
            "ffmpeg_ok",
            runner=FakeRunner({"ffmpeg": (0, "v", "")}),
            which=lambda n: "/usr/bin/ffmpeg"))
        self.assertFalse(offers.run_check("nonsense"))


class WiringTests(unittest.TestCase):
    def test_pages_carry_the_layer(self):
        src = open(os.path.join(
            ROOT, "source", "app", "conduit_pages.py")).read()
        self.assertIn("offers_mod.detect()", src)
        self.assertIn("Things only you can run", src)
        self.assertIn("Check again", src)
        self.assertIn("for_reach", src)


if __name__ == "__main__":
    unittest.main()
