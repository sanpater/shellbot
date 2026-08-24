import asyncio
import os
import signal
import time
import logging
import tempfile
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class CmdRunner:
    def __init__(self):
        self.max_capture_bytes = int(os.environ.get('MAX_CAPTURE_BYTES', 5242880))
        self.message_chunk_size = int(os.environ.get('MESSAGE_CHUNK_SIZE', 3500))
        self.timeout = int(os.environ.get('COMMAND_TIMEOUT', 60))

    async def run(self, command: str) -> Tuple[str, Optional[str]]:
        """
        Runs a command using bash. Returns (output_text, file_path_if_large).
        Uses process groups to ensure child processes are cleaned up.
        """
        logger.info(f"Executing command: {command}")

        try:
            # Run command with preexec_fn to create a new process group
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, # Merge stderr into stdout
                preexec_fn=os.setsid,
                executable='/bin/bash'
            )

            output = b""
            truncated = False
            start_time = time.time()

            # Read output with timeout and capture limits
            while True:
                time_left = self.timeout - (time.time() - start_time)
                if time_left <= 0:
                    break

                try:
                    chunk = await asyncio.wait_for(process.stdout.read(4096), timeout=time_left)
                    if not chunk:
                        break # EOF

                    if len(output) + len(chunk) > self.max_capture_bytes:
                        output += chunk[:self.max_capture_bytes - len(output)]
                        truncated = True
                        break
                    else:
                        output += chunk
                except asyncio.TimeoutError:
                    break

            # Cleanup process
            try:
                if process.returncode is None:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    await asyncio.sleep(0.1)
                    if process.returncode is None:
                        os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error killing process group {process.pid}: {e}")

            decoded_output = output.decode('utf-8', errors='replace')
            if truncated:
                decoded_output += "\n\n[OUTPUT TRUNCATED: Max capture size reached]"

            if process.returncode is None:
                decoded_output += f"\n\n[PROCESS KILLED: Timeout {self.timeout}s exceeded]"

            if len(decoded_output) > self.message_chunk_size:
                # Write to temp file
                fd, path = tempfile.mkstemp(suffix=".txt", text=True)
                with os.fdopen(fd, 'w') as f:
                    f.write(decoded_output)
                return "Output too large for a message. Sent as a file.", path

            return decoded_output, None

        except Exception as e:
            logger.exception(f"Error executing command: {command}")
            return f"Error executing command: {str(e)}", None

cmd_runner = CmdRunner()
