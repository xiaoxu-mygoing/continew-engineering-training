"""人脸认证 — InsightFace 模型单例加载与复用。

buffalo_l 一次推理同时输出检测框、关键点姿态（face.pose）与识别特征（face.normed_embedding）。
get_app 返回全局唯一实例；detect 加锁执行推理，供多会话安全复用。
"""

import threading

from insightface.app import FaceAnalysis

MODEL_NAME = "buffalo_l"
PROVIDERS = ["CUDAExecutionProvider", "CPUExecutionProvider"]
DET_SIZE = (640, 640)

_instance = None
_infer_lock = threading.Lock()


def get_app():
    """返回全局唯一 FaceAnalysis 实例；首次调用时加载并 prepare（双检锁）。"""
    global _instance
    if _instance is None:
        with _infer_lock:
            if _instance is None:
                app = FaceAnalysis(name=MODEL_NAME, providers=PROVIDERS)
                app.prepare(ctx_id=0, det_size=DET_SIZE)
                _instance = app
    return _instance


def detect(frame):
    """加锁执行人脸检测，返回 faces（每个 face 含 .pose 与 .normed_embedding）。"""
    app = get_app()
    with _infer_lock:
        return app.get(frame)
