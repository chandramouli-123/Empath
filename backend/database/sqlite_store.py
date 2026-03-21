"""
SQLite Store — Local timestamped event logging for Empath sessions.
Supplements Supabase with fine-grained local storage.
"""
import sqlite3
import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "empath_local.db")


class SQLiteStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp_seconds REAL NOT NULL,
                emotion TEXT,
                seqi_score INTEGER,
                be REAL,
                es REAL,
                id_score REAL,
                rr REAL,
                engagement_state TEXT,
                trend_slope REAL,
                behavior_events TEXT,
                is_distracted INTEGER DEFAULT 0,
                distraction_reasons TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                student_id TEXT NOT NULL,
                final_seqi REAL,
                emotion_pattern TEXT,
                drift_segments TEXT,
                quiz_score REAL,
                recovery_metrics TEXT,
                key_segments TEXT,
                risk_level TEXT,
                total_time REAL,
                active_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                questions TEXT NOT NULL,
                answers TEXT,
                scores TEXT,
                total_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_session
            ON session_logs(session_id, timestamp_seconds)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_student
            ON session_feedback(student_id)
        """)

        conn.commit()
        conn.close()
        logger.info(f"SQLite store initialized at {self.db_path}")

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def log_event(self, session_id: str, timestamp: float, data: dict):
        """Log a timestamped event during a session."""
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO session_logs
                (session_id, timestamp_seconds, emotion, seqi_score, be, es, id_score, rr,
                 engagement_state, trend_slope, behavior_events, is_distracted, distraction_reasons)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, timestamp,
                data.get("emotion", ""),
                data.get("seqi_score", 0),
                data.get("be", 0),
                data.get("es", 0),
                data.get("id", 0),
                data.get("rr", 0),
                data.get("engagement_state", ""),
                data.get("trend_slope", 0),
                json.dumps(data.get("behavior_events", [])),
                1 if data.get("is_distracted") else 0,
                json.dumps(data.get("distraction_reasons", []))
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
        finally:
            conn.close()

    def get_session_timeline(self, session_id: str) -> list:
        """Get full timestamped timeline for a session."""
        conn = self._connect()
        try:
            cursor = conn.execute("""
                SELECT timestamp_seconds, emotion, seqi_score, be, es, id_score, rr,
                       engagement_state, trend_slope, behavior_events,
                       is_distracted, distraction_reasons
                FROM session_logs
                WHERE session_id = ?
                ORDER BY timestamp_seconds
            """, (session_id,))

            rows = cursor.fetchall()
            return [
                {
                    "t": row[0], "emotion": row[1], "seqi": row[2],
                    "be": row[3], "es": row[4], "id": row[5], "rr": row[6],
                    "state": row[7], "trend": row[8],
                    "events": json.loads(row[9] or "[]"),
                    "distracted": bool(row[10]),
                    "distraction_reasons": json.loads(row[11] or "[]")
                }
                for row in rows
            ]
        finally:
            conn.close()

    def save_feedback(self, session_id: str, student_id: str, data: dict):
        """Save session-end feedback for cross-session learning."""
        conn = self._connect()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO session_feedback
                (session_id, student_id, final_seqi, emotion_pattern, drift_segments,
                 quiz_score, recovery_metrics, key_segments, risk_level, total_time, active_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, student_id,
                data.get("final_seqi", 0),
                json.dumps(data.get("emotion_distribution", {})),
                json.dumps(data.get("drift_segments", [])),
                data.get("quiz_score"),
                json.dumps(data.get("recovery_events", [])),
                json.dumps(data.get("key_segments", {})),
                data.get("risk_level", "red"),
                data.get("total_time", 0),
                data.get("active_time", 0)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
        finally:
            conn.close()

    def get_previous_feedback(self, student_id: str, limit: int = 5) -> list:
        """Get previous session feedback for a student."""
        conn = self._connect()
        try:
            cursor = conn.execute("""
                SELECT session_id, final_seqi, emotion_pattern, drift_segments,
                       quiz_score, recovery_metrics, key_segments, risk_level,
                       total_time, active_time, created_at
                FROM session_feedback
                WHERE student_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (student_id, limit))

            rows = cursor.fetchall()
            return [
                {
                    "session_id": row[0], "final_seqi": row[1],
                    "emotion_pattern": json.loads(row[2] or "{}"),
                    "drift_segments": json.loads(row[3] or "[]"),
                    "quiz_score": row[4],
                    "recovery_metrics": json.loads(row[5] or "[]"),
                    "key_segments": json.loads(row[6] or "{}"),
                    "risk_level": row[7],
                    "total_time": row[8], "active_time": row[9],
                    "created_at": row[10]
                }
                for row in rows
            ]
        finally:
            conn.close()

    def save_quiz_result(self, session_id: str, student_id: str,
                         questions: list, answers: list, scores: list, total: float):
        """Save quiz results."""
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO quiz_results
                (session_id, student_id, questions, answers, scores, total_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id, student_id,
                json.dumps(questions), json.dumps(answers),
                json.dumps(scores), total
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to save quiz: {e}")
        finally:
            conn.close()

    def get_quiz_result(self, session_id: str) -> Optional[dict]:
        """Get quiz results for a session."""
        conn = self._connect()
        try:
            cursor = conn.execute("""
                SELECT questions, answers, scores, total_score
                FROM quiz_results WHERE session_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "questions": json.loads(row[0]),
                    "answers": json.loads(row[1] or "[]"),
                    "scores": json.loads(row[2] or "[]"),
                    "total_score": row[3]
                }
            return None
        finally:
            conn.close()


# Global singleton
sqlite_store = SQLiteStore()
