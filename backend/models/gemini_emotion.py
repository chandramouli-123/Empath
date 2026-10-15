from __future__ import annotations

import os
import io
import json
import base64
import logging
import httpx

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

VALID_EMOTIONS = {"focused", "neutral", "confused", "bored", "distressed"}


def is_gemini_available() -> bool:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return bool(key and key != "YOUR_GEMINI_API_KEY")


def analyze_with_gemini(image_bytes: bytes) -> dict | None:
    """
    Sends webcam frame to Google Gemini 1.5 Flash Vision.
    Returns structured emotion dict or None on failure/fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        return None

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "You are an AI educational emotion and engagement analyzer. "
            "Analyze this student's webcam frame while they are watching an educational lecture. "
            "Return ONLY one valid JSON object matching this schema; do not include markdown or extra text:\n"
            "{\n"
            '  "emotion": "focused" | "neutral" | "confused" | "bored" | "distressed",\n'
            '  "phone_detected": true\n'
            "}\n"
            "Guidelines:\n"
            "- Attentive gaze on screen / taking notes / calm or slight smile = 'focused'.\n"
            "- Frowning at content / head tilt / scratching chin curiously = 'confused'.\n"
            "- Slumped / looking away aimlessly / yawning = 'bored'.\n"
            "- Set phone_detected to true if a smartphone/cell phone is visible or being held, "
            "even if only partly visible. Otherwise set it to false. "
            "phone_detected must be a JSON boolean, not a string."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }

        # 4s timeout to maintain responsive frontend
        with httpx.Client(timeout=4.0) as client:
            resp = client.post(
                f"{GEMINI_URL}?key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

        if resp.status_code != 200:
            logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:100]}")
            return None

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None

        text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        parsed = json.loads(text_content)

        raw_emo = str(parsed.get("emotion", "focused")).lower().strip()
        emotion = raw_emo if raw_emo in VALID_EMOTIONS else "focused"
        confidence = float(parsed.get("confidence", 0.90))
        phone_value = parsed.get("phone_detected", False)
        if isinstance(phone_value, bool):
            phone_detected = phone_value
        elif isinstance(phone_value, str):
            phone_detected = phone_value.strip().lower() == "true"
        else:
            phone_detected = False

        return {
            "emotion": emotion,
            "confidence": round(confidence, 3),
            "raw_label": f"gemini:{emotion}",
            "phone_detected": phone_detected,
            "distractions": ["cell phone"] if phone_detected else []
        }

    except Exception as e:
        logger.warning(f"Gemini vision call failed, falling back to local: {e}")
        return None
