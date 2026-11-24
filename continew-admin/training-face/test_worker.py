"""Template lifecycle regression checks using synthetic, non-biometric vectors."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import worker


class TemplateLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        (self.home / "private").mkdir()

        def features(image, models):
            vector = np.zeros(128, dtype=np.float32)
            vector[int(image)] = 1
            return vector.tobytes()

        extractor = patch.object(worker, "extract", side_effect=features)
        extractor.start()
        self.addCleanup(extractor.stop)

    def call(self, op, tenant=1, user=2, version=0, image="0"):
        return worker.process(dict(op=op, tenant=tenant, user=user, version=version, image=image), self.home)

    def test_verify_is_scoped_to_tenant_and_owner(self):
        self.call("bind")
        self.assertTrue(self.call("verify")["matched"])
        for scope in [dict(tenant=3), dict(user=4), dict(image="1")]:
            with self.assertRaises(worker.FaceError):
                self.call("verify", **scope)

    def test_purge_is_idempotent_and_prevents_late_enrollment(self):
        self.call("bind")
        self.call("enable", version=1)
        self.call("bind", tenant=3)
        self.assertTrue(self.call("purge")["deleted"])
        self.assertTrue(self.call("purge")["deleted"])
        self.assertEqual(0, self.call("status")["templateVersion"])
        with self.assertRaisesRegex(worker.FaceError, "账号已删除"):
            self.call("bind")
        self.assertTrue(self.call("verify", tenant=3)["matched"])

    def test_replacement_and_unbinding_invalidate_old_credentials(self):
        self.call("bind")
        self.call("bind", version=1, image="1")
        with self.assertRaises(worker.FaceError):
            self.call("unbind", version=1)
        with self.assertRaises(worker.FaceError):
            self.call("verify", image="0")
        self.assertTrue(self.call("verify", image="1")["matched"])
        self.call("unbind", version=2)
        self.assertFalse(self.call("status")["bound"])
        with self.assertRaises(worker.FaceError):
            self.call("verify", image="1")
        with self.assertRaises(worker.FaceError):
            self.call("bind", version=0)
        self.assertEqual(self.call("bind", version=3)["templateVersion"], 4)

    def test_identify_only_unique_opted_in_accounts_in_current_tenant(self):
        self.call("bind")
        with self.assertRaises(worker.FaceError):
            self.call("identify")
        self.call("enable", version=1)
        self.call("bind", user=3, image="1")
        self.call("enable", user=3, version=1)
        self.call("bind", tenant=9)
        self.call("enable", tenant=9, version=1)
        self.assertEqual(self.call("identify")["userId"], 2)
        self.assertEqual(self.call("identify", image="1")["userId"], 3)
        with self.assertRaises(worker.FaceError):
            self.call("identify", image="2")
        self.call("bind", user=4)
        self.call("enable", user=4, version=1)
        with self.assertRaises(worker.FaceError):
            self.call("identify")
        self.call("disable", user=4, version=2)
        self.assertEqual(self.call("identify")["userId"], 2)
        self.call("unbind", version=2)
        self.call("bind", version=3)
        with self.assertRaises(worker.FaceError):
            self.call("identify")
        self.assertTrue(self.call("verify")["matched"])


if __name__ == "__main__":
    unittest.main()
