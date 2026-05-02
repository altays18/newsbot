import html
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import TELEGRAM_GROUP_ID
from database import Database
from deduplicator import Deduplicator
from news_client import MarketauxClient
from x_poster import XPoster

logger = logging.getLogger(__name__)

news_client = MarketauxClient()
x_poster    = XPoster()


def _build_message(article: dict) -> str:
    title       = html.escape(article["title"])
    description = html.escape(article.get("description", ""))
    url         = article["url"]
    source      = html.escape(article.get("source", ""))
    published   = article.get("published_at", "")[:10]

    lines = [f"📰 <b>{title}</b>", ""]

    if description:
        desc = description[:220] + "…" if len(description) > 220 else description
        lines += [f"<i>{desc}</i>", ""]

    lines.append(f'🔗 <a href="{url}">Read full article</a>')

    if source:
        lines.append(f"📡 {source}")
    if published:
        lines.append(f"📅 {published}")

    return "\n".join(lines)


def _approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Post",       callback_data="post"),
        InlineKeyboardButton("🔗 Post + URL", callback_data="post_url"),
        InlineKeyboardButton("❌ Skip",        callback_data="skip"),
    ]])


async def send_article_to_group(bot, article: dict, db: Database) -> int | None:
    try:
        msg = await bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=_build_message(article),
            parse_mode=ParseMode.HTML,
            reply_markup=_approval_keyboard(),
            disable_web_page_preview=False,
        )
        db.save_pending(msg.message_id, article)
        logger.info(f"Sent to Telegram [{msg.message_id}]: {article['title'][:60]}")
        return msg.message_id
    except Exception as e:
        logger.error(f"Failed to send article to Telegram: {e}")
        return None


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()

    db         = context.bot_data["db"]
    message_id = query.message.message_id
    action     = query.data
    user       = query.from_user.first_name or "Someone"

    article = db.get_pending(message_id)

    if not article:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ This article was already handled.")
        return

    db.mark_handled(message_id)
    await query.edit_message_reply_markup(reply_markup=None)

    if action in ("post", "post_url"):
        include_url = action == "post_url"
        label = "🔗 Post + URL" if include_url else "✅ Post"
        await query.message.reply_text(f"⏳ Posting to X ({label})…")

        success, result = x_poster.post(article, include_url=include_url)

        if success:
            await query.message.reply_text(
                f"✅ Posted by <b>{html.escape(user)}</b>\n"
                f'🐦 <a href="{result}">View on X</a>',
                parse_mode=ParseMode.HTML,
            )
        else:
            await query.message.reply_text(
                f"❌ Post failed: <code>{html.escape(result)}</code>",
                parse_mode=ParseMode.HTML,
            )

    elif action == "skip":
        await query.message.reply_text(
            f"⏭ Skipped by <b>{html.escape(user)}</b>",
            parse_mode=ParseMode.HTML,
        )


async def poll_news(context: ContextTypes.DEFAULT_TYPE):
    db    = context.job.data
    dedup = Deduplicator(db)

    logger.info("Polling news…")
    articles = news_client.fetch_articles()

    new_count  = 0
    skip_count = 0

    for article in articles:
        title = (article.get("title") or "").strip()
        url   = (article.get("url")   or "").strip()

        if not title or not url:
            continue

        is_dup, reason = dedup.is_duplicate(title, url)

        if is_dup:
            logger.debug(f"Duplicate skipped: {title[:50]} — {reason}")
            skip_count += 1
            continue

        db.mark_seen(url, title)
        await send_article_to_group(context.bot, article, db)
        new_count += 1

    logger.info(f"Poll done — {new_count} new, {skip_count} duplicates skipped")
    db.cleanup_old()
