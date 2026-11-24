"""人脸认证 — 特征提取、融合归一化、重复人脸检测。

从 register_face.py 提取，供外部传入人脸检测结果复用。不加载模型、不打开摄像头。
"""

import numpy as np

# 人脸重复检测阈值（初始测试值，后续需要校准）
DUPLICATE_THRESHOLD = 0.45


def extract_embedding(face):
    """从外部传入的 InsightFace face 对象提取归一化 embedding。"""
    return face.normed_embedding.copy()


def fuse_embeddings(features):
    """融合多次采样特征：均值 + L2 归一化。"""
    embedding = np.mean(features, axis=0)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


def find_duplicate_face(new_embedding, database):
    """检测新的人脸特征是否与已有账号重复（点积，依赖双方均为归一化向量）。

    返回 (best_name, best_similarity)；低于阈值时 best_name 为 None。
    """
    best_name = None
    best_similarity = -1.0

    for name, info in database.items():
        old_embedding = np.asarray(
            info["embedding"], dtype=np.float32
        )

        similarity = float(np.dot(new_embedding, old_embedding))

        if similarity > best_similarity:
            best_similarity = similarity
            best_name = name

    if best_similarity >= DUPLICATE_THRESHOLD:
        return best_name, best_similarity

    return None, best_similarity
