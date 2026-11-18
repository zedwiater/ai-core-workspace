"""core.learn — sections and explainers carry all three layers."""
import unittest

from tests import __init__ as _path  # noqa: F401
from core import learn


class TestLearn(unittest.TestCase):
    def test_sections_cover_the_doors(self):
        ids = {s["id"] for s in learn.SECTIONS}
        for want in ("joy-calculator", "base-floor", "floors-gradients",
                     "redundancy", "free-tier", "plugs", "models",
                     "the-game"):
            self.assertIn(want, ids)

    def test_every_section_has_three_layers(self):
        for s in learn.SECTIONS:
            for layer in learn.LAYERS:
                self.assertTrue(s[layer].strip(),
                                f"{s['id']} missing {layer} layer")

    def test_explainers_three_layers_and_fallback(self):
        for key, entry in learn.EXPLAINERS.items():
            for layer in learn.LAYERS:
                self.assertEqual(learn.explainer(key, layer),
                                 entry[layer])
        self.assertEqual(learn.explainer("theme", "bogus-layer"),
                         learn.EXPLAINERS["theme"]["plain"])
        self.assertEqual(learn.explainer("no-such-key"), "")


if __name__ == "__main__":
    unittest.main()
