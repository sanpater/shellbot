from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.services.system_service import system_service
from bot.services.rate_limit import requires_auth
import os
import logging

logger = logging.getLogger(__name__)


import json
import uuid

# Memory cache for paths to bypass Telegram's 64-byte callback limit
# For a production bot with many users, this should go in a Redis/SQLite DB.
# For MVP, a simple dict works.
path_cache = {}

def get_path_id(path: str) -> str:
    for k, v in path_cache.items():
        if v == path:
            return k

    path_id = str(uuid.uuid4())[:8]
    path_cache[path_id] = path
    return path_id

def get_path_from_id(path_id: str) -> str:
    return path_cache.get(path_id)

def generate_browser_keyboard(current_path: str):
    buttons = []

    try:
        items = os.listdir(current_path)
    except PermissionError:
        return InlineKeyboardMarkup([[InlineKeyboardButton("Permission Denied", callback_data="noop")]])
    except Exception as e:
        return InlineKeyboardMarkup([[InlineKeyboardButton(f"Error: {e}", callback_data="noop")]])

    # Sort: folders first, then files
    items.sort(key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower()))

    for item in items:
        item_path = os.path.join(current_path, item)
        path_id = get_path_id(item_path)

        if os.path.isdir(item_path):
            buttons.append([InlineKeyboardButton(f"📁 {item}", callback_data=f"dir:{path_id}")])
        else:
            # Show file size
            try:
                size_bytes = os.path.getsize(item_path)
                size_kb = size_bytes / 1024
                if size_kb > 1024:
                    size_str = f"{size_kb / 1024:.1f}MB"
                else:
                    size_str = f"{size_kb:.1f}KB"
                buttons.append([InlineKeyboardButton(f"📄 {item} ({size_str})", callback_data=f"file:{path_id}")])
            except Exception:
                buttons.append([InlineKeyboardButton(f"📄 {item}", callback_data=f"file:{path_id}")])

    # Navigation buttons
    nav_buttons = []
    parent_dir = os.path.dirname(current_path)
    if parent_dir and parent_dir != current_path:
        parent_id = get_path_id(parent_dir)
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"dir:{parent_id}"))

    home_id = get_path_id(os.path.expanduser("~"))
    nav_buttons.append(InlineKeyboardButton("🏠 Home", callback_data=f"dir:{home_id}"))

    root_id = get_path_id("/")
    nav_buttons.append(InlineKeyboardButton("🌐 Root", callback_data=f"dir:{root_id}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("download") & filters.private)
@requires_auth
async def download_cmd(client: Client, message: Message):
    parts = message.text.split(" ", 1)
    if len(parts) >= 2:
        # Direct download if path provided
        file_path = os.path.expanduser(parts[1].strip())
        if not os.path.exists(file_path):
             await message.reply("File does not exist.")
             return
        if not os.path.isfile(file_path):
             await message.reply("Path is not a regular file.")
             return
        if not os.access(file_path, os.R_OK):
             await message.reply("Permission denied to read file.")
             return

        reply_msg = await message.reply("Uploading...")
        try:
             await client.send_document(chat_id=message.chat.id, document=file_path)
             await reply_msg.delete()
        except Exception as e:
             logger.error(f"Error uploading file: {e}")
             await reply_msg.edit_text(f"Error uploading file: {str(e)}")
        return

    # Interactive browser
    current_path = os.path.expanduser("~")
    keyboard = generate_browser_keyboard(current_path)
    await message.reply(f"📂 Browsing: `{current_path}`\n\nSelect a file to download or a folder to navigate:", reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^(dir|file):") & filters.private)
@requires_auth
async def download_callback(client: Client, callback: CallbackQuery):
    action, path_id = callback.data.split(":", 1)

    path = get_path_from_id(path_id)
    if not path:
        await callback.answer("Path expired from cache. Please run /download again.", show_alert=True)
        return

    if action == "dir":
        if not os.path.exists(path) or not os.path.isdir(path):
            await callback.answer("Directory not found.", show_alert=True)
            return

        if not os.access(path, os.R_OK | os.X_OK):
            await callback.answer("Permission denied.", show_alert=True)
            return

        keyboard = generate_browser_keyboard(path)
        await callback.message.edit_text(f"📂 Browsing: `{path}`\n\nSelect a file to download or a folder to navigate:", reply_markup=keyboard)

    elif action == "file":
        if not os.path.exists(path) or not os.path.isfile(path):
            await callback.answer("File not found.", show_alert=True)
            return

        if not os.access(path, os.R_OK):
            await callback.answer("Permission denied.", show_alert=True)
            return

        await callback.message.edit_text(f"Uploading `{path}`...")
        try:
             await client.send_document(chat_id=callback.message.chat.id, document=path)
             # Restore browser after sending
             keyboard = generate_browser_keyboard(os.path.dirname(path))
             await callback.message.reply(f"📂 Browsing: `{os.path.dirname(path)}`", reply_markup=keyboard)
        except Exception as e:
             logger.error(f"Error uploading file: {e}")
             await callback.message.edit_text(f"Error uploading file: {str(e)}")

@Client.on_message((filters.document | filters.photo | filters.video | filters.audio) & filters.private)
@requires_auth
async def upload_handler(client: Client, message: Message):
    if message.document:
         file_name = message.document.file_name
    elif message.photo:
         file_name = f"photo_{message.message_id}.jpg"
    elif message.video:
         file_name = message.video.file_name or f"video_{message.message_id}.mp4"
    elif message.audio:
         file_name = message.audio.file_name or f"audio_{message.message_id}.mp3"
    else:
         file_name = f"file_{message.message_id}"

    safe_path = system_service.get_safe_file_path(message.from_user.id, file_name)

    reply_msg = await message.reply("Downloading...")
    try:
         await message.download(file_name=safe_path)
         await reply_msg.edit_text(f"File saved to `{safe_path}`")
    except Exception as e:
         logger.error(f"Error downloading file: {e}")
         await reply_msg.edit_text(f"Error downloading file: {str(e)}")
