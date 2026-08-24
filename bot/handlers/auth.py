from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
from bot.services.db import db
from bot.services.rate_limit import requires_auth, admin_only
import os
import uuid

@Client.on_message(filters.command("help") & filters.private)
@requires_auth
async def help_cmd(client: Client, message: Message):
    help_text = """
**VPS Admin Bot Commands**

*General:*
/cmd <bash command> - Execute a bash command
/shell - Start an interactive PTY session
/endshell - Stop PTY
/ctrlc - Send SIGINT to PTY
/ctrld - Send EOF to PTY
/download <path> - Download a file from the server
/status - Server vitals (CPU/RAM/Disk)
/logs <service> - View logs for allowlisted service
/restart <service> - Restart allowlisted service
/history - View your command history
/clearhistory - Clear your history

*Admin:*
/adduser <telegram_id> - Add a new user
/removeuser <telegram_id> - Remove a user
/listusers - List all authorized users

*Uploads:*
Simply send any document, photo, or video to upload it to your server directory.
"""
    await message.reply(help_text)

@Client.on_message(filters.command("adduser") & filters.private)
@admin_only
async def adduser_cmd(client: Client, message: Message):
    parts = message.text.split(" ")
    if len(parts) != 2:
        await message.reply("Usage: /adduser <telegram_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("Invalid Telegram ID.")
        return

    user = await db.get_user(target_id)
    if user:
        await message.reply("User already exists.")
        return

    await db.create_user(target_id)
    await message.reply(f"User {target_id} added successfully.")

@Client.on_message(filters.command("removeuser") & filters.private)
@admin_only
async def removeuser_cmd(client: Client, message: Message):
    parts = message.text.split(" ")
    if len(parts) != 2:
        await message.reply("Usage: /removeuser <telegram_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("Invalid Telegram ID.")
        return

    if target_id == int(os.environ.get('ADMIN_ID', 0)):
         await message.reply("Cannot remove admin user.")
         return

    await db.delete_user(target_id)
    await message.reply(f"User {target_id} removed.")

@Client.on_message(filters.command("listusers") & filters.private)
@admin_only
async def listusers_cmd(client: Client, message: Message):
    users = await db.get_all_users()
    if not users:
        await message.reply("No users found.")
        return

    text = "**Authorized Users:**\n"
    for u in users:
        text += f"- ID: `{u['telegram_id']}`\n"

    await message.reply(text)
