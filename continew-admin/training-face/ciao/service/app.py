"""人脸认证服务 — FastAPI 入口。

仅新增服务层：鉴权、会话存储、接口路由、大小限制与异常处理。
复用 face_auth 现有算法模块，不重写检测 / 活体 / 匹配逻辑。
"""

import asyncio
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from face_auth import models
from face_auth.matcher import load_db
from face_auth.session import AuthSession

from . import auth, config, schemas
from .session_store import SessionStore

store = SessionStore(config.SESSION_IDLE_TTL, config.SESSION_MAX_AGE, config.DONE_TTL)

CLEANUP_INTERVAL = 30.0


def _handle_frame(entry, body):
    """字节 -> OpenCV BGR -> AuthSession.process（在会话锁内）。"""
    frame = cv2.imdecode(np.frombuffer(body, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="无法解码图像")
    with entry.lock:
        return entry.auth.process(frame)


async def _cleanup_loop():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        store.cleanup()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    auth.require_api_key()  # fail closed：未配置密钥拒绝启动
    models.get_app()  # 预加载模型，避免首帧延迟
    task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Face Auth Service", lifespan=lifespan)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > config.MAX_FRAME_BYTES:
        return JSONResponse(status_code=413, content={"detail": "请求体过大"})
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "服务内部错误"})


@app.post("/sessions/register", response_model=schemas.CreateSessionResponse)
def create_register_session(body: schemas.CreateRegisterRequest, _=Depends(auth.verify_api_key)):
    auth_session = AuthSession("register", username=body.username, db_path=config.DB_PATH)
    return {"session_id": store.create(auth_session)}


@app.post("/sessions/login", response_model=schemas.CreateSessionResponse)
def create_login_session(_=Depends(auth.verify_api_key)):
    auth_session = AuthSession("login", db_path=config.DB_PATH)
    return {"session_id": store.create(auth_session)}


@app.post("/sessions/{session_id}/frame", response_model=schemas.SessionSnapshot)
async def process_frame(session_id: str, request: Request, _=Depends(auth.verify_api_key)):
    entry = store.get_entry(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    body = await request.body()
    if len(body) > config.MAX_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="请求体过大")
    snap = await run_in_threadpool(_handle_frame, entry, body)
    if snap["done"]:
        store.mark_done(session_id)
    return snap


@app.get("/sessions/{session_id}", response_model=schemas.SessionSnapshot)
def get_session(session_id: str, _=Depends(auth.verify_api_key)):
    entry = store.get_entry(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    with entry.lock:
        return entry.auth.snapshot()


@app.get("/faces/{username}", response_model=schemas.FaceStatusResponse)
def face_status(username: str, _=Depends(auth.verify_api_key)):
    return {"registered": username in load_db(config.DB_PATH)}


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, _=Depends(auth.verify_api_key)):
    store.delete(session_id)
    return None
