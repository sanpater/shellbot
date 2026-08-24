from pyrogram import Client, filters
from pyrogram.types import Message
from bot.services.system_service import system_service
from bot.services.rate_limit import requires_auth
import os
import logging

logger = logging.getLogger(__name__)

def get_file_transfer_handlers():

    @Client.on_message(filters.command("download") & filters.private)
    @requires_auth
    async def download_cmd(client: Client, message: Message):
        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            await message.reply("Usage: /download <path>")
            return

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
             await client.send_document(
                 chat_id=message.chat.id,
                 document=file_path
             )
             await reply_msg.delete()
        except Exception as e:
             logger.error(f"Error uploading file: {e}")
             await reply_msg.edit_text(f"Error uploading file: {str(e)}")

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
