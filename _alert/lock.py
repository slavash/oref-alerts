"""File locking utilities for single-instance enforcement."""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from typing import Generator


def try_acquire_lock(lock_path: str) -> bool:
    """Return True if *lock_path* can be exclusively locked (non-blocking)."""
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return True
        except BlockingIOError:
            os.close(fd)
            return False
    except OSError:
        return False


@contextmanager
def hold_lock(lock_path: str) -> Generator[int, None, None]:
    """Context manager that holds an exclusive lock for its lifetime."""
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            pass
