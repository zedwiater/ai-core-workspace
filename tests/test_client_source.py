"""Source-order guards for the client: things that only work if
they happen before something else in the file."""
import os, unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "source", "app",
                   "ai-client.py")


class TestClientSource(unittest.TestCase):
    def test_renderer_default_precedes_gtk_versions(self):
        text = open(SRC).read()
        self.assertLess(text.index("GSK_RENDERER"),
                        text.index("gi.require_version"))


if __name__ == "__main__":
    unittest.main()
