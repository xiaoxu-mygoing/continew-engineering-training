"""人脸认证服务 — 接口与存储测试（不依赖摄像头 / 不加载真实模型）。

- SessionStore：TTL 过期、done_at 保留、锁隔离。
- AuthSession：注册账号已存在的提前终态（无需模型）。
- HTTP 接口：路由、鉴权、大小限制、异常处理（通过 stub 掉 models.detect 避免加载模型）。

运行：.venv-face/Scripts/python.exe -m service.test_service
"""

import json
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from . import config
from .app import app
from .session_store import SessionStore

# 记录测试结果
_PASS = []
_FAIL = []


def check(name, cond):
    if cond:
        _PASS.append(name)
        print(f"  PASS  {name}")
    else:
        _FAIL.append(name)
        print(f"  FAIL  {name}")


def _jpeg_bytes(w=16, h=16):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def test_session_store():
    print("\n[SessionStore]")
    store = SessionStore(idle_ttl=0.15, max_age=0.15, done_ttl=0.2)

    class FakeAuth:
        pass

    a1, a2 = FakeAuth(), FakeAuth()
    s1 = store.create(a1)
    s2 = store.create(a2)
    check("create 返回不同 session_id", s1 != s2)

    e1 = store.get_entry(s1)
    check("get_entry 命中", e1 is not None and e1.auth is a1)
    check("不同会话锁相互独立", e1.lock is not store.get_entry(s2).lock)
    check("会话锁为 threading.Lock", isinstance(e1.lock, type(threading.Lock())))

    # 未完成会话：空闲超时过期
    time.sleep(0.2)
    check("空闲超时后过期", store.get_entry(s1) is None)

    # done 会话：从 done_at 起算，且 get_entry 不延长保留时间
    s3 = store.create(FakeAuth())
    store.mark_done(s3)
    check("done 会话在保留期内可查", store.get_entry(s3) is not None)
    time.sleep(0.25)
    check("done 会话超过 DONE_TTL 后过期", store.get_entry(s3) is None)

    # delete / cleanup
    s4 = store.create(FakeAuth())
    store.delete(s4)
    check("delete 后 get_entry 为 None", store.get_entry(s4) is None)

    dead = store.create(FakeAuth())
    time.sleep(0.2)
    n = store.cleanup()
    check("cleanup 清理过期会话", n >= 1 and store.get_entry(dead) is None)


def test_authsession_early_terminal():
    print("\n[AuthSession 提前终态]")
    from face_auth.session import AuthSession

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "face_db.json"
        db.write_text(json.dumps({"alice": {"embedding": [0.0], "dimension": 1,
                                            "sample_count": 1, "created_at": "x"}}),
                       encoding="utf-8")
        s = AuthSession("register", username="alice", db_path=db)
        check("注册已存在账号 -> 提前 done", s.phase == "done")
        check("提示重复注册", "已经注册过" in (s.result or ""))


def test_login_account_field():
    print("\n[登录成功 account 字段]")
    import face_auth.matcher as fmatch
    import face_auth.models as fm
    from face_auth.session import AuthSession

    class FakeFace:
        normed_embedding = np.zeros(512, dtype=np.float32)

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "face_db.json"
        db.write_text(json.dumps({"bob": {"embedding": [0.0], "dimension": 1,
                                          "sample_count": 1, "created_at": "x"}}),
                       encoding="utf-8")

        # 初始快照 account 为 None
        s0 = AuthSession("login", db_path=db)
        check("初始快照 account=None", s0.snapshot().get("account") is None)

        # 驱动登录匹配成功，验证 account 被结构化填充
        s = AuthSession("login", db_path=db)
        s.phase = "matching"  # 跳过活体，直接进入匹配阶段
        orig_detect = fm.detect
        orig_match = fmatch.match_identity
        try:
            fm.detect = lambda frame: [FakeFace()]
            fmatch.match_identity = lambda emb, database: ("bob", 0.9)
            for _ in range(5):
                s.process(np.zeros((10, 10, 3), dtype=np.uint8))
        finally:
            fm.detect = orig_detect
            fmatch.match_identity = orig_match

        snap = s.snapshot()
        check("登录成功 account=匹配账号", snap.get("account") == "bob")
        check("登录成功 done=True", snap.get("done") is True)
        check("登录成功 result 保留文本", "登录成功" in (snap.get("result") or ""))


def test_api_key_fail_closed():
    print("\n[API-Key fail closed]")
    from .auth import require_api_key

    saved = config.API_KEY
    try:
        config.API_KEY = ""

        # 1) 启动守卫：未配置密钥拒绝启动
        try:
            require_api_key()
            check("未配置密钥 -> 启动守卫抛错", False)
        except RuntimeError as e:
            check("未配置密钥 -> 启动守卫抛错", "FACE_SERVICE_API_KEY" in str(e))

        # 2) 真实 lifespan 启动失败
        raised = False
        try:
            with TestClient(app):
                pass
        except Exception as e:
            raised = "FACE_SERVICE_API_KEY" in str(e) or "密钥" in str(e)
        check("未配置密钥 -> lifespan 启动失败", raised)

        # 3) 空密钥下接口仍 401（无绕过）
        c = TestClient(app)
        r = c.post("/sessions/login", headers={"X-API-Key": "anything"})
        check("空密钥配置下接口仍 401", r.status_code == 401)
        r = c.post("/sessions/login")
        check("空密钥且无头 -> 401", r.status_code == 401)
    finally:
        config.API_KEY = saved


def test_http():
    print("\n[HTTP 接口]")

    # 关闭真实模型：stub detect 返回无人脸
    import face_auth.models as fm
    fm.detect = lambda frame: []

    # 启用鉴权并收紧帧大小限制
    config.API_KEY = "testkey"
    config.MAX_FRAME_BYTES = 1000
    H = {"X-API-Key": "testkey"}

    client = TestClient(app)

    # 鉴权
    r = client.post("/sessions/login", headers={})
    check("无密钥 -> 401", r.status_code == 401)
    r = client.post("/sessions/login", headers={"X-API-Key": "wrong"})
    check("错误密钥 -> 401", r.status_code == 401)

    # 注册会话创建
    r = client.post("/sessions/register", json={"username": "bob"}, headers=H)
    check("创建注册会话 -> 200", r.status_code == 200)
    reg_sid = r.json()["session_id"]
    check("返回 session_id", isinstance(reg_sid, str) and len(reg_sid) > 0)

    # 登录会话创建
    r = client.post("/sessions/login", headers=H)
    check("创建登录会话 -> 200", r.status_code == 200)
    login_sid = r.json()["session_id"]

    # 非法 body 校验（空 username）
    r = client.post("/sessions/register", json={"username": ""}, headers=H)
    check("空 username -> 422", r.status_code == 422)

    # 查询
    r = client.get(f"/sessions/{login_sid}", headers=H)
    check("GET 会话 -> 200", r.status_code == 200)
    snap = r.json()
    check("快照含 phase=liveiness", snap.get("phase") == "liveness")

    # 帧处理（合法图像）
    r = client.post(f"/sessions/{login_sid}/frame",
                    content=_jpeg_bytes(), headers={**H, "Content-Type": "application/octet-stream"})
    check("帧处理 -> 200", r.status_code == 200)
    check("帧快照 done=False", r.json().get("done") is False)

    # 坏图像
    r = client.post(f"/sessions/{login_sid}/frame",
                    content=b"not an image", headers={**H, "Content-Type": "application/octet-stream"})
    check("坏图像 -> 400", r.status_code == 400)

    # 超限
    r = client.post(f"/sessions/{login_sid}/frame",
                    content=b"0" * 2000, headers={**H, "Content-Type": "application/octet-stream"})
    check("超限 -> 413", r.status_code == 413)

    # 未知会话
    r = client.get("/sessions/nonexistent", headers=H)
    check("未知会话 -> 404", r.status_code == 404)

    # 删除
    r = client.delete(f"/sessions/{reg_sid}", headers=H)
    check("删除 -> 204", r.status_code == 204)
    r = client.get(f"/sessions/{reg_sid}", headers=H)
    check("删除后查询 -> 404", r.status_code == 404)


if __name__ == "__main__":
    test_session_store()
    test_authsession_early_terminal()
    test_login_account_field()
    test_api_key_fail_closed()
    test_http()
    print(f"\n===== 结果: {len(_PASS)} 通过, {len(_FAIL)} 失败 =====")
    if _FAIL:
        print("失败项:", _FAIL)
        raise SystemExit(1)
