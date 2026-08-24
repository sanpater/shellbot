import asyncio
import os
import sys
import signal
from pyrogram import Client
from dotenv import load_dotenv
from bot.utils.logger import setup_logger
from bot.services.db import init_db, close_db, db
from bot.services.pty_manager import pty_manager

load_dotenv()
logger = setup_logger()

async def ensure_admin_exists():
    admin_id = int(os.environ.get('ADMIN_ID', 0))
    if admin_id > 0:
        admin_user = await db.get_user(admin_id)
        if not admin_user:
            logger.info(f"Admin user {admin_id} not found in DB. Creating...")
            await db.create_user(admin_id)
            logger.info(f"Admin user {admin_id} added. They must use /login <passphrase> to set their initial password.")

async def main():
    logger.info("Starting VPS Admin Bot...")

    # Check for required API credentials
    api_id = os.environ.get('API_ID')
    api_hash = os.environ.get('API_HASH')
    bot_token = os.environ.get('BOT_TOKEN')

    if not all([api_id, api_hash, bot_token]):
        logger.error("Missing required Telegram API credentials (API_ID, API_HASH, BOT_TOKEN). Please set them in .env")
        sys.exit(1)

    # Initialize DB
    db_path = os.environ.get('DB_PATH', 'data/bot.db')
    await init_db(db_path)
    await ensure_admin_exists()

    # Setup client using Smart Plugins
    client = Client(
        "vps_admin_bot",
        api_id=int(api_id) if api_id.isdigit() else api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        workdir="data",
        plugins=dict(root="bot.handlers")
    )

    stop_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}. Initiating shutdown...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await client.start()
    logger.info("Bot is running.")

    # Wait for shutdown signal
    await stop_event.wait()

    logger.info("Shutting down...")
    pty_manager.stop_all()
    await client.stop()
    await close_db()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
