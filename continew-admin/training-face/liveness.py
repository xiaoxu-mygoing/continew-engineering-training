"""Server-side action challenge verification. Frames exist only for this process."""
import hashlib



def completed(scores, action):
    """Require neutral -> sustained requested action -> neutral, in that order."""
    if len(scores) < 12 or action not in ("mouth", "down", "turn"):
        return False
    base = tuple((scores[0][i] + scores[1][i]) / 2 for i in range(3))
    neutral = lambda s: s[0] < 0.25 and abs(s[1]-base[1]) < 8 and abs(s[2]-base[2]) < 8
    if base[0] > 0.25 or not all(neutral(s) for s in scores[-2:]):
        return False
    if action == "mouth":
        active = lambda s: s[0] > max(0.30, base[0]+0.18)
    elif action == "down":
        active = lambda s: s[1]-base[1] > 10 and abs(s[2]-base[2]) < 15
    else:
        active = lambda s: abs(s[2]-base[2]) > 13
    return any(active(scores[i]) and active(scores[i + 1]) for i in range(2, len(scores) - 3))


def verify(req, models, decode, extract, error):
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    actions, batches = req.get("actions"), req.get("batches")
    preview = req.get("preview") is True
    valid = isinstance(actions, list) and len(actions) == (1 if preview else 2) and len(set(actions)) == len(actions) and all(a in ("mouth", "down", "turn") for a in actions)
    if not valid or not isinstance(batches, list) or len(batches) != len(actions):
        raise error("活体验证步骤无效，请重新开启摄像头")
    if any(not isinstance(batch, list) or not 12 <= len(batch) <= 28 for batch in batches):
        raise error("采集帧数不足，请保持摄像头开启")
    if any(not isinstance(frame, str) or not 0 < len(frame) <= 100000 for batch in batches for frame in batch):
        raise error("活体采集画面大小无效")
    engines = (cv2.FaceDetectorYN.create(str(models / "face_detection_yunet_2023mar.onnx"), "", (320, 240), 0.85),
               cv2.FaceRecognizerSF.create(str(models / "face_recognition_sface_2021dec.onnx"), ""))
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(models / "face_landmarker.task")),
        num_faces=2, output_face_blendshapes=True, output_facial_transformation_matrixes=True,
        min_face_detection_confidence=0.6, min_face_presence_confidence=0.6)
    baseline = None
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        for action, batch in zip(actions, batches):
            if len({hashlib.sha256(frame.encode()).digest() for frame in batch}) < 6:
                if preview:
                    return {"passed": False}
                raise error("画面缺少连续变化，请本人完成动作")
            scores = []
            for image in batch:
                feature = np.frombuffer(extract(image, models, engines=engines), dtype=np.float32)
                feature = feature / max(float(np.linalg.norm(feature)), 1e-8)
                if baseline is None:
                    baseline = feature
                elif float(np.dot(baseline, feature)) < 0.45:
                    raise error("活体过程中人脸不一致，请保持本人入镜")
                frame = cv2.cvtColor(decode(image), cv2.COLOR_BGR2RGB)
                result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=frame))
                if len(result.face_blendshapes) != 1:
                    raise error("请保持单人正对摄像头并完整露出面部")
                values = {item.category_name: item.score for item in result.face_blendshapes[0]}
                rotation = result.facial_transformation_matrixes[0][:3, :3]
                pitch = float(np.degrees(np.arctan2(-rotation[1, 2], rotation[2, 2])))
                yaw = float(np.degrees(np.arctan2(rotation[0, 2], rotation[2, 2])))
                scores.append((values.get("jawOpen", 0), pitch, yaw))
            if not completed(scores, action):
                if preview:
                    return {"passed": False}
                hint = {"mouth": "轻轻张嘴再闭嘴", "down": "轻轻低头再回正", "turn": "向任意一侧转头再回正"}[action]
                raise error("动作未通过：请按提示" + hint + "，动作前后保持自然表情")
    return {"passed": True}
