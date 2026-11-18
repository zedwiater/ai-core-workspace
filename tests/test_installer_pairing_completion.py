"""The installer completes the base function (Zak, 2026-11-18):
size, download, install, seat, balanced settings — even when
the shelf already holds other models. And in merge mode it
stays hands-off an owner's shelf."""
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = open(os.path.join(ROOT, "install.sh")).read()


class PairingCompletionTests(unittest.TestCase):
    def test_paired_model_pulled_when_missing_not_only_when_empty(self):
        self.assertIn("PAIRED_PRESENT", SRC)
        self.assertIn('case " $EXISTING_MODELS " in', SRC)
        self.assertNotIn("Empty shelf — pulling the paired model",
                         SRC)

    def test_talking_model_rebuilt_when_its_base_is_not_the_pair(self):
        self.assertIn("parent_model", SRC)
        self.assertIn('TALKING_PARENT" != "$OPTIMAL_MODEL"', SRC)

    def test_balanced_settings_ride_the_talking_model(self):
        self.assertIn("PARAMETER temperature 0.6", SRC)
        self.assertIn("PARAMETER num_gpu", SRC)

    def test_merge_mode_stays_hands_off(self):
        merge_at = SRC.index('if [ -n "$OWNER_DROPINS" ]; then\n'
                             '        PICK=')
        pull_at = SRC.index('su - "$REAL_USER" -c "ollama pull')
        self.assertLess(merge_at, pull_at)

    def test_seat_is_proven_and_counted(self):
        self.assertIn("Seated and proven in ollama ps", SRC)
        self.assertIn("SEAT_CHECKED", SRC)
        self.assertIn("talking model seated (proven in ollama ps)",
                      SRC)
        self.assertIn("INCOMPLETE: the talking model did not seat",
                      SRC)


if __name__ == "__main__":
    unittest.main()
