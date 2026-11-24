"""One private request per process. Only the Java backend invokes this worker."""
import base64
import binascii
import io
import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import sqlite_vec

MODEL = "sface-2021dec"
MAX_IMAGE_CHARS = 450000
NO_MATCH = "验证未通过，可重试或使用密码登录"
IDENTIFY_THRESHOLD = 0.52
IDENTIFY_MIN_LEAD = 0.08


class FaceError(Exception):
    pass


def decode(image):
    import cv2
    import numpy as np
    from PIL import Image, UnidentifiedImageError

    if not isinstance(image, str) or not 0 < len(image) <= MAX_IMAGE_CHARS:
        raise FaceError("采集画面大小无效，请重新拍摄")
    try:
        raw = base64.b64decode(image, validate=True)
        with Image.open(io.BytesIO(raw)) as header:
            w, h = header.size
            if header.format != "JPEG" or min(w, h) < 80 or max(w, h) > 1280:
                raise FaceError("请使用摄像头采集有效的 JPEG 画面")
    except (ValueError, binascii.Error, UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise FaceError("无法读取画面，请重新采集") from None
    cv2.setNumThreads(2)
    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise FaceError("画面损坏，请重新采集")
    if cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean() < 38:
        raise FaceError("光线过暗，请面向光源后重新采集")
    return frame


def extract(image, models, quality_only=False, engines=None):
    import cv2
    import numpy as np

    frame = decode(image)
    detector = engines[0] if engines else cv2.FaceDetectorYN.create(
        str(models / "face_detection_yunet_2023mar.onnx"), "", (frame.shape[1], frame.shape[0]), 0.85)
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)
    if faces is None or not len(faces):
        raise FaceError("未检测到人脸，请正对并靠近摄像头")
    if len(faces) != 1:
        raise FaceError("检测到多张人脸，请仅保留本人入镜")
    if min(faces[0][2:4]) < 55:
        raise FaceError("人脸过小，请靠近摄像头")
    if quality_only:
        return None
    recognizer = engines[1] if engines else cv2.FaceRecognizerSF.create(
        str(models / "face_recognition_sface_2021dec.onnx"), "")
    aligned = recognizer.alignCrop(frame, faces[0])
    feature = recognizer.feature(aligned).flatten().astype(np.float32)
    if feature.shape != (128,) or not np.isfinite(feature).all():
        raise FaceError("提取特征失败，请重新采集")
    return feature.tobytes()


def process(req, home):
    op = req["op"]
    if op == "liveness":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from liveness import verify
        return verify(req, home / "models", decode, extract, FaceError)
    owner = (int(req["tenant"]), int(req["user"]))
    database = home / "private" / "templates.sqlite3"
    if op == "purge" and owner[1] <= 0:
        raise FaceError("账号无效")
    if op == "quality":
        try:
            extract(req["image"], home / "models", quality_only=True)
            return {"hint": "画面合格，可以确认录入"}
        except FaceError as error:
            return {"hint": str(error)}
    vector = extract(req["image"], home / "models") if op in ("bind", "verify", "identify") else None
    with closing(sqlite3.connect(database, timeout=5)) as db:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        db.execute("PRAGMA secure_delete=ON")
        db.execute("""CREATE TABLE IF NOT EXISTS binding (
            id INTEGER PRIMARY KEY, tenant INTEGER NOT NULL, user INTEGER NOT NULL,
            version INTEGER NOT NULL, model TEXT, updated TEXT NOT NULL, UNIQUE(tenant,user))""")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS face_vector USING vec0(embedding float[128])")
        db.execute("CREATE TABLE IF NOT EXISTS face_identification (binding_id INTEGER PRIMARY KEY)")
        db.execute("""CREATE TABLE IF NOT EXISTS retired_face_account (
            tenant INTEGER NOT NULL, user INTEGER NOT NULL, PRIMARY KEY(tenant,user))""")
        db.execute("BEGIN IMMEDIATE" if op in ("bind", "unbind", "enable", "disable", "purge") else "BEGIN")
        if op == "identify":
            hits = db.execute("""SELECT b.user, 1 - vec_distance_cosine(v.embedding, ?) AS score
                FROM binding b JOIN face_identification i ON i.binding_id=b.id
                CROSS JOIN face_vector v WHERE b.tenant=? AND b.model=? AND v.rowid=b.id
                ORDER BY score DESC LIMIT 2""", (vector, owner[0], MODEL)).fetchall()
            if not hits or hits[0][1] is None or not hits[0][1] >= IDENTIFY_THRESHOLD:
                raise FaceError(NO_MATCH)
            if len(hits) > 1 and (hits[1][1] is None or not hits[0][1] - hits[1][1] >= IDENTIFY_MIN_LEAD):
                raise FaceError(NO_MATCH)
            return {"userId": hits[0][0]}
        row = db.execute("""SELECT b.id,b.version,b.model,b.updated,i.binding_id FROM binding b
            LEFT JOIN face_identification i ON i.binding_id=b.id WHERE b.tenant=? AND b.user=?""", owner).fetchone()
        if op == "purge":
            db.execute("INSERT OR IGNORE INTO retired_face_account (tenant,user) VALUES (?,?)", owner)
            if row:
                db.execute("DELETE FROM face_identification WHERE binding_id=?", (row[0],))
                db.execute("DELETE FROM face_vector WHERE rowid=?", (row[0],))
                db.execute("DELETE FROM binding WHERE id=?", (row[0],))
            db.commit()
            return {"deleted": True}
        if op == "bind" and db.execute("SELECT 1 FROM retired_face_account WHERE tenant=? AND user=?", owner).fetchone():
            raise FaceError("账号已删除")
        version = row[1] if row else 0
        bound = bool(row and row[2])
        enabled = bool(bound and row[4] is not None)
        if op == "status":
            return {"bound": bound, "templateVersion": version, "updatedAt": row[3] if row else None,
                    "identificationEnabled": enabled}
        if op == "verify":
            if not bound or row[2] != MODEL:
                raise FaceError(NO_MATCH)
            result = db.execute("SELECT vec_distance_cosine(embedding, ?) FROM face_vector WHERE rowid=?",
                                (vector, row[0])).fetchone()
            # SFace cosine similarity = 1 - cosine distance.
            if not result or result[0] is None or not 1 - result[0] >= 0.40:
                raise FaceError(NO_MATCH)
            return {"matched": True}
        if op not in ("bind", "unbind", "enable", "disable"):
            raise FaceError("操作无效")
        if req["version"] != version or (op != "bind" and not bound):
            raise FaceError("绑定状态已变更，请刷新后重试")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if op in ("enable", "disable"):
            if op == "enable":
                db.execute("INSERT OR IGNORE INTO face_identification(binding_id) VALUES(?)", (row[0],))
            else:
                db.execute("DELETE FROM face_identification WHERE binding_id=?", (row[0],))
            db.execute("UPDATE binding SET version=?,updated=? WHERE id=?", (version + 1, now, row[0]))
            db.commit()
            return {"bound": True, "identificationEnabled": op == "enable", "templateVersion": version + 1,
                    "updatedAt": now}
        model = MODEL if op == "bind" else None
        if row:
            rowid = row[0]
            if op == "unbind":
                db.execute("DELETE FROM face_identification WHERE binding_id=?", (rowid,))
            db.execute("DELETE FROM face_vector WHERE rowid=?", (rowid,))
            db.execute("UPDATE binding SET version=?,model=?,updated=? WHERE id=?",
                       (version + 1, model, now, rowid))
        else:
            rowid = db.execute("INSERT INTO binding(tenant,user,version,model,updated) VALUES(?,?,1,?,?)",
                               (*owner, model, now)).lastrowid
        if vector is not None:
            db.execute("INSERT INTO face_vector(rowid,embedding) VALUES(?,?)", (rowid, vector))
        db.commit()
        return {"bound": model is not None, "identificationEnabled": model is not None and enabled,
                "templateVersion": version + 1, "updatedAt": now}


if __name__ == "__main__":
    try:
        data = process(json.load(sys.stdin), Path(os.environ["TRAINING_FACE_HOME"]))
        print(json.dumps({"data": data}))
    except FaceError as error:
        print(json.dumps({"error": str(error)}))
    except Exception:
        print(json.dumps({"error": "本地人脸识别服务不可用，请检查模型与运行环境"}))
