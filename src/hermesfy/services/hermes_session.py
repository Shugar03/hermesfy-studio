"""Hermes Agent subprocess manager — spawns, monitors, cancels, and collects output.

Manages lifecycle of `hermes chat -q` as a subprocess for agentic DAG operations.
One subprocess per chat turn. Supports soft/hard timeouts, cancellation, env isolation,
concurrency limiting, and safe cleanup.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from hermesfy.api.settings import Settings

logger = logging.getLogger("hermesfy.hermes_session")

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class HermesTurnConfig:
    """Configuration for a single Hermes agent turn."""
    session_id: str
    turn_id: str
    message: str
    provider: str = "openrouter"
    model: str = "moonshotai/kimi-k2.6"
    skills: str = "hermesfy-agent"
    timeout_soft: int = 120  # emit heartbeat/narration after this
    timeout_hard: int = 300  # kill process after this
    cwd: str = "/opt/hermesfy-studio"


@dataclass
class HermesTurnResult:
    """Result of a completed (or failed/cancelled) Hermes turn."""
    turn_id: str
    session_id: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    cancelled: bool = False
    timed_out: bool = False
    started_at: str = ""
    finished_at: str = ""
    pid: int = 0


class HermesSessionManager:
    """Manages Hermes Agent subprocesses with concurrency limits and safety."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._binary = settings.hermes_binary
        # Resolve to absolute path if just a name
        if "/" not in self._binary:
            resolved = shutil.which(self._binary)
            if resolved:
                self._binary = resolved
        self._semaphore = asyncio.Semaphore(settings.hermes_max_concurrent)
        self._active: dict[str, asyncio.subprocess.Process] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    async def run_turn(self, config: HermesTurnConfig) -> HermesTurnResult:
        """Execute one Hermes agent turn as a subprocess.

        Returns a HermesTurnResult with stdout, stderr, exit code, and timing.
        Raises no exception — errors are captured in the result.
        """
        async with self._semaphore:
            return await self._run_turn_internal(config)

    async def cancel_turn(self, turn_id: str) -> bool:
        """Cancel a running turn. Returns True if a process was found and killed."""
        proc = self._active.pop(turn_id, None)
        if proc is None:
            return False
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
            return True
        except ProcessLookupError:
            return True  # already dead
        except Exception:
            logger.exception("Error cancelling turn %s", turn_id)
            return False

    @property
    def active_count(self) -> int:
        return len(self._active)

    # ── Internal ───────────────────────────────────────────────────────────

    async def _run_turn_internal(self, config: HermesTurnConfig) -> HermesTurnResult:
        started_at = datetime.now(timezone.utc).isoformat()
        safe_env = self._build_safe_env()

        args = [
            self._binary, "chat", "-q",
            config.message,
            "--provider", config.provider,
            "--model", config.model,
            "--skills", config.skills,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=config.cwd,
                env=safe_env,
            )
        except FileNotFoundError:
            return HermesTurnResult(
                turn_id=config.turn_id,
                session_id=config.session_id,
                exit_code=-1,
                stderr=f"Hermes binary not found: {self._binary}",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        except PermissionError:
            return HermesTurnResult(
                turn_id=config.turn_id,
                session_id=config.session_id,
                exit_code=-2,
                stderr=f"Hermes binary not executable: {self._binary}",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

        self._active[config.turn_id] = proc
        pid = proc.pid or 0
        cancelled = False
        timed_out = False

        stdout_bytes = b""
        stderr_bytes = b""

        async def _read_stream(stream, buffer: bytearray) -> None:
            while True:
                try:
                    chunk = await stream.read(4096)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                except (asyncio.CancelledError, Exception):
                    break

        stdout_buf = bytearray()
        stderr_buf = bytearray()

        stdout_task = asyncio.create_task(_read_stream(proc.stdout, stdout_buf))
        stderr_task = asyncio.create_task(_read_stream(proc.stderr, stderr_buf))

        try:
            await asyncio.wait_for(proc.wait(), timeout=config.timeout_hard)
        except asyncio.TimeoutError:
            timed_out = True
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            except ProcessLookupError:
                pass
        except asyncio.CancelledError:
            cancelled = True
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    proc.kill()
                    await proc.wait()
            except ProcessLookupError:
                pass
        except Exception:
            logger.exception("Unexpected error running turn %s", config.turn_id)
        finally:
            stdout_task.cancel()
            stderr_task.cancel()
            try:
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            except Exception:
                pass
            stdout_bytes = bytes(stdout_buf)
            stderr_bytes = bytes(stderr_buf)
            self._active.pop(config.turn_id, None)

        finished_at = datetime.now(timezone.utc).isoformat()

        return HermesTurnResult(
            turn_id=config.turn_id,
            session_id=config.session_id,
            exit_code=proc.returncode if not cancelled and not timed_out else (-9 if cancelled else -15),
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            cancelled=cancelled,
            timed_out=timed_out,
            started_at=started_at,
            finished_at=finished_at,
            pid=pid,
        )

    def _build_safe_env(self) -> dict[str, str]:
        """Build a safe environment allowlist for the Hermes subprocess.

        Only passes through explicitly allowed variables plus required keys.
        Strips user-specific and dangerous variables.
        """
        allowed_prefixes = [
            "HERMESFY_", "FAL_", "FAL_KEY", "GOOGLE_API_KEY",
            "OPENAI_API_KEY", "OPENROUTER_API_KEY", "PATH", "HOME",
            "USER", "LOGNAME", "LANG", "LC_", "TZ",
        ]
        env = {}
        for key, value in os.environ.items():
            for prefix in allowed_prefixes:
                if key.startswith(prefix):
                    env[key] = value
                    break
        # Ensure PATH is at least present
        if "PATH" not in env:
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
        # Ensure genmedia and other binaries work
        env["GENMEDIA_NO_UPDATE"] = "1"
        env["GENMEDIA_NO_ANALYTICS"] = "1"
        return env


# ── Convenience factory ───────────────────────────────────────────────────────

def create_hermes_session_manager(settings: Settings) -> HermesSessionManager:
    """Create a HermesSessionManager from Settings."""
    return HermesSessionManager(settings)
