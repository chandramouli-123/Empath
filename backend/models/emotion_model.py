from transformers import pipeline
from PIL import Image
import torch
import io
import logging
from collections import deque, Counter

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

# 4-frame temporal smoothing window (~8 seconds)
SMOOTHING_WINDOW = 4
_recent_emotions = deque(maxlen=SMOOTHING_WINDOW)
_current_stable_emotion = "focused"


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
    global _current_stable_emotion

    if emotion_pipeline is None:
        return {"emotion": "focused", "confidence": 0.85, "raw_label": "default"}

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = emotion_pipeline(image)

        if not results:
            return {"emotion": _current_stable_emotion, "confidence": 0.0, "raw_label": "none"}

        top = results[0]
        raw_label = top["label"].lower()
        confidence = top["score"]

        mapped = LABEL_MAP.get(raw_label, "focused")
        _recent_emotions.append(mapped)

        # Count frequencies in recent window
        counts = Counter(_recent_emotions)
        most_common, most_count = counts.most_common(1)[0]

        # Require at least 2 consistent votes in window to transition
        if most_count >= 2 and most_common != _current_stable_emotion:
            # Prevent single-frame lighting artifacts from triggering negative states
            if most_common in ("bored", "distressed") and confidence < 0.30:
                pass
            else:
                _current_stable_emotion = most_common

        return {
            "emotion": _current_stable_emotion,
            "confidence": round(float(confidence), 3),
            "raw_label": raw_label
        }
    except Exception as e:
        logger.error(f"Emotion analysis failed: {e}")
        return {
            "emotion": "focused",
            "confidence": 0.0,
            "raw_label": "error"
        }
