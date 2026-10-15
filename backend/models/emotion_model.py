from __future__ import annotations

from transformers import pipeline
from PIL import Image
import torch
import io
import logging
from collections import deque
import cv2
import numpy as np
try:
    import mediapipe as mp
except ImportError:
    mp = None

logger = logging.getLogger(__name__)

emotion_pipeline = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

LABEL_MAP = {
    "happy":    "focused",
    "neutral":  "focused",   # In learning, a calm resting face is focused!
    "surprise": "confused",
    "fear":     "confused",
    "sad":      "bored",
    "angry":    "distressed",
    "disgust":  "bored",
    "contempt": "bored",
}

# Facial affect is a weak signal for a studying student. Keep a visible face
# focused unless a negative class has strong, repeated evidence.
NEGATIVE_CONFIDENCE_THRESHOLD = 0.75
SAD_CONFIDENCE_THRESHOLD = NEGATIVE_CONFIDENCE_THRESHOLD
SAD_DISGUST_DOMINANCE_RATIO = 2.0
DISTRESSED_CONFIDENCE_THRESHOLD = NEGATIVE_CONFIDENCE_THRESHOLD

# 4-frame temporal smoothing window (~8 seconds)
SMOOTHING_WINDOW = 4
_recent_emotions = deque(maxlen=SMOOTHING_WINDOW)
_current_stable_emotion = "focused"
_pending_emotion = None
_pending_emotion_count = 0
_behavior_pending = None
_behavior_pending_count = 0
_face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
_face_mesh = (
    mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    )
    if mp is not None
    else None
)

_LEFT_EYE = (362, 385, 387, 263, 373, 380)
_RIGHT_EYE = (33, 160, 158, 133, 153, 144)


def _center_crop(image: Image.Image) -> Image.Image:
    """Keep the central 70% of the frame to reduce background influence."""
    width, height = image.size
    x_margin = int(width * 0.15)
    y_margin = int(height * 0.15)
    return image.crop((x_margin, y_margin, width - x_margin, height - y_margin))


def _find_face(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Find the largest frontal face using a lightweight local detector."""
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    faces = _face_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(max(32, image.width // 12), max(32, image.height // 12)),
    )
    if len(faces) == 0:
        return None
    return tuple(max(faces, key=lambda face: face[2] * face[3]))


def detect_face(image_bytes: bytes) -> bool:
    """Return whether a usable face is present in the webcam frame."""
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if _find_face(image) is not None:
            return True
        # Haar is fast but often misses a returning face, especially with
        # glasses, side lighting, or a slightly turned head.
        if _face_mesh is not None:
            mesh_result = _face_mesh.process(np.asarray(image))
            return bool(mesh_result.multi_face_landmarks)
        return False
    except Exception as e:
        logger.error(f"Face detection failed: {e}")
        return False


def _face_crop(image: Image.Image, face: tuple[int, int, int, int]) -> Image.Image:
    """Crop a face with a small margin so the classifier sees facial context."""
    x, y, width, height = face
    margin_x = int(width * 0.25)
    margin_y = int(height * 0.35)
    left = max(0, x - margin_x)
    top = max(0, y - margin_y)
    right = min(image.width, x + width + margin_x)
    bottom = min(image.height, y + height + margin_y)
    return image.crop((left, top, right, bottom))


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _eye_ratio(landmarks, indices: tuple[int, ...]) -> float:
    points = np.array(
        [(landmarks[i].x, landmarks[i].y) for i in indices],
        dtype=np.float32,
    )
    horizontal = _distance(points[0], points[3])
    vertical = _distance(points[1], points[5]) + _distance(points[2], points[4])
    return (vertical / (2.0 * horizontal)) if horizontal else 0.0


def _behavior_signal(image: Image.Image) -> tuple[str | None, float]:
    """Estimate attention from face landmarks; emotion is only a fallback."""
    global _face_mesh
    if _face_mesh is None:
        return None, 0.0

    frame = np.asarray(image)
    result = _face_mesh.process(frame)
    if not result.multi_face_landmarks:
        return None, 0.0

    landmarks = result.multi_face_landmarks[0].landmark
    left_eye = _eye_ratio(landmarks, _LEFT_EYE)
    right_eye = _eye_ratio(landmarks, _RIGHT_EYE)
    eye_open = (left_eye + right_eye) / 2.0

    # Face-relative orientation from the nose and cheek/eye geometry.
    nose = landmarks[1]
    left_cheek = landmarks[234]
    right_cheek = landmarks[454]
    face_width = max(abs(right_cheek.x - left_cheek.x), 0.01)
    yaw = abs((nose.x - (left_cheek.x + right_cheek.x) / 2.0) / face_width)
    pitch = abs(nose.y - (landmarks[10].y + landmarks[152].y) / 2.0)

    if yaw > 0.30 or pitch > 0.25:
        return "distracted", 0.95
    # Require both eyes to be substantially closed. This avoids treating a
    # hand on the cheek or a one-sided landmark occlusion as boredom.
    if left_eye < 0.16 and right_eye < 0.16:
        return "bored", 0.90
    return "focused", 0.95


def _map_emotion(raw_label: str, scores: dict[str, float]) -> str:
    """Map model labels using context-aware confidence and competing scores."""
    top_score = scores.get(raw_label, 0.0)
    if raw_label in {"surprise", "fear", "angry", "sad", "disgust", "contempt"}:
        if top_score < NEGATIVE_CONFIDENCE_THRESHOLD:
            return "focused"

    if raw_label == "angry":
        angry_score = scores.get("angry", 0.0)
        neutral_happy_score = scores.get("neutral", 0.0) + scores.get("happy", 0.0)
        if (
            angry_score < DISTRESSED_CONFIDENCE_THRESHOLD
            or neutral_happy_score >= angry_score * 0.75
        ):
            return "focused"
        return "distressed"

    if raw_label == "sad":
        sad_score = scores.get("sad", 0.0)
        neutral_happy_score = scores.get("neutral", 0.0) + scores.get("happy", 0.0)
        sad_disgust_score = sad_score + scores.get("disgust", 0.0)

        if (
            sad_score < SAD_CONFIDENCE_THRESHOLD
            or neutral_happy_score >= sad_score * 0.75
        ):
            return "focused"
        if (
            sad_score >= SAD_CONFIDENCE_THRESHOLD
            or sad_disgust_score >= neutral_happy_score * SAD_DISGUST_DOMINANCE_RATIO
        ):
            return "bored"
        return "focused"

    if raw_label == "disgust":
        sad_disgust_score = scores.get("sad", 0.0) + scores.get("disgust", 0.0)
        neutral_happy_score = scores.get("neutral", 0.0) + scores.get("happy", 0.0)
        if (
            sad_disgust_score > 0.0
            and sad_disgust_score >= neutral_happy_score * SAD_DISGUST_DOMINANCE_RATIO
        ):
            return "bored"
        return "focused"

    mapped = LABEL_MAP.get(raw_label, "focused")
    if mapped == "bored":
        sad_score = scores.get("sad", 0.0)
        sad_disgust_score = sad_score + scores.get("disgust", 0.0)
        neutral_happy_score = scores.get("neutral", 0.0) + scores.get("happy", 0.0)
        if (
            sad_score >= SAD_CONFIDENCE_THRESHOLD
            or (
                sad_disgust_score > 0.0
                and sad_disgust_score >= neutral_happy_score * SAD_DISGUST_DOMINANCE_RATIO
            )
        ):
            return "bored"
        return "focused"
    return mapped


def load_model():
    global emotion_pipeline
    print(f"[emotion_model] Using device: {DEVICE}")
    emotion_pipeline = pipeline(
        "image-classification",
        model="dima806/facial_emotions_image_detection",
        device=DEVICE,
        framework="pt"
    )


def analyze_frame(image_bytes: bytes) -> dict:
    """
    Stabilized real-time emotion inference with temporal hysteresis.
    Eliminates frame-by-frame flicker and noise while responding to genuine shifts.
    """
    global _current_stable_emotion, _pending_emotion, _pending_emotion_count
    global _behavior_pending, _behavior_pending_count

    if emotion_pipeline is None:
        return {
            "emotion": "focused",
            "confidence": 0.85,
            "raw_label": "default",
            "face_detected": True,
        }

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        face = _find_face(image)
        mesh_face_present = False
        if face is None and _face_mesh is not None:
            mesh_result = _face_mesh.process(np.asarray(image))
            mesh_face_present = bool(mesh_result.multi_face_landmarks)

        if face is None and not mesh_face_present:
            _recent_emotions.clear()
            _pending_emotion = None
            _pending_emotion_count = 0
            _behavior_pending = None
            _behavior_pending_count = 0
            return {
                "emotion": "distracted",
                "confidence": 1.0,
                "raw_label": "no_face",
                "face_detected": False,
            }

        behavior, behavior_confidence = _behavior_signal(image)
        if behavior is not None:
            if behavior == "focused":
                _behavior_pending = None
                _behavior_pending_count = 0
                _current_stable_emotion = "focused"
            elif behavior == _behavior_pending:
                _behavior_pending_count += 1
            else:
                _behavior_pending = behavior
                _behavior_pending_count = 1

            if behavior != "focused" and _behavior_pending_count >= 2:
                _current_stable_emotion = behavior
                _behavior_pending = None
                _behavior_pending_count = 0

            return {
                "emotion": _current_stable_emotion,
                "confidence": behavior_confidence,
                "raw_label": f"landmarks:{behavior}",
                "face_detected": True,
            }

        crop = _face_crop(image, face) if face is not None else _center_crop(image)
        results = emotion_pipeline(crop, top_k=None)

        if not results:
            return {
                "emotion": _current_stable_emotion,
                "confidence": 0.0,
                "raw_label": "none",
                "face_detected": True,
            }

        scores = {
            str(result["label"]).lower(): float(result["score"])
            for result in results
        }
        raw_label, confidence = max(scores.items(), key=lambda item: item[1])

        mapped = _map_emotion(raw_label, scores)
        _recent_emotions.append(mapped)

        # Confirm negative states over consecutive frames, but let clear focus
        # immediately recover from stale bored/confused votes.
        if mapped == "focused":
            _current_stable_emotion = "focused"
            _pending_emotion = None
            _pending_emotion_count = 0
        elif mapped == _current_stable_emotion:
            _pending_emotion = None
            _pending_emotion_count = 0
        else:
            if mapped == _pending_emotion:
                _pending_emotion_count += 1
            else:
                _pending_emotion = mapped
                _pending_emotion_count = 1

            if _pending_emotion_count >= 2:
                _current_stable_emotion = mapped
                _pending_emotion = None
                _pending_emotion_count = 0

        return {
            "emotion": _current_stable_emotion,
            "confidence": round(float(confidence), 3),
            "raw_label": raw_label,
            "face_detected": True,
        }
    except Exception as e:
        logger.error(f"Emotion analysis failed: {e}")
        return {
            "emotion": "focused",
            "confidence": 0.0,
            "raw_label": "error",
            "face_detected": False,
        }
