import asyncio
import json
import logging
import os
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

X_USERNAME      = os.getenv("X_USERNAME", "")
X_PASSWORD      = os.getenv("X_PASSWORD", "")
X_EMAIL         = os.getenv("X_EMAIL", "")        # Sometimes X asks for email
COOKIES_FILE    = Path("x_cookies.json")
MAX_TWEET_LEN   = 280
TWITTER_URL_LEN = 23   # X counts every URL as 23 chars


def _format_tweet(article: dict) -> str:
    title  = article["title"].strip()
    url    = article["url"]
    source = article.get("source", "").strip()

    source_tag = f" [{source}]" if source else ""
    available  = MAX_TWEET_LEN - TWITTER_URL_LEN - 2 - len(source_tag)

    if len(title) > available:
        title = title[:available - 1] + "…"

    return f"{title}{source_tag}\n\n{url}"


class XPoster:

    async def _save_cookies(self, context):
        cookies = await context.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies))
        logger.info("Cookies saved")

    async def _load_cookies(self, context) -> bool:
        if not COOKIES_FILE.exists():
            return False
        try:
            cookies = json.loads(COOKIES_FILE.read_text())
            await context.add_cookies(cookies)
            logger.info("Cookies loaded")
            return True
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
            return False

    async def _login(self, page) -> bool:
        """Log into X. Returns True on success."""
        try:
            logger.info("Logging into X...")
            await page.goto("https://x.com/login", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Username step
            await page.fill('input[autocomplete="username"]', X_USERNAME)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2000)

            # Sometimes X asks for email/phone verification
            email_input = page.locator('input[data-testid="ocfEnterTextTextInput"]')
            if await email_input.count() > 0:
                logger.info("X asked for email verification")
                await email_input.fill(X_EMAIL or X_USERNAME)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)

            # Password step
            await page.fill('input[name="password"]', X_PASSWORD)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(4000)

            # Check we're logged in
            if "home" in page.url or "x.com" in page.url:
                logger.info("Login successful")
                return True

            logger.error(f"Login may have failed, current URL: {page.url}")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def _post_tweet(self, text: str) -> tuple[bool, str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            try:
                # Try with saved cookies first
                cookies_loaded = await self._load_cookies(context)

                await page.goto("https://x.com/home", wait_until="networkidle")
                await page.wait_for_timeout(2000)

                # If not logged in, do full login
                if "login" in page.url or not cookies_loaded:
                    success = await self._login(page)
                    if not success:
                        return False, "Login failed"
                    await self._save_cookies(context)
                    await page.goto("https://x.com/home", wait_until="networkidle")
                    await page.wait_for_timeout(2000)

                # Click the tweet compose box
                compose = page.locator('[data-testid="tweetTextarea_0"]')
                await compose.wait_for(timeout=10000)
                await compose.click()
                await page.wait_for_timeout(1000)

                # Type the tweet
                await compose.fill(text)
                await page.wait_for_timeout(1000)

                # Click Post button
                post_btn = page.locator('[data-testid="tweetButtonInline"]')
                await post_btn.wait_for(timeout=5000)
                await post_btn.click()
                await page.wait_for_timeout(3000)

                # Save fresh cookies
                await self._save_cookies(context)

                logger.info("Tweet posted successfully via browser")
                return True, "https://x.com"

            except PlaywrightTimeout as e:
                logger.error(f"Playwright timeout: {e}")
                if COOKIES_FILE.exists():
                    COOKIES_FILE.unlink()
                return False, f"Timeout: {e}"

            except Exception as e:
                logger.error(f"Browser post error: {e}")
                return False, str(e)

            finally:
                await browser.close()

    def post(self, article: dict) -> tuple[bool, str]:
        """Synchronous wrapper called from the Telegram handler."""
        text = _format_tweet(article)
        return asyncio.run(self._post_tweet(text))
