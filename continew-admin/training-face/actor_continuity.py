"""Conservative continuity gate: rejected frames never advance a challenge."""
import numpy as np


class ActorContinuity:
    THRESHOLD = 0.4
    CALIBRATION_FRAMES = 3
    MISMATCH_FRAMES = 3
    RECOVERY_SECONDS = 4.0

    def __init__(self):
        self.reference = None
        self.samples = []
        self.mismatches = 0
        self.uncertain_since = None

    def gap(self):
        self.mismatches = 0
        if self.reference is None:
            self.samples.clear()

    def check(self, embedding, now, neutral):
        vector = np.asarray(embedding, dtype=np.float32)
        valid = vector.shape == (512,) and np.isfinite(vector).all()
        norm = float(np.linalg.norm(vector)) if valid else 0.0
        if norm > 0:
            vector = vector / norm
        if self.reference is None:
            if not valid or norm == 0 or not neutral:
                self.samples.clear()
                return "calibrating"
            # Auto-exposure / an unstable first frame can restart calibration;
            # no action evidence has been accumulated at this point.
            if self.samples and any(float(np.dot(v, vector)) < self.THRESHOLD for v in self.samples):
                self.samples.clear()
            self.samples.append(vector.copy())
            if len(self.samples) < self.CALIBRATION_FRAMES:
                return "calibrating"
            mean = np.mean(self.samples, axis=0)
            self.reference = mean / np.linalg.norm(mean)
            self.samples.clear()

        if self.uncertain_since is not None and now - self.uncertain_since >= self.RECOVERY_SECONDS:
            return "timeout"
        if valid and norm > 0 and float(np.dot(self.reference, vector)) >= self.THRESHOLD:
            self.mismatches = 0
            self.uncertain_since = None
            return "ok"
        # Never update the frozen reference with an untrusted frame.
        if self.uncertain_since is None:
            self.uncertain_since = now
        self.mismatches = self.mismatches + 1 if neutral and valid and norm > 0 else 0
        if self.mismatches >= self.MISMATCH_FRAMES:
            return "changed"
        if now - self.uncertain_since >= self.RECOVERY_SECONDS:
            return "timeout"
        return "uncertain"
