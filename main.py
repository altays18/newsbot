import logging
from telegram.ext import Application, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, POLL_INTERVAL_MINUTES
from bot import handle_callback, poll_news
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    db = Database()
    db.init()
    logger.info("Database initialised")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Make db available to all handlers
    app.bot_data["db"] = db

    # Button press handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Scheduled news poll
    app.job_queue.run_repeating(
        poll_news,
        interval=POLL_INTERVAL_MINUTES * 60,
        first=10,          # First poll 10 seconds after startup
        data=db,
    )

    logger.info(f"Bot started — polling every {POLL_INTERVAL_MINUTES} minutes")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
