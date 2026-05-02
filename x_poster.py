import asyncio
import json
import logging
import os
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

X_USERNAME      = os.getenv("X_USERNAME", "")
X_PASSWORD      = os.getenv("X_PASSWORD", "")
X_EMAIL         = os.getenv("X_EMAIL", "")
COOKIES_FILE    = Path("x_cookies.json")
MAX_TWEET_LEN   = 280
TWITTER_URL_LEN = 23


def _format_tweet(article: dict) -> str:
    title  = article["title"].strip()
    url    = article["url"]
    source = article.get("source", "").strip()
    source_tag = f" [{source}]" if source else ""
    available  = MAX_TWEET_LEN - TWITTER_URL_LEN - 2 - len(source_tag)
    if len(title) > available:
        title = title[:available - 1] + "…"
    return f"{title}{source_tag}\n\n{url}"


async def _save_cookies(context):
    cookies = await context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies))
    logger.info("Cookies saved")


async def _load_cookies(context) -> bool:
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


async def _login(page) -> bool:
    try:
        logger.info("Navigating to X login...")
        await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        logger.info(f"Login page loaded, URL: {page.url}")

        # Username
        await page.fill('input[autocomplete="username"]', X_USERNAME)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3000)
        logger.info("Username entered")

        # Possible email verification step
        try:
            email_input = page.locator('input[data-testid="ocfEnterTextTextInput"]')
            if await email_input.count() > 0:
                logger.info("Email verification requested")
                await email_input.fill(X_EMAIL or X_USERNAME)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        # Password
        await page.fill('input[name="password"]', X_PASSWORD)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(5000)
        logger.info(f"Password entered, URL now: {page.url}")

        if "home" in page.url:
            logger.info("Login successful")
            return True

        logger.error(f"Login failed, stuck at: {page.url}")
        return False

    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


async def post_article(article: dict) -> tuple[bool, str]:
    """Async function — called directly from the Telegram handler."""
    text = _format_tweet(article)
    logger.info(f"Starting browser post: {text[:60]}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
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
            cookies_loaded = await _load_cookies(context)

            if cookies_loaded:
                logger.info("Trying with saved cookies...")
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

            if not cookies_loaded or "login" in page.url:
                logger.info("Doing full login...")
                success = await _login(page)
                if not success:
                    return False, "Login failed — check X_USERNAME, X_PASSWORD, X_EMAIL variables"
                await _save_cookies(context)
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

            logger.info("Looking for compose box...")
            compose = page.locator('[data-testid="tweetTextarea_0"]')
            await compose.wait_for(timeout=15000)
            await compose.click()
            await page.wait_for_timeout(1000)

            await compose.fill(text)
            await page.wait_for_timeout(1000)
            logger.info("Tweet text entered")

            post_btn = page.locator('[data-testid="tweetButtonInline"]')
            await post_btn.wait_for(timeout=5000)
            await post_btn.click()
            await page.wait_for_timeout(3000)

            await _save_cookies(context)
            logger.info("Tweet posted successfully!")
            return True, "https://x.com"

        except PlaywrightTimeout as e:
            logger.error(f"Timeout: {e}")
            if COOKIES_FILE.exists():
                COOKIES_FILE.unlink()
            return False, f"Timeout — X took too long to respond: {e}"

        except Exception as e:
            logger.error(f"Post error: {e}")
            return False, str(e)

        finally:
            await browser.close()
