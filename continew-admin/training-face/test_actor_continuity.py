import unittest

import numpy as np

from actor_continuity import ActorContinuity


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.person = np.eye(1, 512, dtype=np.float32)[0]
        self.other = np.roll(self.person, 1)
        self.guard = ActorContinuity()

    def calibrate(self):
        for i in range(3):
            result = self.guard.check(self.person, i / 10, True)
        self.assertEqual("ok", result)

    def test_unstable_first_frame_does_not_become_reference(self):
        self.assertEqual("calibrating", self.guard.check(self.other, 0, True))
        self.calibrate()
        np.testing.assert_allclose(self.guard.reference, self.person)

    def test_motion_outlier_is_not_admitted_or_learned(self):
        self.calibrate()
        self.assertEqual("uncertain", self.guard.check(self.other, 1, False))
        self.assertEqual("ok", self.guard.check(self.person, 2, True))
        np.testing.assert_allclose(self.guard.reference, self.person)

    def test_three_neutral_mismatches_fail(self):
        self.calibrate()
        for t in (1, 2):
            self.assertEqual("uncertain", self.guard.check(self.other, t, True))
        self.assertEqual("changed", self.guard.check(self.other, 3, True))

    def test_motion_mismatch_and_late_return_expire(self):
        self.calibrate()
        self.assertEqual("uncertain", self.guard.check(self.other, 1, False))
        self.assertEqual("timeout", self.guard.check(self.person, 5, True))

    def test_invalid_vector_cannot_authenticate(self):
        self.calibrate()
        self.assertEqual("uncertain", self.guard.check(np.full(512, np.nan), 1, True))


if __name__ == "__main__":
    unittest.main()
