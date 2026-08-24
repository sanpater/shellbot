# VPS Admin Telegram Bot

A secure, multi-user Telegram bot for Linux VPS administration using Pyrofork (Pyrogram-compatible MTProto API).

## Features
- Secure authentication (bcrypt stored in SQLite)
- Multi-user support with an Admin role
- Brute-force protection & rate limiting
- Interactive PTY Shell (`/shell`) with process group cleanup
- Bash Command execution (`/cmd`) with timeout and capture limits
- Allowed Services control (`/logs`, `/restart`)
- File transfers over MTProto (up to 2000 MiB)
- Safe user directories with collision-free downloads
- Strict security model (runs as unprivileged user, persistent DB state)

## Installation

1. Install Python 3.12+
2. `python -m venv venv && source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and configure it.
   - You must get your API_ID and API_HASH from [my.telegram.org](https://my.telegram.org).
   - Get your BOT_TOKEN from [@BotFather](https://t.me/BotFather).
   - Put your Telegram User ID in `ADMIN_ID`.

## Security Warning

**DO NOT RUN THIS AS ROOT.** This bot grants shell execution access to authenticated users on Telegram. You should run this bot as a dedicated, low-privilege Linux user.

Note: All authenticated users interact with the system under the **same Linux user**. There is no OS-level isolation between different Telegram users.

## Usage

Start the bot:
```bash
python main.py
```

### Initial Setup
1. Send `/login <your_chosen_passphrase>` to the bot. Since you are the initial admin (defined by `ADMIN_ID`), your first login sets your password in the database.
2. Once authenticated, you can use the bot.

### Commands
- `/login <passphrase>` - Authenticate yourself
- `/logout` - Log out
- `/cmd <bash command>` - Execute a bash command
- `/shell` - Start an interactive PTY session
- `/endshell` - Stop PTY
- `/ctrlc` - Send SIGINT to PTY
- `/ctrld` - Send EOF to PTY
- `/download <path>` - Download a file from the server
- `/status` - Server vitals (CPU/RAM/Disk)
- `/logs <service>` - View logs for allowlisted service
- `/restart <service>` - Restart allowlisted service
- `/history` - View your command history
- `/clearhistory` - Clear your history

**Admin Commands:**
- `/adduser <telegram_id>` - Begin add user process
- `/removeuser <telegram_id>` - Remove a user
- `/listusers` - List all users
- `/revoke <telegram_id>` - Revoke a user's session without deleting them
- `/resetpass <telegram_id>` - Reset a user's password

## Systemd Service

Use the included `bot.service` template to run this securely in the background as a restricted user. Adjust `User`, `Group`, and `WorkingDirectory`.

```bash
sudo cp bot.service /etc/systemd/system/vps-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now vps-bot
```
