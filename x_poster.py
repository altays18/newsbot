import re
import tweepy
import logging
from config import X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET

URL_PATTERN = re.compile(r'https?://\S+|www\.\S+|\S+\.(com|net|org|io|co|uk|de|fr|tr)\S*', re.IGNORECASE)


def _strip_urls(text: str) -> str:
    """Remove any URLs or domain-like strings from text."""
    return URL_PATTERN.sub('', text).strip()

logger = logging.getLogger(__name__)

MAX_TWEET_LENGTH = 280
TWITTER_URL_LENGTH = 23


class XPoster:
    def __init__(self):
        self.client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
        )

    def _format_tweet(self, article: dict, include_url: bool) -> str:
        title  = article["title"].strip()
        url    = article["url"]
        source = article.get("source", "").strip()
        source_tag = f" [{source}]" if source else ""

        if include_url:
            available = MAX_TWEET_LENGTH - TWITTER_URL_LENGTH - 2 - len(source_tag)
            if len(title) > available:
                title = title[:available - 1] + "…"
            return f"{title}{source_tag}\n\n{url}"
        else:
            # Strip any URLs/domains from title and source
            title      = _strip_urls(title)
            source_tag = f" [{_strip_urls(source)}]" if source else ""
            available  = MAX_TWEET_LENGTH - len(source_tag)
            if len(title) > available:
                title = title[:available - 1] + "…"
            return f"{title}{source_tag}"

    def post(self, article: dict, include_url: bool = False) -> tuple[bool, str]:
        try:
            text = self._format_tweet(article, include_url)
            response = self.client.create_tweet(text=text)
            tweet_id = response.data["id"]
            tweet_url = f"https://x.com/i/web/status/{tweet_id}"
            logger.info(f"Posted tweet {tweet_id}: {article['title'][:60]}")
            return True, tweet_url
        except tweepy.TweepyException as e:
            logger.error(f"Tweet failed: {e}")
            return False, str(e)
