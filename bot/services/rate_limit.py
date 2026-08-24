import time
import os
import asyncio
from collections import defaultdict
from functools import wraps
from pyrogram.errors import FloodWait
import logging
from bot.services.db import db
from bot.services.auth_service import auth_service

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.cmd_limit = int(os.environ.get('COMMAND_RATE_LIMIT', 5))
        self.cmd_window = int(os.environ.get('COMMAND_RATE_WINDOW', 10))
        self.history = defaultdict(list)

    def is_rate_limited(self, user_id: int) -> bool:
        now = time.time()
        # Clean up old history
        self.history[user_id] = [ts for ts in self.history[user_id] if now - ts < self.cmd_window]

        if len(self.history[user_id]) >= self.cmd_limit:
            return True

        self.history[user_id].append(now)
        return False

rate_limiter = RateLimiter()

def requires_auth(func):
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        # We handle callback queries and messages slightly differently for replies
        is_callback = hasattr(message, 'data')
        sender = message.from_user

        if not sender:
            return

        user_id = sender.id

        # Check rate limit
        if rate_limiter.is_rate_limited(user_id):
            msg = "Rate limit exceeded. Please slow down."
            if is_callback:
                await message.answer(msg, show_alert=True)
            else:
                await message.reply(msg)
            return

        try:
            user = await db.get_user(user_id)
            if not user or not user['is_auth']:
                msg = "You are not authenticated. Please use /login <passphrase>."
                if is_callback:
                    await message.answer(msg, show_alert=True)
                else:
                    await message.reply(msg)
                return

            return await func(client, message, *args, **kwargs)
        except FloodWait as e:
            logger.warning(f"FloodWait encountered: sleeping for {e.value} seconds")
            await asyncio.sleep(e.value)
            return await wrapper(client, message, *args, **kwargs)

    return wrapper

def admin_only(func):
    @wraps(func)
    @requires_auth
    async def wrapper(client, message, *args, **kwargs):
        is_callback = hasattr(message, 'data')
        sender = message.from_user
        admin_id = int(os.environ.get('ADMIN_ID', 0))

        if sender.id != admin_id:
            msg = "You are not authorized to use this command."
            if is_callback:
                await message.answer(msg, show_alert=True)
            else:
                await message.reply(msg)
            return

        return await func(client, message, *args, **kwargs)
    return wrapper
