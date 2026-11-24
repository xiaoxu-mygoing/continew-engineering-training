"""Integration contracts with synthetic embeddings; no real biometric data."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

_temporary = tempfile.TemporaryDirectory()
os.environ["TRAINING_FACE_HOME"] = _temporary.name
os.environ["FACE_SERVICE_API_KEY"] = "test-only-not-a-runtime-key"
import ciao_engine
import ciao_server as server
import ciao_worker as worker


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        (self.home / "private").mkdir()
        self.vector = np.zeros(512, dtype=np.float32)
        self.vector[0] = 1
        self.patches = [patch.object(server, "HOME", self.home),
                        patch.object(ciao_engine, "extract", return_value=self.vector.tobytes())]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.directory.cleanup()

    def bind(self, tenant, user):
        worker.process({"op": "bind", "tenant": tenant, "user": user,
                        "version": 0, "image": "synthetic"}, self.home)

    def test_scoped_vectors_and_opt_in(self):
        self.bind(0, 1)
        self.bind(2, 3)
        self.assertEqual({"1"}, set(server.ScopedSession(0, 1).database))
        with self.assertRaises(worker.FaceError):
            server.ScopedSession(2, 1)
        with self.assertRaises(worker.FaceError):
            server.ScopedSession(0, 0)
        worker.process({"op": "enable", "tenant": 0, "user": 1, "version": 1}, self.home)
        self.assertEqual({"1"}, set(server.ScopedSession(0, 0).database))

    def test_http_key_is_required(self):
        from fastapi.testclient import TestClient
        with patch.object(server, "initialize"), TestClient(server.app) as client:
            request = {"op": "status", "tenant": 0, "user": 1}
            self.assertEqual(401, client.post("/worker", json=request).status_code)
            result = client.post("/worker", json=request,
                                 headers={"X-API-Key": server.KEY})
            self.assertEqual(200, result.status_code)
            self.assertFalse(result.json()["data"]["bound"])

    def test_purge_removes_only_target_template_and_invalidates_cached_sessions(self):
        self.bind(0, 1)
        self.bind(0, 2)
        self.bind(2, 1)
        worker.process({"op": "enable", "tenant": 0, "user": 1, "version": 1}, self.home)
        with patch.object(server, "store", server.ScopedSessionStore(30, 120, 20)):
            target = server.store.create(server.ScopedSession(0, 1))
            identify = server.store.create(server.ScopedSession(0, 0))
            other = server.store.create(server.ScopedSession(0, 2))
            other_tenant = server.store.create(server.ScopedSession(2, 1))
            request = {"op": "purge", "tenant": 0, "user": 1}
            self.assertEqual({"data": {"deleted": True}}, server.worker(request, server.KEY))
            self.assertEqual({"data": {"deleted": True}}, server.worker(request, server.KEY))
            self.assertIsNone(server.store.get_entry(target))
            self.assertIsNone(server.store.get_entry(identify))
            self.assertIsNotNone(server.store.get_entry(other))
            self.assertIsNotNone(server.store.get_entry(other_tenant))
        status = worker.process({"op": "status", "tenant": 0, "user": 1}, self.home)
        self.assertFalse(status["bound"])
        self.assertFalse(status["identificationEnabled"])
        self.assertEqual(0, status["templateVersion"])
        with self.assertRaisesRegex(worker.FaceError, "账号已删除"):
            self.bind(0, 1)
        self.assertEqual({"1"}, set(server.ScopedSession(2, 1).database))

    def test_matching_needs_five_consecutive_frames(self):
        self.bind(0, 1)
        session = server.ScopedSession(0, 1)
        session.phase = "matching"
        session.continuity.reference = self.vector.copy()
        face = SimpleNamespace(normed_embedding=self.vector, pose=np.zeros(3))
        with patch.object(server, "decode", return_value=None), patch.object(server.models, "detect", return_value=[face]):
            for _ in range(4):
                self.assertFalse(session.accept("frame")["done"])
            self.assertEqual("1", session.accept("frame")["account"])
            with self.assertRaises(worker.FaceError):
                session.accept("frame")

    def test_actor_swap_fails_before_matching(self):
        self.bind(0, 1)
        session = server.ScopedSession(0, 1)
        other = np.zeros(512, dtype=np.float32)
        other[1] = 1
        faces = [SimpleNamespace(normed_embedding=self.vector, pose=np.zeros(3)),
                 SimpleNamespace(normed_embedding=other, pose=np.zeros(3))]
        with patch.object(server, "decode", return_value=None), patch.object(server.models, "detect", side_effect=[[faces[0]]] * 3 + [[faces[1]]] * 3):
            for _ in range(5):
                self.assertFalse(session.accept("frame")["done"])
            result = session.accept("changed")
            self.assertTrue(result["done"])
            self.assertIsNone(result["account"])

    def test_bad_motion_frame_does_not_advance_and_can_recover(self):
        self.bind(0, 1)
        session = server.ScopedSession(0, 1)
        session.continuity.reference = self.vector.copy()
        session.round.update(phase="challenge", current="turn_left", actions=["turn_left", "look_up", "look_down"],
                             baseline_pose=np.zeros(3), action_start=100)
        session.round["st"] = {"hold": 2, "pose_armed": True}
        other = np.zeros(512, dtype=np.float32)
        other[1] = 1
        blurred = SimpleNamespace(normed_embedding=other, pose=np.array([0, 25, 0]))
        clear = SimpleNamespace(normed_embedding=self.vector, pose=np.zeros(3))
        with patch.object(server, "decode", return_value=None), patch.object(server.models, "detect", side_effect=[[blurred], [clear]]), patch("time.time", return_value=101), patch.object(server.time, "monotonic", side_effect=[10, 11]):
            result = session.accept("blurred")
            self.assertFalse(result["done"])
            self.assertIn("暂不稳定", result["action"])
            self.assertEqual([], session.round["done"])
            self.assertEqual(0, session.round["st"]["hold"])
            result = session.accept("clear")
            self.assertFalse(result["done"])
            self.assertEqual("turn_left", session.round["current"])
            self.assertEqual(101, session.round["action_start"])

    def test_bad_matching_frame_resets_identity_streak(self):
        self.bind(0, 1)
        session = server.ScopedSession(0, 1)
        session.continuity.reference = self.vector.copy()
        session.phase = "matching"
        session.pending_count = 4
        session.pending_name = "1"
        other = np.zeros(512, dtype=np.float32)
        other[1] = 1
        faces = [SimpleNamespace(normed_embedding=other, pose=np.zeros(3)),
                 SimpleNamespace(normed_embedding=self.vector, pose=np.zeros(3))]
        with patch.object(server, "decode", return_value=None), patch.object(server.models, "detect", side_effect=[[faces[0]], [faces[1]]]):
            self.assertFalse(session.accept("bad")["done"])
            self.assertEqual(0, session.pending_count)
            self.assertFalse(session.accept("good")["done"])
            self.assertEqual(1, session.pending_count)


if __name__ == "__main__":
    unittest.main()
