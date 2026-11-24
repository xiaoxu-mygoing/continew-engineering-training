"""人脸认证 — 活体检测配置。

从 test_random_liveness.py 提取，仅保留已验证的姿态动作（左右转头、抬头、低头），
不包含眨眼挑战。阈值、方向符号、动作顺序、时间参数均与原脚本保持一致。
"""

# ==================== 集中配置（阈值统一在此调整） ====================
CONFIG = {
    # —— 姿态（弧度）—— 均为相对「自然正脸基线」的变化量
    "yaw_turn_threshold": 0.25,       # 转头：|yaw 变化| >= 该值
    "pitch_turn_threshold": 0.20,     # 抬头/低头：|pitch 变化| >= 该值
    "pose_hold_frames": 3,            # 姿态需连续保持的帧数

    # —— 基线 ——
    "baseline_frames": 10,            # 采集自然正脸的帧数

    # —— 每轮挑战 ——
    "actions_per_round": 3,
    "action_timeout": 8.0,            # 单个动作超时（秒）
    "face_lost_timeout": 1.5,         # 无有效人脸超过该秒数判本轮失败

    # 方向符号：相对变化的「正方向」。若实际感知方向相反，把 +1/-1 对调即可。
    "yaw_sign": {"turn_left": 1.0, "turn_right": -1.0},
    "pitch_sign": {"look_up": 1.0, "look_down": -1.0},

    # 中立位门控：pose 动作相应轴需先进入 |变化| < 该值的中立范围才判定
    "pose_neutral_thr": 0.10,
}

ACTIONS = ("turn_left", "turn_right", "look_up", "look_down")
ACTION_TEXT = {
    "turn_left": "请向左转头",
    "turn_right": "请向右转头",
    "look_up": "请抬头",
    "look_down": "请低头",
}

# ==================== 会话参数（注册 / 登录） ====================
STABLE_FRAMES = 5        # 登录：连续同账号确认帧数
SAMPLE_COUNT = 10        # 注册：特征采集次数
SAMPLE_INTERVAL = 0.3    # 注册：采集间隔（秒）
