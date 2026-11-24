"""人脸认证服务 — 运行配置（环境变量 + 默认值）。"""

import os
from pathlib import Path


def _env(name, default=""):
    return os.environ.get(name, default)


def _env_float(name, default):
    try:
        return float(_env(name))
    except ValueError:
        return default


def _env_int(name, default):
    try:
        return int(_env(name))
    except ValueError:
        return default


# 服务鉴权密钥；为空则不校验（仅开发用，生产必须设置）
API_KEY = _env("FACE_SERVICE_API_KEY", "")

# 会话 TTL（秒）
SESSION_IDLE_TTL = _env_float("FACE_SESSION_IDLE_TTL", 120.0)   # 无活动过期
SESSION_MAX_AGE = _env_float("FACE_SESSION_MAX_AGE", 300.0)     # 绝对上限
DONE_TTL = _env_float("FACE_DONE_TTL", 10.0)                    # 完成后保留

# 单帧最大字节数
MAX_FRAME_BYTES = _env_int("FACE_MAX_FRAME_BYTES", 2 * 1024 * 1024)

# face_db.json 路径；默认沿用仓库 data/face_db.json
_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(_env("FACE_DB_PATH", str(_REPO_ROOT / "data" / "face_db.json")))

HOST = _env("FACE_SERVICE_HOST", "127.0.0.1")
PORT = _env_int("FACE_SERVICE_PORT", 8000)
