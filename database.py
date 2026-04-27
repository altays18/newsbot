import sqlite3
import json
from datetime import datetime, timedelta
from config import DB_PATH, DEDUP_WINDOW_HOURS


class Database:
    def __init__(self):
        self.path = DB_PATH

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS seen_articles (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    url      TEXT UNIQUE NOT NULL,
                    title    TEXT NOT NULL,
                    seen_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_articles (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id   INTEGER UNIQUE NOT NULL,
                    article_json TEXT NOT NULL,
                    created_at   TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_seen_at    ON seen_articles(seen_at);
                CREATE INDEX IF NOT EXISTS idx_message_id ON pending_articles(message_id);
            """)

    # ── Deduplication helpers ──────────────────────────────────────────────────

    def _cutoff(self) -> str:
        return (datetime.utcnow() - timedelta(hours=DEDUP_WINDOW_HOURS)).isoformat()

    def is_url_seen(self, url: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_articles WHERE url = ? AND seen_at > ?",
                (url, self._cutoff()),
            ).fetchone()
            return row is not None

    def get_recent_titles(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT title FROM seen_articles WHERE seen_at > ?",
                (self._cutoff(),),
            ).fetchall()
            return [r["title"] for r in rows]

    def mark_seen(self, url: str, title: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_articles (url, title, seen_at) VALUES (?, ?, ?)",
                (url, title, datetime.utcnow().isoformat()),
            )

    # ── Pending articles (awaiting Telegram decision) ─────────────────────────

    def save_pending(self, message_id: int, article: dict):
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO pending_articles
                   (message_id, article_json, created_at) VALUES (?, ?, ?)""",
                (message_id, json.dumps(article), datetime.utcnow().isoformat()),
            )

    def get_pending(self, message_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT article_json FROM pending_articles WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            return json.loads(row["article_json"]) if row else None

    def delete_pending(self, message_id: int):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM pending_articles WHERE message_id = ?",
                (message_id,),
            )

    # ── Maintenance ───────────────────────────────────────────────────────────

    def cleanup_old(self):
        """Remove records older than 2x the dedup window."""
        cutoff = (datetime.utcnow() - timedelta(hours=DEDUP_WINDOW_HOURS * 2)).isoformat()
        with self._conn() as conn:
            conn.execute("DELETE FROM seen_articles    WHERE seen_at   < ?", (cutoff,))
            conn.execute("DELETE FROM pending_articles WHERE created_at < ?", (cutoff,))
