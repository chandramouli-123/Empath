from transformers import pipeline
from PIL import Image
import torch
import io
import logging
from collections import deque

logger = logging.getLogger(__name__)

emotion_pipeline = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Map dima806 output labels → 4 model-derived classes
# Raw model labels: happy, surprise, neutral, fear, sad, disgust, angry, contempt
LABEL_MAP = {
    "happy":    "focused",
    "neutral":  "focused",
    "surprise": "confused",
    "fear":     "confused",
    "sad":      "distressed",
    "angry":    "distressed",
    "disgust":  "bored",
    "contempt": "bored",
}

# Confidence thresholds per emotion class
# Higher threshold = harder to trigger that emotion (more conservative)
THRESHOLDS = {
    "confused":   0.60,
    "distressed": 0.65,  # Highest — very hard to trigger
    "bored":      0.55,
}

VALID_EMOTIONS = {"focused", "confused", "bored", "distressed"}

# Temporal smoothing — last N frames vote for the final emotion
# Prevents single-frame noise from flipping the displayed emotion
SMOOTHING_WINDOW = 5
_recent_emotions = deque(maxlen=SMOOTHING_WINDOW)
_recent_focused_prob = deque(maxlen=SMOOTHING_WINDOW)


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
    Analyze a webcam frame and return the detected emotion.
    
    3-layer calibration:
    1. Per-class confidence thresholds (distressed hardest to trigger)
    2. Combined focused-probability check (happy+neutral vs non-focused)
    3. Temporal smoothing (majority vote over last 5 frames)
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = emotion_pipeline(image)

        if not results:
            return {"emotion": "focused", "confidence": 0.0, "raw_label": "none"}

        top = results[0]
        raw_label = top["label"].lower()
        confidence = top["score"]
        emotion = LABEL_MAP.get(raw_label, "focused")

        # ─── Layer 1: Per-class confidence threshold ───
        if emotion != "focused":
            threshold = THRESHOLDS.get(emotion, 0.55)
            if confidence < threshold:
                emotion = "focused"  # not confident enough

        # ─── Layer 2: Combined focused-probability check ───
        # Even if above threshold, check if focused labels collectively
        # still dominate. This handles cases where the model
        # gives e.g. 40% sad + 35% neutral + 20% happy
        if emotion != "focused":
            focused_prob = sum(
                r["score"] for r in results
                if LABEL_MAP.get(r["label"].lower()) == "focused"
            )
            # If focused labels combined > 1.2× the non-focused prediction,
            # the user is more likely focused
            if focused_prob > confidence * 1.2:
                emotion = "focused"
                confidence = focused_prob
                raw_label = f"{raw_label}→focused(combined)"

        # ─── Layer 3: Temporal smoothing ───
        _recent_emotions.append(emotion)

        # Only change reported emotion if the new emotion appears
        # in at least 60% of the recent window
        if len(_recent_emotions) >= 3:
            from collections import Counter
            counts = Counter(_recent_emotions)
            most_common, most_count = counts.most_common(1)[0]
            # Need 60% agreement (3/5 frames) to report non-focused
            if most_common != "focused" and most_count >= 3:
                emotion = most_common
            elif most_common == "focused":
                emotion = "focused"
            else:
                # No strong consensus → default to focused
                emotion = "focused"

        return {
            "emotion": emotion,
            "confidence": round(confidence, 3),
            "raw_label": raw_label
        }
    except Exception as e:
        logger.error(f"Emotion analysis failed: {e}")
        return {
            "emotion": "focused",
            "confidence": 0.0,
            "raw_label": "error"
        }
