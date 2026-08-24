import psutil
import os
import time
import logging
import re
from typing import List

logger = logging.getLogger(__name__)

class SystemService:
    def __init__(self):
        self.allowed_services = [
            s.strip() for s in os.environ.get('ALLOWED_SERVICES', '').split(',') if s.strip()
        ]
        self.upload_dir = os.environ.get('UPLOAD_DIR', 'data/uploads')

    def get_status(self) -> str:
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = time.time() - psutil.boot_time()

        days, remainder = divmod(int(boot_time), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime = f"{days}d {hours}h {minutes}m"

        return (
            f"**System Status:**\n"
            f"CPU Usage: {cpu_percent}%\n"
            f"Memory Usage: {mem.percent}% ({mem.used / (1024**3):.1f}GB / {mem.total / (1024**3):.1f}GB)\n"
            f"Disk Usage: {disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)\n"
            f"Uptime: {uptime}"
        )

    def is_service_allowed(self, service_name: str) -> bool:
        return service_name in self.allowed_services

    def get_allowed_services(self) -> List[str]:
        return self.allowed_services

    def get_user_upload_dir(self, user_id: int) -> str:
        dir_path = os.path.join(self.upload_dir, str(user_id))
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def sanitize_filename(self, filename: str) -> str:
        # Keep only alphanumeric characters, dots, dashes and underscores
        clean = re.sub(r'[^a-zA-Z0-9.\-_]', '_', filename)
        if not clean or clean.startswith('.'):
            clean = "unnamed_file"
        return clean

    def get_safe_file_path(self, user_id: int, filename: str) -> str:
        safe_filename = self.sanitize_filename(filename)
        base_dir = self.get_user_upload_dir(user_id)

        # Handle collisions
        file_path = os.path.join(base_dir, safe_filename)
        if not os.path.exists(file_path):
            return file_path

        name, ext = os.path.splitext(safe_filename)
        counter = 1
        while True:
            new_path = os.path.join(base_dir, f"{name}_{counter}{ext}")
            if not os.path.exists(new_path):
                return new_path
            counter += 1

system_service = SystemService()
