"""人脸认证 — 随机动作主动活体检测状态机（仅姿态动作）。

从 test_random_liveness.py 提取并重构，供外部传入人脸检测结果与会话状态复用。
- 仅包含已验证的姿态动作：turn_left / turn_right / look_up / look_down。
- 不含眨眼挑战（眨眼依赖 MediaPipe FaceMesh 的 EAR，见 test_random_liveness.py）。
- 不加载模型、不打开摄像头、不绘制 HUD；由调用方负责检测人脸并把结果传入。

与原始脚本的耦合说明（保持算法不变，未擅自改写）：
- measure_pose：依赖 InsightFace face.pose（单位度），此处统一转为弧度。
- step_round 的基线阶段原依赖双眼 EAR（眨眼基线），姿态动作不需要，故只采集 pose。
- draw_hud / main（摄像头、模型加载、HUD 绘制）未提取，仍保留在 test_random_liveness.py。
"""

import random
import time

import numpy as np

from .config import ACTIONS, CONFIG


# ==================== 特征提取 ====================
def measure_pose(face):
    """提取 InsightFace 姿态 [pitch, yaw, roll]；face.pose 原始单位为度，转为弧度返回。"""
    return np.deg2rad(np.asarray(face.pose, dtype=np.float32)) if face.pose is not None else None


# ==================== 动作判定 ====================
def new_state():
    return {"hold": 0, "pose_armed": False}


def check_action(action, pose_rel, st):
    """返回 True 表示该动作已连续满足要求（完成）。

    仅处理姿态动作（turn_left / turn_right / look_up / look_down）。
    中立位门控：相应轴先进入 |变化| < pose_neutral_thr 的中立范围，才允许计数判定。
    """
    if action in ("turn_left", "turn_right"):
        axis = 1
        value = pose_rel[1] * CONFIG["yaw_sign"][action]
        threshold = CONFIG["yaw_turn_threshold"]
    else:  # look_up / look_down
        axis = 0
        value = pose_rel[0] * CONFIG["pitch_sign"][action]
        threshold = CONFIG["pitch_turn_threshold"]

    # 中立位门控：相应轴先进入中立范围，才允许开始计数判定
    if not st["pose_armed"]:
        if abs(pose_rel[axis]) < CONFIG["pose_neutral_thr"]:
            st["pose_armed"] = True
            st["hold"] = 0
        return False

    if value >= threshold:
        st["hold"] += 1
    else:
        st["hold"] = 0
    return st["hold"] >= CONFIG["pose_hold_frames"]


# ==================== 一轮挑战 ====================
def new_round():
    return {
        "phase": "baseline",
        "baseline": [],
        "baseline_pose": None,
        "actions": random.sample(ACTIONS, CONFIG["actions_per_round"]),
        "done": [],
        "current": None,
        "st": new_state(),
        "action_start": 0.0,
        "lost_since": None,
        "result": "",
    }


def step_round(r, faces):
    """推进一轮；返回 'ok' / 'success' / 'fail'。

    faces 为外部传入的人脸检测结果列表（每项需含 .pose，与 InsightFace face 对象一致）。
    """
    now = time.time()

    if r["phase"] == "baseline":
        if len(faces) == 1:
            pose = measure_pose(faces[0])
            if pose is not None:
                r["baseline"].append(pose)
        else:
            r["baseline"].clear()
        if len(r["baseline"]) >= CONFIG["baseline_frames"]:
            poses = np.stack(r["baseline"])
            r["baseline_pose"] = poses.mean(axis=0)
            r["phase"] = "challenge"
            r["current"] = r["actions"][0]
            r["st"] = new_state()
            r["action_start"] = now
            r["lost_since"] = None
        return "ok"

    if r["phase"] in ("success", "fail"):
        return r["phase"]

    # challenge
    if len(faces) == 1:
        r["lost_since"] = None
        face = faces[0]
        pose = measure_pose(face)
        pose_rel = pose - r["baseline_pose"] if pose is not None else None

        action = r["current"]
        can_judge = pose_rel is not None

        if can_judge:
            if check_action(action, pose_rel, r["st"]):
                r["done"].append(action)
                if len(r["done"]) >= len(r["actions"]):
                    r["phase"] = "success"
                    r["result"] = "挑战成功"
                    return "success"
                r["current"] = r["actions"][len(r["done"])]
                r["st"] = new_state()
                r["action_start"] = now

        if now - r["action_start"] > CONFIG["action_timeout"]:
            r["phase"] = "fail"
            r["result"] = "本轮失败：动作超时"
            return "fail"
    else:
        if r["lost_since"] is None:
            r["lost_since"] = now
        elif now - r["lost_since"] > CONFIG["face_lost_timeout"]:
            r["phase"] = "fail"
            r["result"] = "本轮失败：人脸丢失"
            return "fail"

    return "ok"
