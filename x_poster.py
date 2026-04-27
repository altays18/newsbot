import tweepy
import logging
from config import X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET

logger = logging.getLogger(__name__)

MAX_TWEET_LENGTH = 280
TWITTER_URL_LENGTH = 23   # Twitter counts every URL as 23 characters


class XPoster:
    def __init__(self):
        self.client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
        )

    def _format_tweet(self, article: dict) -> str:
        title  = article["title"].strip()
        url    = article["url"]
        source = article.get("source", "").strip()

        source_tag = f" [{source}]" if source else ""

        # Characters available for the title
        available = MAX_TWEET_LENGTH - TWITTER_URL_LENGTH - 2 - len(source_tag)

        if len(title) > available:
            title = title[:available - 1] + "…"

        return f"{title}{source_tag}\n\n{url}"

    def post(self, article: dict) -> tuple[bool, str]:
        """
        Post an article to X.
        Returns (success: bool, tweet_url_or_error: str)
        """
        try:
            text     = self._format_tweet(article)
            response = self.client.create_tweet(text=text)
            tweet_id = response.data["id"]
            tweet_url = f"https://x.com/i/web/status/{tweet_id}"
            logger.info(f"Posted tweet {tweet_id}: {article['title'][:60]}")
            return True, tweet_url

        except tweepy.TweepyException as e:
            logger.error(f"Tweet failed: {e}")
            return False, str(e)
