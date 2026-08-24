from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.services.pty_manager import pty_manager
from bot.services.rate_limit import requires_auth
import os


@Client.on_message(filters.command("shell") & filters.private)
@requires_auth
async def shell_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    existing = pty_manager.get_session(user_id)
    if existing:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Keep", callback_data="shell_keep")],
            [InlineKeyboardButton("Restart", callback_data="shell_restart")],
            [InlineKeyboardButton("Cancel", callback_data="shell_cancel")]
        ])
        await message.reply("You already have an active shell session.", reply_markup=keyboard)
        return

    success = pty_manager.start_session(user_id, client, message.chat.id)
    if success:
        await message.reply("Shell session started. Send commands directly.")
    else:
        await message.reply("Maximum shell sessions reached globally. Try again later.")

@Client.on_callback_query(filters.regex("^shell_"))
@requires_auth
async def shell_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split("_")[1]

    if action == "keep":
        await callback.message.edit_text("Kept existing shell session active.")
    elif action == "restart":
        pty_manager.stop_session(user_id)
        success = pty_manager.start_session(user_id, client, callback.message.chat.id)
        if success:
            await callback.message.edit_text("Restarted shell session.")
        else:
            await callback.message.edit_text("Failed to restart. Maximum global sessions reached.")
    elif action == "cancel":
        await callback.message.edit_text("Cancelled shell start.")

@Client.on_message(filters.command("endshell") & filters.private)
@requires_auth
async def endshell_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if pty_manager.get_session(user_id):
        pty_manager.stop_session(user_id)
        await message.reply("Shell session ended.")
    else:
        await message.reply("No active shell session.")

@Client.on_message(filters.command("ctrlc") & filters.private)
@requires_auth
async def ctrlc_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    session = pty_manager.get_session(user_id)
    if session:
        session.write("\x03")
        await message.reply("Sent SIGINT (Ctrl+C)")
    else:
        await message.reply("No active shell session.")

@Client.on_message(filters.command("ctrld") & filters.private)
@requires_auth
async def ctrld_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    session = pty_manager.get_session(user_id)
    if session:
        session.write("\x04")
        await message.reply("Sent EOF (Ctrl+D)")
    else:
        await message.reply("No active shell session.")

# Must be lowest priority, catch-all for shell input
@Client.on_message(filters.text & filters.private & ~filters.regex("^/") & filters.create(lambda _, __, m: pty_manager.get_session(m.from_user.id) is not None))
async def shell_input(client: Client, message: Message):
    user_id = message.from_user.id
    session = pty_manager.get_session(user_id)
    # Avoid circular imports with pending admin states
    from bot.handlers.auth import pending_user_creation, pending_pass_reset
    if user_id in pending_user_creation or user_id in pending_pass_reset:
        return

    if session:
        session.write(message.text + "\n")
