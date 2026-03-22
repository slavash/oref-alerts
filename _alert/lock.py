"""File locking utilities for single-instance enforcement."""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from typing import Generator


def _read_pid(path: str) -> int | None:
    """Read the PID stored in *path*, or return None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    """Return True if *pid* refers to a running (non-zombie) process."""
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    # kill(0) succeeds for zombies too — check /proc or waitpid.
    # On macOS there's no /proc; use waitpid with WNOHANG to detect
    # zombies that are our children.
    try:
        waited, _ = os.waitpid(pid, os.WNOHANG)
        if waited == pid:
            return False  # was a zombie child, now reaped
    except ChildProcessError:
        pass  # not our child — can't reap, fall through to ps check
    # For non-child zombies or to be safe, check process state via ps.
    try:
        import subprocess  # pylint: disable=import-outside-toplevel
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True, text=True, timeout=2, check=False,
        )
        stat = result.stdout.strip()
        if stat.startswith("Z"):
            return False
    except (OSError, subprocess.TimeoutExpired):
        pass
    return True


def try_acquire_lock(lock_path: str) -> bool:
    """Return True if no live popup process owns *lock_path*."""
    pid = _read_pid(lock_path)
    if pid is not None and _pid_alive(pid):
        return False
    return True


def write_lock_pid(lock_path: str, pid: int) -> None:
    """Atomically write *pid* into *lock_path*."""
    tmp = lock_path + f".{os.getpid()}"
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    os.write(fd, f"{pid}\n".encode())
    os.fsync(fd)
    os.close(fd)
    os.rename(tmp, lock_path)


@contextmanager
def hold_lock(lock_path: str) -> Generator[int, None, None]:
    """Context manager that holds an exclusive flock for its lifetime.

    Overwrites the lock file with the **current** (subprocess) PID so that
    ``try_acquire_lock`` in the parent can accurately check liveness.
    """
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.fsync(fd)
    try:
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            pass
