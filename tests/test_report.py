"""The failure report: redaction is the feature. Nothing leaves
the machine in the tool itself, and what the user reviews must
already be stripped of home path, username and hostname."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from core import report


class TestReport(unittest.TestCase):
    def test_redact_strips_identity(self):
        text = "dezritawre@endevlapdez /home/dezritawre/app dezritawre"
        out = report.redact(text, user="dezritawre",
                            host="endevlapdez", home="/home/dezritawre")
        self.assertNotIn("dezritawre", out)
        self.assertNotIn("endevlapdez", out)
        self.assertNotIn("/home/", out)

    def test_render_sections(self):
        data = {"platform": "Linux-test", "python": "3.14",
                "crawl": {"threads": 4.0, "ram_gb": 7.6,
                          "gpus": ["Intel 0GB"],
                          "pairing": {"model": "qwen2.5:3b",
                                      "mode": "CPU seat",
                                      "gpu_layers": 0, "total_layers": 36},
                          "budget": 1},
                "services": {"ollama": "active"}, "door": None,
                "journal_ollama": "some log line", "coredump": ""}
        text = report.render(data)
        self.assertIn("SILENT", text)
        self.assertIn("qwen2.5:3b", text)
        self.assertIn("some log line", text)


if __name__ == "__main__":
    unittest.main()
