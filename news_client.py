import requests
import logging
import os
from config import NEWS_API_KEY, NEWS_API_URL, NEWS_PAGE_SIZE

logger = logging.getLogger(__name__)


# ── Base class ────────────────────────────────────────────────────────────────

class NewsClient:
    """
    Base class. Every client must return a list of article dicts with these keys:
        title        (str, required)
        url          (str, required)
        description  (str, optional)
        published_at (str, optional — ISO 8601 or any date string)
        source       (str, optional)
    """
    def fetch_articles(self) -> list[dict]:
        raise NotImplementedError


# ── Marketaux ─────────────────────────────────────────────────────────────────

class MarketauxClient(NewsClient):
    """Client for api.marketaux.com — free tier: 100 req/day"""

    def fetch_articles(self) -> list[dict]:
        try:
            resp = requests.get(
                NEWS_API_URL,
                params={
                    "api_token": NEWS_API_KEY,
                    "language":  os.getenv("NEWS_LANGUAGE", "en"),
                    "limit":     NEWS_PAGE_SIZE,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            articles = []
            for item in data.get("data", []):
                if not item.get("title") or not item.get("url"):
                    continue
                articles.append({
                    "title":        item["title"],
                    "description":  item.get("description", ""),
                    "url":          item["url"],
                    "published_at": item.get("published_at", ""),
                    "source":       item.get("source", ""),
                })

            logger.info(f"Fetched {len(articles)} articles from Marketaux")
            return articles

        except Exception as e:
            logger.error(f"Marketaux fetch failed: {e}")
            return []
