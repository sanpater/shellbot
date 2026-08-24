from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.services.cmd_runner import cmd_runner
from bot.services.system_service import system_service
from bot.services.rate_limit import requires_auth, admin_only
from bot.services.db import db
import os


@Client.on_message(filters.command("cmd") & filters.private)
@requires_auth
async def cmd_cmd(client: Client, message: Message):
    command = message.text[len("/cmd "):].strip()
    if not command:
        await message.reply("Usage: /cmd <command>")
        return

    user_id = message.from_user.id
    await db.add_history(user_id, command)

    reply_msg = await message.reply("Running...")

    output, file_path = await cmd_runner.run(command)

    if file_path:
        try:
            await client.send_document(
                chat_id=message.chat.id,
                document=file_path,
                caption="Command output too large. Sent as file."
            )
            await reply_msg.delete()
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        if not output.strip():
            output = "(No output)"
        await reply_msg.edit_text(f"```\n{output}\n```")

@Client.on_message(filters.command("status") & filters.private)
@requires_auth
async def status_cmd(client: Client, message: Message):
    status = system_service.get_status()
    await message.reply(status)

@Client.on_message(filters.command("logs") & filters.private)
@requires_auth
async def logs_cmd(client: Client, message: Message):
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        allowed = system_service.get_allowed_services()
        await message.reply(f"Usage: /logs <service>\nAllowed: {', '.join(allowed)}")
        return

    service = parts[1].strip()
    if not system_service.is_service_allowed(service):
        await message.reply("Service not in allowlist.")
        return

    await db.add_history(message.from_user.id, f"logs {service}")
    reply_msg = await message.reply(f"Fetching logs for {service}...")

    # systemd journald specific, or generic fallback. We use journalctl
    cmd = f"journalctl -u {service} -n 100 --no-pager"
    output, file_path = await cmd_runner.run(cmd)

    if file_path:
         try:
             await client.send_document(
                chat_id=message.chat.id,
                document=file_path,
                caption=f"Logs for {service}."
             )
             await reply_msg.delete()
         finally:
             if os.path.exists(file_path):
                 os.remove(file_path)
    else:
        if not output.strip():
            output = "(No logs found)"
        await reply_msg.edit_text(f"```\n{output}\n```")

@Client.on_message(filters.command("restart") & filters.private)
@requires_auth
async def restart_cmd(client: Client, message: Message):
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
         allowed = system_service.get_allowed_services()
         await message.reply(f"Usage: /restart <service>\nAllowed: {', '.join(allowed)}")
         return

    service = parts[1].strip()
    if not system_service.is_service_allowed(service):
         await message.reply("Service not in allowlist.")
         return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Confirm", callback_data=f"restart_confirm_{service}"),
            InlineKeyboardButton("Cancel", callback_data="restart_cancel")
        ]
    ])
    await message.reply(f"Are you sure you want to restart {service}?", reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^restart_"))
@requires_auth
async def restart_callback(client: Client, callback: CallbackQuery):
    data = callback.data
    if data == "restart_cancel":
        await callback.message.edit_text("Restart cancelled.")
        return

    service = data[len("restart_confirm_"):]
    if not system_service.is_service_allowed(service):
         await callback.answer("Service not allowed.", show_alert=True)
         return

    await db.add_history(callback.from_user.id, f"restart {service}")
    await callback.message.edit_text(f"Restarting {service}...")

    # We need sudo for systemctl usually, assuming bot has sudo NOPASSWD for these or runs as a user that can restart them
    cmd = f"sudo systemctl restart {service}"
    output, _ = await cmd_runner.run(cmd)

    await callback.message.edit_text(f"Restart command executed.\n```\n{output}\n```")

@Client.on_message(filters.command("history") & filters.private)
@requires_auth
async def history_cmd(client: Client, message: Message):
    history = await db.get_history(message.from_user.id)
    if not history:
         await message.reply("No history found.")
         return

    buttons = []
    for row in history:
        cmd = row['command'][:20] + ("..." if len(row['command']) > 20 else "")
        buttons.append([InlineKeyboardButton(cmd, callback_data=f"hist_{row['record_id']}")])

    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply("Command History:", reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^hist_"))
@requires_auth
async def history_callback(client: Client, callback: CallbackQuery):
    record_id = int(callback.data.split("_")[1])
    record = await db.get_history_by_id(record_id)

    if not record or record['telegram_id'] != callback.from_user.id:
        await callback.answer("Record not found or unauthorized.", show_alert=True)
        return

    await callback.message.edit_text(f"**Command:**\n`{record['command']}`\n**Time:** {record['timestamp']}")

@Client.on_message(filters.command("clearhistory") & filters.private)
@requires_auth
async def clearhistory_cmd(client: Client, message: Message):
    await db.clear_history(message.from_user.id)
    await message.reply("History cleared.")
