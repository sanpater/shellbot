from bot.handlers.auth import get_auth_handlers
from bot.handlers.shell import get_shell_handlers
from bot.handlers.system import get_system_handlers
from bot.handlers.file_transfer import get_file_transfer_handlers

def register_all_handlers():
    get_auth_handlers()
    get_shell_handlers()
    get_system_handlers()
    get_file_transfer_handlers()
