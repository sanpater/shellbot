import os
import pty
import asyncio
import re
import signal
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PTYSession:
    def __init__(self, user_id: int, client, chat_id: int):
        self.user_id = user_id
        self.client = client
        self.chat_id = chat_id

        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.pid: Optional[int] = None

        self.last_activity = time.time()
        self.output_buffer = ""
        self.buffer_size_limit = int(os.environ.get('MESSAGE_CHUNK_SIZE', 3500))
        self.idle_timeout = int(os.environ.get('SHELL_IDLE_TIMEOUT', 3600))

        self._reader_task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._timeout_task: Optional[asyncio.Task] = None
        self._running = False

        # ANSI escape regex
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def start(self):
        # Create PTY
        self.master_fd, self.slave_fd = pty.openpty()

        # Fork and exec bash
        self.pid = os.fork()
        if self.pid == 0:
            # Child process
            os.setsid() # New process group
            os.close(self.master_fd)
            os.dup2(self.slave_fd, 0)
            os.dup2(self.slave_fd, 1)
            os.dup2(self.slave_fd, 2)
            if self.slave_fd > 2:
                os.close(self.slave_fd)

            # Execute bash
            os.execv('/bin/bash', ['/bin/bash', '-i'])
        else:
            # Parent process
            os.close(self.slave_fd)
            self._set_nonblocking(self.master_fd)
            self._running = True

            # Add reader to event loop
            loop = asyncio.get_event_loop()
            loop.add_reader(self.master_fd, self._read_pty)

            # Start background tasks
            self._flush_task = asyncio.create_task(self._flush_loop())
            self._timeout_task = asyncio.create_task(self._check_timeout())

            logger.info(f"Started PTY session for user {self.user_id} with PID {self.pid}")

    def _set_nonblocking(self, fd):
        import fcntl
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def _read_pty(self):
        try:
            data = os.read(self.master_fd, 4096)
            if not data:
                self.terminate()
                return

            text = data.decode('utf-8', errors='replace')
            clean_text = self.ansi_escape.sub('', text)
            self.output_buffer += clean_text
            self.last_activity = time.time()

            if len(self.output_buffer) >= self.buffer_size_limit:
                asyncio.create_task(self._flush_buffer())

        except BlockingIOError:
            pass
        except OSError as e:
            logger.error(f"OSError reading PTY for user {self.user_id}: {e}")
            self.terminate()

    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(1.0) # Flush interval
            if self.output_buffer:
                await self._flush_buffer()

    async def _flush_buffer(self):
        if not self.output_buffer:
            return

        text_to_send = self.output_buffer[:self.buffer_size_limit]
        self.output_buffer = self.output_buffer[self.buffer_size_limit:]

        if text_to_send.strip():
            try:
                await self.client.send_message(
                    chat_id=self.chat_id,
                    text=f"```\n{text_to_send}\n```"
                )
            except Exception as e:
                logger.error(f"Failed to send PTY output to user {self.user_id}: {e}")

    async def _check_timeout(self):
        while self._running:
            await asyncio.sleep(60)
            if time.time() - self.last_activity > self.idle_timeout:
                logger.info(f"PTY session for user {self.user_id} timed out")
                await self.client.send_message(self.chat_id, "Shell session closed due to inactivity.")
                self.terminate()

    def write(self, text: str):
        if self._running and self.master_fd:
            try:
                os.write(self.master_fd, text.encode('utf-8'))
                self.last_activity = time.time()
            except OSError as e:
                logger.error(f"Failed to write to PTY for user {self.user_id}: {e}")

    def terminate(self):
        if not self._running:
            return

        self._running = False

        # Remove reader
        try:
            loop = asyncio.get_event_loop()
            loop.remove_reader(self.master_fd)
        except Exception:
            pass

        # Cancel tasks
        if self._flush_task:
            self._flush_task.cancel()
        if self._timeout_task:
            self._timeout_task.cancel()

        # Kill process group
        if self.pid:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGTERM)
                time.sleep(0.1)
                os.killpg(os.getpgid(self.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                 logger.error(f"Error killing PTY process for user {self.user_id}: {e}")

        if self.master_fd:
            try:
                os.close(self.master_fd)
            except Exception:
                pass

        logger.info(f"Terminated PTY session for user {self.user_id}")

class PTYManager:
    def __init__(self):
        self.sessions: Dict[int, PTYSession] = {}
        self.max_sessions = int(os.environ.get('MAX_SHELL_SESSIONS', 5))

    def get_session(self, user_id: int) -> Optional[PTYSession]:
        return self.sessions.get(user_id)

    def start_session(self, user_id: int, client, chat_id: int) -> bool:
        if user_id in self.sessions:
            self.stop_session(user_id)

        if len(self.sessions) >= self.max_sessions:
            return False

        session = PTYSession(user_id, client, chat_id)
        session.start()
        self.sessions[user_id] = session
        return True

    def stop_session(self, user_id: int):
        if user_id in self.sessions:
            self.sessions[user_id].terminate()
            del self.sessions[user_id]

    def stop_all(self):
        for user_id in list(self.sessions.keys()):
            self.stop_session(user_id)

pty_manager = PTYManager()
