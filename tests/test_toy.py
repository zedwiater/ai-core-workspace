"""core.toy — the Eddy Toy's pure physics step."""
import random
import unittest

from tests import __init__ as _path  # noqa: F401
from core import toy


class TestPond(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(7)

    def test_spawn_inside_pond_sizes(self):
        e = toy.spawn(100, 100, rng=self.rng)
        self.assertTrue(13.0 <= e.r <= 24.0)
        self.assertFalse(e.big)

    def test_step_moves_and_stays_in_bounds(self):
        e = toy.spawn(5, 5, rng=self.rng)
        e.vx, e.vy = -50.0, -50.0
        out = toy.step([e], 200, 200, 1.0, rng=self.rng)
        self.assertEqual(len(out), 1)
        self.assertGreaterEqual(out[0].x, out[0].r)
        self.assertGreater(out[0].vx, 0)  # bounced off the wall

    def test_step_does_not_mutate_input(self):
        e = toy.spawn(100, 100, rng=self.rng)
        x0 = e.x
        toy.step([e], 400, 400, 0.5, rng=self.rng)
        self.assertEqual(e.x, x0)

    def test_bump_exchanges_motion(self):
        a = toy.Eddy(100, 100, 10.0, 0.0, 20.0, 1.0)
        b = toy.Eddy(135, 100, -10.0, 0.0, 20.0, 1.0)
        out = toy.step([a, b], 400, 400, 0.1, rng=random.Random(1))
        self.assertEqual(len(out), 2)
        self.assertLess(out[0].vx, 0)   # a now heads back left
        self.assertGreater(out[1].vx, 0)

    def test_deep_meeting_can_merge_big_and_disco(self):
        a = toy.Eddy(100, 100, 0.0, 0.0, 30.0, 1.0)
        b = toy.Eddy(105, 100, 0.0, 0.0, 30.0, 1.0)
        merged = None
        for seed in range(20):  # merge is a coin flip per meeting
            out = toy.step([a, b], 400, 400, 0.05,
                           rng=random.Random(seed))
            if len(out) == 1:
                merged = out[0]
                break
        self.assertIsNotNone(merged, "eddies never merged in 20 tries")
        self.assertGreater(merged.r, 30.0)
        self.assertTrue(merged.big)
        self.assertIn(merged.color(0.0), toy.DISCO)

    def test_small_eddy_color_is_pond(self):
        e = toy.spawn(50, 50, rng=self.rng)
        self.assertEqual(e.color(3.0), toy.POND)

    def test_poke_caps_the_pond(self):
        eddies = []
        for i in range(toy.MAX_EDDIES + 5):
            eddies = toy.poke(eddies, 50 + i, 50, rng=self.rng)
        self.assertLessEqual(len(eddies), toy.MAX_EDDIES)


if __name__ == "__main__":
    unittest.main()
