"""Generate transcript-grounded quizzes through Gemini with a local fallback."""
import os
import logging
import re
import json
import time
import httpx

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
PREDEFINED_VIDEO_IDS = {"jGwO_UgTS7I", "UzxYlbK2c7E"}


def predefined_quiz_for_video(video_url: str) -> list:
    """Return stable, transcript-grounded questions for the demo lecture."""
    if _extract_video_id(video_url) not in PREDEFINED_VIDEO_IDS:
        return []
    return [
        {
            "question": "What is the main goal of the CS229 machine learning course described in the lecture?",
            "type": "conceptual",
            "options": {
                "A": "To teach only software engineering interview techniques",
                "B": "To equip students to understand and build meaningful machine learning applications",
                "C": "To replace probability and linear algebra with programming practice",
                "D": "To focus exclusively on self-driving cars",
            },
            "correct": "B",
            "index": 0,
        },
        {
            "question": "Why does Andrew Ng compare AI to the new electricity?",
            "type": "conceptual",
            "options": {
                "A": "Both are useful only in the energy industry",
                "B": "Both are primarily methods for reducing computer power usage",
                "C": "AI is expected to transform many major industries, as electricity did",
                "D": "Electricity is required to train every machine learning model",
            },
            "correct": "C",
            "index": 1,
        },
        {
            "question": "Which background does the lecture identify as useful preparation for CS229?",
            "type": "conceptual",
            "options": {
                "A": "Basic computer science, probability, and linear algebra",
                "B": "Advanced chemistry and mechanical engineering",
                "C": "Only prior experience deploying mobile applications",
                "D": "No mathematics or programming knowledge",
            },
            "correct": "A",
            "index": 2,
        },
        {
            "question": "Applied scenario: A logistics company has valuable data but no machine learning team. What opportunity does the lecture suggest?",
            "type": "applied",
            "options": {
                "A": "Ignore the data until the company becomes a technology company",
                "B": "Apply machine learning to a useful logistics problem where there may be little competition",
                "C": "Use machine learning only after hiring hundreds of researchers",
                "D": "Replace all logistics workers immediately with an untested model",
            },
            "correct": "B",
            "index": 3,
        },
    ]


def _gemini_generate(prompt: str) -> str:
    """Generate quiz JSON through Gemini without requiring a local model."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        return ""

    for attempt in range(2):
        try:
            response = httpx.post(
                f"{GEMINI_URL}?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.2,
                        "max_output_tokens": 1500,
                    },
                },
                timeout=30.0,
            )
            if response.status_code == 503 and attempt == 0:
                time.sleep(1)
                continue
            response.raise_for_status()
            parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "").strip() if parts else ""
        except Exception as e:
            logger.warning("Gemini quiz generation failed: %s", e)
            return ""
    return ""


def fetch_transcript(video_url: str) -> str:
    """Fetch transcript from YouTube video."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        video_id = _extract_video_id(video_url)
        if not video_id:
            return ""

        # youtube-transcript-api 1.x exposes an instance-based fetch method;
        # retain compatibility with the older class method used previously.
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            entries = transcript_list
        else:
            transcript_list = YouTubeTranscriptApi().fetch(video_id)
            entries = transcript_list
        text = " ".join(
            entry.text if hasattr(entry, "text") else entry["text"]
            for entry in entries
        )
        return text[:4000]  # Limit for context

    except ImportError:
        logger.error("youtube-transcript-api not installed. Run: pip install youtube-transcript-api")
        return ""
    except Exception as e:
        logger.error(f"Failed to fetch transcript: {e}")
        return ""


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if len(url) == 11 and re.match(r'^[a-zA-Z0-9_-]+$', url):
        return url
    return ""


def generate_quiz(transcript: str, topic: str, suggestion_pipeline=None) -> list:
    """
    Generate 4 MCQ questions using Ollama Llama:
    - 3 conceptual questions
    - 1 applied question
    Each question has 4 options (A-D) with one correct answer.
    """
    if not transcript:
        return _generate_fallback_quiz(topic)

    prompt = f"""You are a quiz generator. Based on the following transcript about "{topic}", generate exactly 4 multiple-choice questions.

TRANSCRIPT:
\"\"\"{transcript[:3000]}\"\"\"

RULES:
- Questions 1-3 should be CONCEPTUAL (test understanding of concepts)
- Question 4 should be APPLIED (test ability to use knowledge practically)
- Each question must have exactly 4 options: A, B, C, D
- Exactly one option must be correct
- Options should be plausible (no obviously wrong answers)

Respond ONLY with valid JSON in this exact format (no other text):
[
  {{
    "question": "What is...?",
    "type": "conceptual",
    "options": {{"A": "option text", "B": "option text", "C": "option text", "D": "option text"}},
    "correct": "B"
  }},
  {{
    "question": "How does...?",
    "type": "conceptual",
    "options": {{"A": "option text", "B": "option text", "C": "option text", "D": "option text"}},
    "correct": "A"
  }},
  {{
    "question": "Which of...?",
    "type": "conceptual",
    "options": {{"A": "option text", "B": "option text", "C": "option text", "D": "option text"}},
    "correct": "C"
  }},
  {{
    "question": "In a scenario where...?",
    "type": "applied",
    "options": {{"A": "option text", "B": "option text", "C": "option text", "D": "option text"}},
    "correct": "D"
  }}
]"""

    raw = _gemini_generate(prompt)
    questions = _parse_mcq_response(raw)

    if len(questions) < 2:
        logger.warning("Gemini returned insufficient questions, using fallback")
        return _generate_fallback_quiz(topic)

    # Add index
    for i, q in enumerate(questions):
        q["index"] = i

    return questions


def _parse_mcq_response(raw: str) -> list:
    """Parse Ollama JSON response into question list."""
    if not raw:
        return []

    try:
        # Try direct JSON parse
        questions = json.loads(raw)
        if isinstance(questions, list):
            return [q for q in questions if _validate_question(q)]
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from mixed output
    json_match = re.search(r'\[[\s\S]*\]', raw)
    if json_match:
        try:
            questions = json.loads(json_match.group())
            if isinstance(questions, list):
                return [q for q in questions if _validate_question(q)]
        except json.JSONDecodeError:
            pass

    logger.error(f"Could not parse Ollama MCQ response: {raw[:200]}")
    return []


def _validate_question(q: dict) -> bool:
    """Check that a question has all required fields."""
    return (
        isinstance(q, dict)
        and "question" in q
        and "options" in q
        and isinstance(q["options"], dict)
        and len(q["options"]) >= 3
        and "correct" in q
        and q["correct"] in q["options"]
    )


def _generate_fallback_quiz(topic: str) -> list:
    """Generate MCQ quiz without transcript using Ollama."""
    prompt = f"""Generate exactly 4 multiple-choice questions about "{topic}".

RULES:
- Questions 1-3: conceptual (test understanding)
- Question 4: applied (test practical use)
- Each has 4 options (A-D), one correct
- Respond ONLY with valid JSON array

Format:
[
  {{"question": "...", "type": "conceptual", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct": "B"}},
  {{"question": "...", "type": "conceptual", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct": "A"}},
  {{"question": "...", "type": "conceptual", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct": "C"}},
  {{"question": "...", "type": "applied", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct": "D"}}
]"""

    raw = _gemini_generate(prompt)
    questions = _parse_mcq_response(raw)

    if not questions:
        t_lower = (topic or "").lower()
        if any(k in t_lower for k in ["learn", "ai", "model", "neural", "deep", "data", "vision", "general"]):
            return [
                {
                    "question": f"In {topic}, what is the primary role of an objective/loss function during model training?",
                    "type": "conceptual",
                    "options": {
                        "A": "To increase the dataset size indefinitely",
                        "B": "To quantify prediction error and guide gradient updates",
                        "C": "To eliminate the need for validation testing",
                        "D": "To force all parameter weights to equal zero"
                    },
                    "correct": "B",
                    "index": 0
                },
                {
                    "question": f"When evaluating a system in {topic}, what is the definition of 'overfitting'?",
                    "type": "conceptual",
                    "options": {
                        "A": "High training accuracy but poor generalization to unseen test data",
                        "B": "The model having too few parameters to fit the data",
                        "C": "Convergence within a single training iteration",
                        "D": "Learning rate set below 0.001"
                    },
                    "correct": "A",
                    "index": 1
                },
                {
                    "question": f"Which strategy is most effective for mitigating overfitting in {topic}?",
                    "type": "conceptual",
                    "options": {
                        "A": "Discarding validation checkpoints",
                        "B": "Regularization, dropout, and early stopping",
                        "C": "Expanding model depth without cross-validation",
                        "D": "Using unlabelled training samples exclusively"
                    },
                    "correct": "B",
                    "index": 2
                },
                {
                    "question": f"Applied Scenario: Your {topic} model scores 98% accuracy on training data but drops to 62% on test data. What should you do next?",
                    "type": "applied",
                    "options": {
                        "A": "Deploy directly to production",
                        "B": "Introduce regularization, data augmentation, or collect more diverse training data",
                        "C": "Delete the test evaluation dataset",
                        "D": "Increase model capacity tenfold without regularization"
                    },
                    "correct": "B",
                    "index": 3
                }
            ]
        else:
            return [
                {
                    "question": f"Which foundational principle is most critical when studying {topic}?",
                    "type": "conceptual",
                    "options": {
                        "A": "Relying on arbitrary assumptions without systematic analysis",
                        "B": "Understanding core concepts, mechanisms, and cause-and-effect relationships",
                        "C": "Skipping empirical verification entirely",
                        "D": "Memorizing without practical application"
                    },
                    "correct": "B",
                    "index": 0
                },
                {
                    "question": f"What is the most effective approach for retaining key ideas in {topic}?",
                    "type": "conceptual",
                    "options": {
                        "A": "Active recall and structured problem-solving",
                        "B": "Passive reading without reflection",
                        "C": "Speeding through without pausing for comprehension",
                        "D": "Ignoring foundational prerequisites"
                    },
                    "correct": "A",
                    "index": 1
                },
                {
                    "question": f"In {topic}, how should complex problems be broken down?",
                    "type": "conceptual",
                    "options": {
                        "A": "Attempting all subproblems simultaneously without modularity",
                        "B": "Decomposing into smaller, testable sub-components",
                        "C": "Guessing solutions without diagnostic metrics",
                        "D": "Disregarding feedback loops"
                    },
                    "correct": "B",
                    "index": 2
                },
                {
                    "question": f"Applied Scenario: You encounter a roadblock while applying concepts in {topic}. What is the optimal diagnostic step?",
                    "type": "applied",
                    "options": {
                        "A": "Abandon the topic immediately",
                        "B": "Isolate the problematic step, review the principle, and test with minimal examples",
                        "C": "Change all parameters randomly at once",
                        "D": "Ignore error signals"
                    },
                    "correct": "B",
                    "index": 3
                }
            ]

    for i, q in enumerate(questions):
        q["index"] = i
    return questions


def grade_answers(questions: list, answers: list, suggestion_pipeline=None) -> dict:
    """
    Grade MCQ answers — direct comparison against correct answer.
    Also use Ollama for optional feedback on wrong answers.
    """
    scores = []

    for i, (q, user_answer) in enumerate(zip(questions, answers)):
        if not user_answer or not user_answer.strip():
            scores.append({"index": i, "score": 0, "feedback": "No answer selected."})
            continue

        # Extract the letter from user answer (could be "A", "B: some text", etc.)
        selected = user_answer.strip().upper()[0] if user_answer.strip() else ""
        correct = q.get("correct", "").upper()

        if selected == correct:
            correct_text = q["options"].get(correct, "")
            scores.append({
                "index": i,
                "score": 100,
                "feedback": f"Correct! {correct_text}",
                "selected": selected,
                "correct": correct
            })
        else:
            correct_text = q["options"].get(correct, "")
            selected_text = q["options"].get(selected, user_answer)

            # Quick Ollama feedback on why the answer is wrong
            feedback = f"The correct answer is {correct}: {correct_text}"
            try:
                explanation = _ollama_generate(
                    f"In one sentence, explain why '{correct_text}' is the correct answer to: {q['question']}",
                    max_tokens=80
                )
                if explanation and len(explanation) > 10:
                    feedback = explanation
            except Exception:
                pass

            scores.append({
                "index": i,
                "score": 0,
                "feedback": feedback,
                "selected": selected,
                "correct": correct
            })

    total = sum(s["score"] for s in scores) / max(len(scores), 1)
    return {"scores": scores, "total_score": round(total, 1)}
