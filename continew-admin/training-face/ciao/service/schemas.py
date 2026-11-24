"""人脸认证服务 — 请求 / 响应模型。"""

from pydantic import BaseModel, Field


class CreateRegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)


class CreateSessionResponse(BaseModel):
    session_id: str


class SessionSnapshot(BaseModel):
    mode: str
    phase: str
    done: bool
    result: str | None = None
    action: str | None = None
    account: str | None = None


class FaceStatusResponse(BaseModel):
    registered: bool
