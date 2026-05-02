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


async def _click_next_button(page) -> bool:
    """Click whichever Next/Continue button is visible."""
    selectors = [
        '[data-testid="ocfEnterTextNextButton"]',
        '[data-testid="LoginForm_Login_Button"]',
        'div[role="button"]:has-text("Next")',
        'div[role="button"]:has-text("Continue")',
        'span:has-text("Next")',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                logger.info(f"Clicked button: {sel}")
                return True
        except Exception:
            continue
    # Fallback — press Enter
    await page.keyboard.press("Enter")
    return True


async def _login(page) -> bool:
    try:
        logger.info("Navigating to X login...")
        await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        logger.info(f"URL: {page.url}")

        # Step 1 — username
        username_input = page.locator('input[autocomplete="username"], input[name="text"]').first
        await username_input.wait_for(state="visible", timeout=10000)
        await username_input.fill(X_USERNAME)
        await _click_next_button(page)
        await page.wait_for_timeout(3000)
        logger.info("Username submitted")

        # Step 2 — loop through whatever screens X shows
        for attempt in range(4):
            await page.wait_for_timeout(2000)
            logger.info(f"Screen check attempt {attempt + 1}, URL: {page.url}")

            # Success — we're logged in
            if "home" in page.url:
                logger.info("Login successful!")
                return True

            # Password field
            pwd = page.locator('input[name="password"]')
            if await pwd.count() > 0 and await pwd.is_visible():
                logger.info("Password field found, entering password...")
                await pwd.fill(X_PASSWORD)
                await _click_next_button(page)
                await page.wait_for_timeout(5000)
                logger.info(f"Password submitted, URL: {page.url}")
                continue

            # Email/phone verification field
            verify = page.locator('input[data-testid="ocfEnterTextTextInput"]')
            if await verify.count() > 0 and await verify.is_visible():
                logger.info("Verification field found, entering email...")
                await verify.fill(X_EMAIL)
                await _click_next_button(page)
                await page.wait_for_timeout(3000)
                continue

            # Generic text input (phone/email prompt before password)
            generic = page.locator('input[name="text"]')
            if await generic.count() > 0 and await generic.is_visible():
                logger.info("Generic text input, entering email...")
                await generic.fill(X_EMAIL)
                await _click_next_button(page)
                await page.wait_for_timeout(3000)
                continue

            logger.info("No known input found on this screen, waiting...")

        # Final check
        if "home" in page.url:
            logger.info("Login successful!")
            return True

        logger.error(f"Login failed after all attempts, URL: {page.url}")
        return False

    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


async def post_article(article: dict) -> tuple[bool, str]:
    text = _format_tweet(article)
    logger.info(f"Starting browser post: {text[:60]}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
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
                logger.info("Trying saved cookies...")
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

            if not cookies_loaded or "login" in page.url:
                logger.info("Performing full login...")
                success = await _login(page)
                if not success:
                    return False, "Login failed — check X_USERNAME, X_PASSWORD, X_EMAIL in Railway variables"
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
            return False, f"Timeout: {e}"

        except Exception as e:
            logger.error(f"Post error: {e}")
            return False, str(e)

        finally:
            await browser.close()
