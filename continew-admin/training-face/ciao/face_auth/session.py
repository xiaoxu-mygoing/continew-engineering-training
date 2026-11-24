"""人脸认证 — 注册 / 登录会话编排。

串联活体挑战（liveness）、特征采集/匹配（features / matcher）与模型推理（models）。
每个 AuthSession 实例维护独立状态，互不污染；模型为只读单例、推理加锁；
数据库写入加锁，并在写前重新读取、重新查重，避免并发覆盖。
"""

import threading
import time

from . import features, liveness, matcher, models
from .config import ACTION_TEXT, CONFIG, SAMPLE_COUNT, SAMPLE_INTERVAL, STABLE_FRAMES

# 数据库写锁：跨会话共享，避免并发写入覆盖
_db_lock = threading.Lock()


class AuthSession:
    """注册 / 登录会话状态机。

    mode: "register" | "login"。
    每帧调用 process(frame) 推进，返回状态快照 dict。
    不持有摄像头；帧由调用方采集后传入。
    """

    def __init__(self, mode, username=None, db_path=None):
        if mode not in ("register", "login"):
            raise ValueError(f"未知会话模式: {mode}")
        if mode == "register" and not username:
            raise ValueError("注册模式必须提供 username")

        self.mode = mode
        self.username = username
        self.db_path = db_path
        self.database = matcher.load_db(db_path)

        self.round = liveness.new_round()
        self.phase = "liveness"  # liveness -> collect(注册) / matching(登录) -> done
        self.result = None
        self.account = None  # 登录成功时为匹配账号，其余为 None

        # 注册：特征采集缓冲与节流
        self.embeddings = []
        self.last_capture = 0.0

        # 登录：稳定帧确认
        self.pending_name = None
        self.pending_count = 0
        self.confirmed_name = None
        self.confirmed_sim = 0.0

        # 注册：账号已存在则提前终态（沿用原脚本的重复注册校验）
        if self.mode == "register" and self.username in self.database:
            self.phase = "done"
            self.result = "该账号已经注册过人脸，请勿重复注册"

    # ==================== 每帧推进 ====================
    def process(self, frame):
        """处理一帧；返回当前状态快照。终态后重复调用不再变化。"""
        if self.phase == "done":
            return self.snapshot()

        faces = models.detect(frame)

        if self.phase == "liveness":
            self._step_liveness(faces)
        elif self.phase == "collect":
            self._step_collect(faces)
        elif self.phase == "matching":
            self._step_matching(faces)

        return self.snapshot()

    # ==================== 各阶段 ====================
    def _step_liveness(self, faces):
        status = liveness.step_round(self.round, faces)
        if status == "fail":
            self.phase = "done"
            self.result = f"活体挑战失败：{self.round['result']}"
        elif status == "success":
            self.phase = "collect" if self.mode == "register" else "matching"

    def _step_collect(self, faces):
        # 仅单张人脸时采样；无人脸/多人脸跳过本帧（与原脚本一致）
        if len(faces) != 1:
            return
        now = time.time()
        if now - self.last_capture >= SAMPLE_INTERVAL:
            self.embeddings.append(features.extract_embedding(faces[0]))
            self.last_capture = now
        if len(self.embeddings) >= SAMPLE_COUNT:
            self._finalize_register()

    def _step_matching(self, faces):
        if len(faces) != 1:
            self.pending_name = None
            self.pending_count = 0
            return
        embedding = features.extract_embedding(faces[0])
        best_name, best_sim = matcher.match_identity(embedding, self.database)

        if best_sim >= matcher.SIMILARITY_THRESHOLD:
            if best_name == self.pending_name:
                self.pending_count += 1
            else:
                self.pending_name = best_name
                self.pending_count = 1
            if self.pending_count >= STABLE_FRAMES:
                self.confirmed_name = best_name
                self.confirmed_sim = best_sim
                self.phase = "done"
                self.result = f"登录成功：{best_name}"
                self.account = best_name
        else:
            self.pending_name = None
            self.pending_count = 0

    # ==================== 注册落库 ====================
    def _finalize_register(self):
        embedding = features.fuse_embeddings(self.embeddings)
        with _db_lock:
            # 写前重新读取最新库并重新查重，避免并发覆盖 / 漏检
            database = matcher.load_db(self.db_path)
            if self.username in database:
                self.phase = "done"
                self.result = "该账号已经注册过人脸，请勿重复注册"
                return
            dup_name, _ = features.find_duplicate_face(embedding, database)
            if dup_name is not None:
                self.phase = "done"
                self.result = f"注册失败：人脸已关联账号 {dup_name}"
                return
            database[self.username] = {
                "embedding": embedding.tolist(),
                "dimension": int(len(embedding)),
                "sample_count": len(self.embeddings),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            matcher.save_db(database, self.db_path)
            self.phase = "done"
            self.result = f"注册成功：{self.username}"

    # ==================== 状态快照 ====================
    def snapshot(self):
        s = {
            "mode": self.mode,
            "phase": self.phase,
            "done": self.phase == "done",
            "result": self.result,
            "account": self.account,
        }
        if self.phase == "liveness":
            r = self.round
            if r["phase"] == "baseline":
                s["action"] = f"请正对摄像头（基线 {len(r['baseline'])}/{CONFIG['baseline_frames']}）"
            elif r["phase"] == "challenge":
                s["action"] = f"[{len(r['done'])}/{len(r['actions'])}] {ACTION_TEXT[r['current']]}"
            else:
                s["action"] = r["result"]
        elif self.phase == "collect":
            s["action"] = f"采集特征 {len(self.embeddings)}/{SAMPLE_COUNT}"
        elif self.phase == "matching":
            s["action"] = f"匹配中 [{self.pending_count}/{STABLE_FRAMES}]"
        return s
