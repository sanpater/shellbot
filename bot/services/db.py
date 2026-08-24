import aiosqlite
import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = "data/bot.db"
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self, db_path: str = None):
        if db_path:
            self.db_path = db_path

        # Ensure directory exists
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrency
        await self._conn.execute('PRAGMA journal_mode=WAL')
        await self._conn.commit()
        logger.info(f"Connected to database at {self.db_path} with WAL mode")

        await self._init_schema()

    async def _init_schema(self):
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS history (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                command TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        ''')

        await self._conn.commit()
        logger.info("Database schema initialized")

    async def close(self):
        if self._conn:
            await self._conn.close()
            logger.info("Database connection closed")

    async def get_user(self, telegram_id: int) -> Optional[aiosqlite.Row]:
        async with self._conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)) as cursor:
            return await cursor.fetchone()

    async def create_user(self, telegram_id: int):
        await self._conn.execute(
            'INSERT OR IGNORE INTO users (telegram_id) VALUES (?)',
            (telegram_id,)
        )
        await self._conn.commit()

    async def update_user(self, telegram_id: int, **kwargs):
        if not kwargs:
            return

        fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(telegram_id)

        await self._conn.execute(
            f'UPDATE users SET {fields} WHERE telegram_id = ?',
            values
        )
        await self._conn.commit()

    async def delete_user(self, telegram_id: int):
        await self._conn.execute('DELETE FROM users WHERE telegram_id = ?', (telegram_id,))
        await self._conn.commit()

    async def get_all_users(self) -> List[aiosqlite.Row]:
        async with self._conn.execute('SELECT * FROM users') as cursor:
            return await cursor.fetchall()

    async def add_history(self, telegram_id: int, command: str) -> int:
        cursor = await self._conn.execute(
            'INSERT INTO history (telegram_id, command) VALUES (?, ?)',
            (telegram_id, command)
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_history(self, telegram_id: int, limit: int = 10) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            'SELECT * FROM history WHERE telegram_id = ? ORDER BY timestamp DESC LIMIT ?',
            (telegram_id, limit)
        ) as cursor:
            return await cursor.fetchall()

    async def clear_history(self, telegram_id: int):
        await self._conn.execute('DELETE FROM history WHERE telegram_id = ?', (telegram_id,))
        await self._conn.commit()

    async def get_history_by_id(self, record_id: int) -> Optional[aiosqlite.Row]:
         async with self._conn.execute(
             'SELECT * FROM history WHERE record_id = ?',
             (record_id,)
         ) as cursor:
             return await cursor.fetchone()

# Global database instance
db = Database()

async def init_db(db_path: str = None):
    await db.connect(db_path)

async def close_db():
    await db.close()
