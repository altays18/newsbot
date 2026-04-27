import logging
from rapidfuzz import fuzz
from database import Database
from config import SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self, db: Database):
        self.db = db

    def is_duplicate(self, title: str, url: str) -> tuple[bool, str]:
        """
        Returns (is_duplicate, reason_string).

        Two-stage check:
          1. Exact URL match  — fast, zero false positives
          2. Fuzzy title match — catches reworded versions of the same story
        """

        # Stage 1 — exact URL
        if self.db.is_url_seen(url):
            return True, "URL already seen"

        # Stage 2 — fuzzy title similarity
        recent_titles = self.db.get_recent_titles()
        title_lower   = title.lower()

        for existing in recent_titles:
            # token_sort_ratio handles word-order differences well
            score = fuzz.token_sort_ratio(title_lower, existing.lower())
            if score >= SIMILARITY_THRESHOLD * 100:
                logger.debug(
                    f"Duplicate detected (score={score}): "
                    f"'{title[:50]}' ≈ '{existing[:50]}'"
                )
                return True, f"Similar to: '{existing[:60]}' (score: {score})"

        return False, ""
