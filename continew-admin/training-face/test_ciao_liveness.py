"""Exercise the imported state machine without a camera or downloaded model."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "ciao"))
from face_auth import liveness
from face_auth.config import CONFIG


class LivenessTests(unittest.TestCase):
    def test_random_actions_and_static_face(self):
        r = liveness.new_round()
        self.assertEqual(3, len(set(r["actions"])))
        face = SimpleNamespace(pose=np.zeros(3))
        for _ in range(50):
            self.assertNotEqual("success", liveness.step_round(r, [face]))
        self.assertEqual([], r["done"])

    def test_neutral_gate_and_consecutive_hold(self):
        for action in liveness.ACTIONS:
            st = liveness.new_state()
            pose = np.zeros(3)
            axis = 1 if action.startswith("turn") else 0
            signs = CONFIG["yaw_sign"] if axis == 1 else CONFIG["pitch_sign"]
            pose[axis] = signs[action] * 0.4
            for _ in range(5):
                self.assertFalse(liveness.check_action(action, pose, st))
            self.assertFalse(liveness.check_action(action, np.zeros(3), st))
            self.assertFalse(liveness.check_action(action, pose, st))
            self.assertFalse(liveness.check_action(action, np.zeros(3), st))
            self.assertFalse(liveness.check_action(action, pose, st))
            self.assertFalse(liveness.check_action(action, pose, st))
            self.assertTrue(liveness.check_action(action, pose, st))

    def test_incomplete_action_does_not_advance(self):
        r = liveness.new_round()
        with patch.object(liveness.time, "time", return_value=100):
            for _ in range(10):
                liveness.step_round(r, [SimpleNamespace(pose=np.zeros(3))])
            original = r["current"]
            for _ in range(20):
                liveness.step_round(r, [SimpleNamespace(pose=np.zeros(3))])
            self.assertEqual(original, r["current"])
            self.assertEqual([], r["done"])
        with patch.object(liveness.time, "time", return_value=110):
            self.assertEqual("fail", liveness.step_round(r, [SimpleNamespace(pose=np.zeros(3))]))


if __name__ == "__main__":
    unittest.main()
