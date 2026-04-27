import requests
import logging
from config import NEWS_API_KEY, NEWS_API_URL, NEWS_COUNTRY, NEWS_CATEGORY, NEWS_PAGE_SIZE

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


# ── NewsAPI.org (default) ─────────────────────────────────────────────────────

class NewsAPIClient(NewsClient):
    """Default client using newsapi.org (free tier: 100 req/day)."""

    def fetch_articles(self) -> list[dict]:
        try:
            resp = requests.get(
                NEWS_API_URL,
                params={
                    "apiKey":   NEWS_API_KEY,
                    "country":  NEWS_COUNTRY,
                    "category": NEWS_CATEGORY,
                    "pageSize": NEWS_PAGE_SIZE,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            articles = []
            for item in data.get("articles", []):
                if not item.get("title") or not item.get("url"):
                    continue
                articles.append({
                    "title":        item["title"],
                    "description":  item.get("description", ""),
                    "url":          item["url"],
                    "published_at": item.get("publishedAt", ""),
                    "source":       item.get("source", {}).get("name", "Unknown"),
                })

            logger.info(f"Fetched {len(articles)} articles from NewsAPI")
            return articles

        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")
            return []


# ── YOUR CUSTOM NEWS API ───────────────────────────────────────────────────────
#
# Replace NewsAPIClient with your own class. Example:
#
# class MyNewsClient(NewsClient):
#     BASE_URL = "https://your-api.com/v1"
#     API_KEY  = os.getenv("MY_NEWS_API_KEY")
#
#     def fetch_articles(self) -> list[dict]:
#         resp = requests.get(
#             f"{self.BASE_URL}/articles",
#             headers={"Authorization": f"Bearer {self.API_KEY}"},
#             params={"limit": 20},
#             timeout=10,
#         )
#         resp.raise_for_status()
#         return [
#             {
#                 "title":        a["headline"],
#                 "description":  a.get("summary", ""),
#                 "url":          a["link"],
#                 "published_at": a.get("published", ""),
#                 "source":       a.get("publisher", ""),
#             }
#             for a in resp.json().get("results", [])
#             if a.get("headline") and a.get("link")
#         ]
#
# Then in bot.py change:
#   news_client = NewsAPIClient()
# to:
#   news_client = MyNewsClient()
# ─────────────────────────────────────────────────────────────────────────────
