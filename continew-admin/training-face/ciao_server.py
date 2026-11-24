"""Scoped integration of the teammate's streaming AuthSession.

Original pose state machine and five-frame matching are reused. SQLite vectors,
account opt-in, single-actor checks and API-key authentication are integration rules.
"""
import os
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Header, HTTPException

from ciao_engine import initialize, models
from actor_continuity import ActorContinuity
from ciao_worker import FaceError, MODEL, decode, process
from face_auth.session import AuthSession
from service.session_store import SessionStore

HOME = Path(os.environ["TRAINING_FACE_HOME"])
KEY = os.environ.get("FACE_SERVICE_API_KEY", "")
capacity = threading.Lock()


class ScopedSessionStore(SessionStore):
    def invalidate_user(self, tenant, user):
        with self._guard:
            stale = [sid for sid, entry in self._sessions.items()
                     if entry.auth.tenant == tenant and str(user) in entry.auth.database]
            for sid in stale:
                del self._sessions[sid]


store = ScopedSessionStore(30, 120, 20)


class ScopedSession(AuthSession):
    def __init__(self, tenant, user):
        super().__init__("login", db_path=HOME / "unused.json")
        self.tenant = tenant
        process({"op": "status", "tenant": tenant, "user": 0}, HOME)
        with closing(sqlite3.connect(HOME / "private" / "templates-insightface.sqlite3")) as db:
            import sqlite_vec
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            db.enable_load_extension(False)
            rows = db.execute("""SELECT b.user,v.embedding FROM binding b
                JOIN face_vector v ON v.rowid=b.id
                LEFT JOIN face_identification i ON i.binding_id=b.id
                WHERE b.tenant=? AND b.model=? AND
                ((? > 0 AND b.user=?) OR (?=0 AND i.binding_id IS NOT NULL))""",
                (tenant, MODEL, user, user, user)).fetchall()
        self.database = {str(uid): {"embedding": np.frombuffer(vec, np.float32).tolist()}
                         for uid, vec in rows}
        if not self.database:
            raise FaceError("请先用密码登录，重新录入人脸并按需开启免输账号登录")
        self.continuity = ActorContinuity()
        self.identity_pause = None

    def _neutral(self, face):
        pose = getattr(face, "pose", None)
        if pose is None:
            return False
        pose = np.asarray(pose)
        if pose.shape != (3,) or not np.isfinite(pose).all():
            return False
        baseline = self.round["baseline_pose"]
        if baseline is None:
            return bool(np.max(np.abs(pose[:2])) <= 25)
        return bool(np.max(np.abs(np.deg2rad(pose[:2]) - baseline[:2])) <= 0.17)

    def accept(self, image):
        if self.phase == "done":
            raise FaceError("会话已结束，请重新验证")
        faces = models.detect(decode(image))
        if len(faces) != 1:
            self.continuity.gap()
            self.round["st"]["hold"] = 0
        if len(faces) == 1:
            now = time.monotonic()
            verdict = self.continuity.check(faces[0].normed_embedding, now, self._neutral(faces[0]))
            if verdict != "ok":
                self.round["st"]["hold"] = 0
                self.pending_name = None
                self.pending_count = 0
                if verdict in ("changed", "timeout"):
                    self.phase = "done"
                    self.result = ("连续检测到身份不一致，请重新验证" if verdict == "changed"
                                   else "画面持续不稳定，请正对摄像头后重新验证")
                elif self.identity_pause is None:
                    self.identity_pause = now
                result = self.snapshot()
                if verdict == "calibrating":
                    result["action"] = f"请正对摄像头，正在确认稳定画面（{len(self.continuity.samples)}/3）"
                elif verdict == "uncertain":
                    result["action"] = "画面暂不稳定，请稍微回正并保持清晰；当前动作尚未计入"
                return result
            if self.identity_pause is not None:
                # A bounded recovery pause must not consume the action timer.
                if self.round["phase"] == "challenge":
                    self.round["action_start"] += now - self.identity_pause
                self.identity_pause = None
        if self.phase == "liveness":
            self._step_liveness(faces)
        else:
            self._step_matching(faces)
        result = self.snapshot()
        if self.phase == "matching":
            result["action"] = "请回正并保持自然，" + result["action"]
        if self.phase == "liveness" and self.round["phase"] == "challenge":
            if not self.round["st"]["pose_armed"]:
                result["action"] = "请先回正，再按提示做动作：" + result["action"]
        return result


@asynccontextmanager
async def lifespan(app):
    if not KEY:
        raise RuntimeError("FACE_SERVICE_API_KEY is required")
    (HOME / "private").mkdir(parents=True, exist_ok=True)
    initialize(HOME)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"ready": models._instance is not None, "model": MODEL}


@app.post("/worker")
def worker(req: dict, x_api_key: str = Header(default="")):
    if not KEY or not secrets.compare_digest(KEY, x_api_key):
        raise HTTPException(401, "Invalid API key")
    try:
        op = req.get("op")
        if op == "session_start":
            with capacity:
                store.cleanup()
                if len(store._sessions) >= 16:
                    raise FaceError("识别服务繁忙，请稍后再试")
                sid = store.create(ScopedSession(int(req["tenant"]), int(req["user"])))
            return {"data": {"sessionId": sid}}
        if op == "session_frame":
            entry = store.get_entry(req["sessionId"])
            if entry is None:
                raise FaceError("会话已过期，请重新验证")
            with entry.lock:
                result = entry.auth.accept(req["image"])
                if result["done"]:
                    store.mark_done(req["sessionId"])
                return {"data": result}
        if op == "purge":
            with capacity:
                result = process(req, HOME)
                store.invalidate_user(int(req["tenant"]), int(req["user"]))
                return {"data": result}
        if op not in {"status", "quality", "bind", "unbind", "enable", "disable", "verify", "identify"}:
            raise FaceError("操作无效")
        return {"data": process(req, HOME)}
    except FaceError as error:
        return {"error": str(error)}
