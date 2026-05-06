import requests
import logging
import os

logger = logging.getLogger(__name__)

FIBNEWS_API_URL  = os.getenv("FIBNEWS_API_URL", "https://fibnews-backend-production.up.railway.app")
FIBNEWS_REGION   = os.getenv("FIBNEWS_REGION", "")   # Optional: us, europe, asia or blank for all
NEWS_PAGE_SIZE   = int(os.getenv("NEWS_PAGE_SIZE", "20"))


class NewsClient:
    def fetch_articles(self) -> list[dict]:
        raise NotImplementedError


class FibNewsClient(NewsClient):
    """Pulls articles from the fibnews backend."""

    def fetch_articles(self) -> list[dict]:
        try:
            params = {"limit": NEWS_PAGE_SIZE}
            if FIBNEWS_REGION:
                params["region"] = FIBNEWS_REGION

            resp = requests.get(
                f"{FIBNEWS_API_URL}/api/news",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            # Backend returns either a list or {"articles": [...]}
            items = data if isinstance(data, list) else data.get("articles", data.get("data", []))

            articles = []
            for item in items:
                if not item.get("title") or not item.get("url"):
                    continue
                articles.append({
                    "title":        item["title"],
                    "description":  item.get("description", ""),
                    "url":          item["url"],
                    "published_at": item.get("published_at", ""),
                    "source":       item.get("source", ""),
                    "category":     item.get("category", ""),
                    "region":       item.get("region", ""),
                })

            logger.info(f"Fetched {len(articles)} articles from FibNews backend")
            return articles

        except Exception as e:
            logger.error(f"FibNews fetch failed: {e}")
            return []
