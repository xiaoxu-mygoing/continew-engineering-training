"""Windows adapter for CiaoAmore16's persistent InsightFace model."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "ciao"))
from face_auth import models, features


def initialize(home):
    # Keep upstream locking and singleton inference; keep model files on D:.
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name="buffalo_l", root=str(home),
                       allowed_modules=["detection", "recognition", "landmark_3d_68"],
                       providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    models._instance = app


def extract(image, model_path, quality_only=False, engines=None):
    from ciao_worker import decode, FaceError
    faces = models.detect(decode(image))
    if len(faces) != 1:
        raise FaceError("请保持单人入镜并正对摄像头")
    if quality_only:
        return None
    vector = features.extract_embedding(faces[0]).astype(np.float32)
    if vector.shape != (512,) or not np.isfinite(vector).all():
        raise FaceError("无法提取有效人脸特征")
    return vector.tobytes()
