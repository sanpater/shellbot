import asyncio
import os
import sys

# mock env variables
os.environ['API_ID'] = '1'
os.environ['API_HASH'] = 'test'
os.environ['BOT_TOKEN'] = 'test:test'
os.environ['ADMIN_ID'] = '123'
os.environ['DB_PATH'] = 'test.db'

from bot.services.db import init_db, db
from bot.handlers import auth

async def main():
    await init_db('test.db')
    user = await db.get_user(123)
    print("User found:", user)

if __name__ == "__main__":
    asyncio.run(main())
