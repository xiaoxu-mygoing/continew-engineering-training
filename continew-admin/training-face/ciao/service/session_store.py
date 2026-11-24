"""人脸认证服务 — 内存会话存储与 TTL 回收。

每个会话持有一把独立锁，避免同一 AuthSession 并发 process 造成状态竞争；
不同会话锁相互独立，可并发处理。done 会话从 done_at 起算 DONE_TTL，查询不延长其保留时间。
"""

import threading
import time
import uuid


class SessionEntry:
    __slots__ = ("auth", "created_at", "last_access", "done_at", "lock")

    def __init__(self, auth):
        self.auth = auth
        self.created_at = time.monotonic()
        self.last_access = self.created_at
        self.done_at = None
        self.lock = threading.Lock()


class SessionStore:
    def __init__(self, idle_ttl, max_age, done_ttl):
        self._idle_ttl = idle_ttl
        self._max_age = max_age
        self._done_ttl = done_ttl
        self._sessions = {}
        self._guard = threading.Lock()

    def create(self, auth):
        sid = uuid.uuid4().hex
        with self._guard:
            self._sessions[sid] = SessionEntry(auth)
        return sid

    def _expired(self, entry, now):
        if entry.done_at is not None:
            return now - entry.done_at > self._done_ttl
        return (now - entry.last_access > self._idle_ttl) or \
               (now - entry.created_at > self._max_age)

    def get_entry(self, sid):
        with self._guard:
            entry = self._sessions.get(sid)
            if entry is None:
                return None
            now = time.monotonic()
            if self._expired(entry, now):
                del self._sessions[sid]
                return None
            # 仅未完成会话更新活跃时间；done 会话不延长保留时间
            if entry.done_at is None:
                entry.last_access = now
            return entry

    def mark_done(self, sid):
        with self._guard:
            entry = self._sessions.get(sid)
            if entry is not None and entry.done_at is None:
                entry.done_at = time.monotonic()

    def delete(self, sid):
        with self._guard:
            self._sessions.pop(sid, None)

    def cleanup(self):
        now = time.monotonic()
        with self._guard:
            expired = [sid for sid, e in self._sessions.items() if self._expired(e, now)]
            for sid in expired:
                del self._sessions[sid]
        return len(expired)
