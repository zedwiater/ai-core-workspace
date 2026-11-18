"""The Joy setup finish (Zak's play session, 2026-11-17):
'nothing really finishes joy setup just ends at last question
only button is go back.' The summary page now carries an
explicit Finish act and a completion page of its own."""
import os
import unittest

SRC = open(os.path.join(os.path.dirname(__file__), "..",
                        "source", "app", "ai-client.py")).read()


class FinishWiringTests(unittest.TestCase):
    def test_finish_button_exists_and_is_summary_only(self):
        self.assertIn("calc_done_btn = Gtk.Button", SRC)
        self.assertIn('self.calc_done_btn.set_visible(kind == "summary")',
                      SRC)

    def test_done_page_registered_and_reachable(self):
        self.assertIn('add_named(self._build_calc_done_page(), "done")',
                      SRC)
        self.assertIn('self._calc_show_special("done")', SRC)
        self.assertIn('"Setup complete"', SRC)

    def test_finish_saves_then_says_so(self):
        body = SRC[SRC.index("def _calc_finish"):]
        body = body[:body.index("def _calc_show_page")
                     if "def _calc_show_page" in body else 1200]
        self.assertIn("_calc_refresh_summary()", body)
        self.assertIn("Setup complete — saved", body)

    def test_special_pages_hide_the_finish_button(self):
        self.assertIn("self.calc_next_btn, self.calc_done_btn", SRC)


if __name__ == "__main__":
    unittest.main()
