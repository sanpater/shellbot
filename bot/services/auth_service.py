import bcrypt
import time
import os
import logging
from bot.services.db import db

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.login_max_fails = int(os.environ.get('LOGIN_MAX_FAILS', 3))
        self.login_lockout_seconds = int(os.environ.get('LOGIN_LOCKOUT_MINUTES', 10)) * 60

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password: str, hashed: str) -> bool:
        if not hashed:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    async def get_user_status(self, telegram_id: int):
        user = await db.get_user(telegram_id)
        if not user:
            return None
        return user

    async def authenticate(self, telegram_id: int, password: str) -> tuple[bool, str]:
        user = await db.get_user(telegram_id)
        if not user:
            return False, "User not found."

        now = time.time()

        if user['lock_until'] > now:
            remaining = int((user['lock_until'] - now) / 60)
            return False, f"Account locked. Try again in {remaining} minutes."

        # If user has no hash yet, first login sets the password
        if not user['hash']:
            hashed = self.hash_password(password)
            await db.update_user(telegram_id, hash=hashed, is_auth=1, fails=0, lock_until=0)
            return True, "Passphrase set successfully. You are now authenticated."

        if self.check_password(password, user['hash']):
            await db.update_user(telegram_id, is_auth=1, fails=0, lock_until=0)
            return True, "Authentication successful."
        else:
            fails = user['fails'] + 1
            lock_until = 0
            msg = "Invalid passphrase."
            if fails >= self.login_max_fails:
                lock_until = now + self.login_lockout_seconds
                msg = f"Too many failed attempts. Account locked for {self.login_lockout_seconds // 60} minutes."

            await db.update_user(telegram_id, fails=fails, lock_until=lock_until)
            return False, msg

    async def logout(self, telegram_id: int):
        await db.update_user(telegram_id, is_auth=0)

auth_service = AuthService()
