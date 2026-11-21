import unittest

from liveness import completed


class ActionTests(unittest.TestCase):
    neutral = (0.05, 0.05, 0.04)
    blink = (0.9, 0.9, 0.04)
    mouth = (0.05, 0.05, 0.8)

    def test_neutral_and_held_expression_photos_are_rejected(self):
        for value in (self.neutral, self.blink, self.mouth):
            for action in ("blink", "mouth"):
                self.assertFalse(completed([value] * 16, action))

    def test_complete_actions_require_matching_challenge(self):
        for action, value in (("blink", self.blink), ("mouth", self.mouth)):
            samples = [self.neutral] * 4 + [value] * 4 + [self.neutral] * 8
            self.assertTrue(completed(samples, action))
            self.assertFalse(completed(samples, "mouth" if action == "blink" else "blink"))

    def test_delayed_action_is_accepted_after_completion(self):
        self.assertFalse(completed([self.neutral] * 20, "blink"))
        self.assertTrue(completed([self.neutral] * 20 + [self.blink] * 3 + [self.neutral] * 4, "blink"))

    def test_missing_neutral_start_or_return_is_rejected(self):
        self.assertFalse(completed([self.blink] * 8 + [self.neutral] * 8, "blink"))
        self.assertFalse(completed([self.neutral] * 8 + [self.blink] * 8, "blink"))

    def test_one_frame_glitch_and_single_eye_closure_are_rejected(self):
        self.assertFalse(completed([self.neutral] * 4 + [self.blink] + [self.neutral] * 11, "blink"))
        self.assertFalse(completed([self.neutral] * 4 + [(0.9, 0.05, 0.04)] * 4 + [self.neutral] * 8, "blink"))


if __name__ == "__main__":
    unittest.main()
