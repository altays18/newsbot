import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


# ── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID  = int(_require("TELEGRAM_GROUP_ID"))

# ── X / Twitter ───────────────────────────────────────────────────────────────
X_API_KEY             = _require("X_API_KEY")
X_API_SECRET          = _require("X_API_SECRET")
X_ACCESS_TOKEN        = _require("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = _require("X_ACCESS_TOKEN_SECRET")

# ── News API ───────────────────────────────────────────────────────────────────
NEWS_API_KEY   = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL   = os.getenv("NEWS_API_URL", "https://newsapi.org/v2/top-headlines")
NEWS_COUNTRY   = os.getenv("NEWS_COUNTRY", "us")
NEWS_CATEGORY  = os.getenv("NEWS_CATEGORY", "technology")
NEWS_PAGE_SIZE = int(os.getenv("NEWS_PAGE_SIZE", "10"))

# ── Deduplication ─────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.80"))
DEDUP_WINDOW_HOURS   = int(os.getenv("DEDUP_WINDOW_HOURS", "24"))

# ── Polling ───────────────────────────────────────────────────────────────────
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "15"))

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "articles.db")
