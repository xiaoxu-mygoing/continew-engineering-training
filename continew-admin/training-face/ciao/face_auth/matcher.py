"""人脸认证 — face_db.json 读写、余弦相似度、1:N 身份匹配。

从 login_face.py 提取。不加载模型、不打开摄像头；
稳定帧累计与会话逻辑保留给 session.py。
"""

import json
from pathlib import Path

import numpy as np

# ===== 可调参数 =====
SIMILARITY_THRESHOLD = 0.4   # 余弦相似度阈值，>= 判为同一人
DB_PATH = Path("data") / "face_db.json"


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def build_vectors(database):
    """将 face_db.json 记录转为 {name: float32 向量}。"""
    return {
        name: np.asarray(info["embedding"], dtype=np.float32)
        for name, info in database.items()
    }


def match_identity(embedding, database):
    """1:N 匹配，返回最相似账号 (best_name, best_sim)。

    不在此处叠加阈值判定；阈值比较与稳定帧累计由调用方（session.py）处理，
    对应 login_face.py 中循环内的阈值分支。
    """
    best_name, best_sim = None, -1.0
    for name, vec in build_vectors(database).items():
        sim = cosine(embedding, vec)
        if sim > best_sim:
            best_sim = sim
            best_name = name
    return best_name, best_sim


def load_db(path=None):
    """读取 face_db.json；不存在时返回空字典。"""
    p = Path(path) if path is not None else DB_PATH
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_db(database, path=None):
    """写入 face_db.json。"""
    p = Path(path) if path is not None else DB_PATH
    p.parent.mkdir(exist_ok=True)
    p.write_text(
        json.dumps(database, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
