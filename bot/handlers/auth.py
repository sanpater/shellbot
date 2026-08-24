from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
from bot.services.auth_service import auth_service
from bot.services.db import db
from bot.services.rate_limit import requires_auth, admin_only
import os
import uuid

# In-memory dictionary to store pending password entries
# mapping admin_id -> target_user_id
pending_user_creation = {}


@Client.on_message(filters.command("login") & filters.private)
async def login_cmd(client: Client, message: Message):
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.reply("Usage: /login <passphrase>")
        return

    password = parts[1]
    success, msg = await auth_service.authenticate(message.from_user.id, password)

    # Delete message to hide passphrase
    try:
        await message.delete()
    except Exception:
        pass

    await message.reply(msg)

@Client.on_message(filters.command("logout") & filters.private)
@requires_auth
async def logout_cmd(client: Client, message: Message):
    await auth_service.logout(message.from_user.id)
    await message.reply("You have been logged out.")

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

    pending_user_creation[message.from_user.id] = target_id
    await message.reply(f"Please enter a passphrase for user {target_id} in your next message.")

@Client.on_message(filters.private & ~filters.regex("^/") & filters.create(lambda _, __, m: m.from_user.id in pending_user_creation))
async def set_user_passphrase(client: Client, message: Message):
    admin_id = message.from_user.id
    target_id = pending_user_creation.pop(admin_id)
    password = message.text

    # Delete message to hide passphrase
    try:
        await message.delete()
    except Exception:
        pass

    hashed = auth_service.hash_password(password)
    await db.create_user(target_id, hash=hashed)
    await message.reply(f"User {target_id} created successfully.")

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

    text = "**Users:**\n"
    for u in users:
        status = "Auth" if u['is_auth'] else "Not Auth"
        text += f"- ID: {u['telegram_id']}, Status: {status}, Fails: {u['fails']}\n"

    await message.reply(text)

@Client.on_message(filters.command("revoke") & filters.private)
@admin_only
async def revoke_cmd(client: Client, message: Message):
    parts = message.text.split(" ")
    if len(parts) != 2:
        await message.reply("Usage: /revoke <telegram_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("Invalid Telegram ID.")
        return

    await db.update_user(target_id, is_auth=0)
    await message.reply(f"Revoked authentication for user {target_id}.")

pending_pass_reset = {}

@Client.on_message(filters.command("resetpass") & filters.private)
@admin_only
async def resetpass_cmd(client: Client, message: Message):
    parts = message.text.split(" ")
    if len(parts) != 2:
        await message.reply("Usage: /resetpass <telegram_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("Invalid Telegram ID.")
        return

    user = await db.get_user(target_id)
    if not user:
         await message.reply("User not found.")
         return

    pending_pass_reset[message.from_user.id] = target_id
    await message.reply(f"Please enter a new passphrase for user {target_id} in your next message.")

@Client.on_message(filters.private & ~filters.regex("^/") & filters.create(lambda _, __, m: m.from_user.id in pending_pass_reset))
async def execute_pass_reset(client: Client, message: Message):
    admin_id = message.from_user.id
    target_id = pending_pass_reset.pop(admin_id)
    password = message.text

    # Delete message to hide passphrase
    try:
        await message.delete()
    except Exception:
        pass

    hashed = auth_service.hash_password(password)
    await db.update_user(target_id, hash=hashed, is_auth=0, fails=0, lock_until=0)
    await message.reply(f"Passphrase for user {target_id} reset successfully. They must login again.")
