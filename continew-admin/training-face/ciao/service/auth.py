"""人脸认证服务 — API-Key 鉴权依赖。"""

import secrets

from fastapi import Header, HTTPException, status

from . import config


def require_api_key():
    """服务启动守卫：未配置密钥时拒绝启动（fail closed）。"""
    if not config.API_KEY:
        raise RuntimeError("未配置服务密钥：请设置环境变量 FACE_SERVICE_API_KEY（不允许为空）")


def verify_api_key(x_api_key: str = Header(default="", alias="X-API-Key")):
    if not x_api_key or not secrets.compare_digest(x_api_key, config.API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的服务密钥")
    return None
