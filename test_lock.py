"""Tests for file-locking and stale-lock recovery in _alert.lock.

Covers the popup-stops-appearing bug: if a popup process dies while
holding the lock, subsequent popups must still be able to spawn.
"""
# pylint: disable=missing-function-docstring
from __future__ import annotations

import fcntl
import os
import sys
import textwrap
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
_PYTHON = str(PROJECT_DIR / ".venv" / "bin" / "python3")
if not os.path.exists(_PYTHON):
    _PYTHON = sys.executable


def _run_python(code: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_DIR),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )


# ── try_acquire_lock ─────────────────────────────────────────────────────

class TestTryAcquireLock:
    """Basic behavior of try_acquire_lock."""

    def test_returns_true_when_no_lock_exists(self, tmp_path):
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock
            print(try_acquire_lock({lock!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "True" in result.stdout

    def test_returns_false_when_lock_owned_by_live_process(self, tmp_path):
        """A live child's PID in the lock file must block acquisition."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys, time
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock, hold_lock

            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(r)
                with hold_lock({lock!r}):
                    os.write(w, b"ready")
                    os.close(w)
                    time.sleep(5)
                os._exit(0)
            else:
                os.close(w)
                os.read(r, 16)
                os.close(r)
                print(try_acquire_lock({lock!r}))
                os.kill(pid, 9)
                os.waitpid(pid, 0)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "False" in result.stdout

    def test_returns_true_after_child_popup_exits(self, tmp_path):
        """After the popup subprocess exits, the parent can reacquire."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock, hold_lock

            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(r)
                with hold_lock({lock!r}):
                    os.write(w, b"ready")
                    os.close(w)
                os._exit(0)
            else:
                os.close(w)
                os.read(r, 16)
                os.close(r)
                os.waitpid(pid, 0)
                print(try_acquire_lock({lock!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "True" in result.stdout

    def test_repeated_calls_return_true_without_lock(self, tmp_path):
        """Without a live popup, try_acquire_lock always returns True."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock

            first = try_acquire_lock({lock!r})
            second = try_acquire_lock({lock!r})
            print(f"FIRST:{{first}}")
            print(f"SECOND:{{second}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "FIRST:True" in result.stdout
        assert "SECOND:True" in result.stdout


# ── write_lock_pid ───────────────────────────────────────────────────────

class TestWriteLockPid:
    """Verify write_lock_pid writes the child PID atomically."""

    def test_writes_pid_to_lock_file(self, tmp_path):
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import write_lock_pid

            write_lock_pid({lock!r}, 12345)
            content = open({lock!r}).read().strip()
            print(f"CONTENT:{{content}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "CONTENT:12345" in result.stdout

    def test_write_then_check_blocks(self, tmp_path):
        """After writing a live PID, try_acquire_lock returns False."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import write_lock_pid, try_acquire_lock

            write_lock_pid({lock!r}, os.getpid())
            print(try_acquire_lock({lock!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "False" in result.stdout

    def test_write_dead_pid_then_check_succeeds(self, tmp_path):
        """After writing a dead PID, try_acquire_lock returns True."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import write_lock_pid, try_acquire_lock

            # Fork and reap a child to get a dead PID.
            pid = os.fork()
            if pid == 0:
                os._exit(0)
            os.waitpid(pid, 0)
            write_lock_pid({lock!r}, pid)
            print(try_acquire_lock({lock!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "True" in result.stdout


# ── hold_lock ────────────────────────────────────────────────────────────

class TestHoldLock:
    """Verify hold_lock writes PID and holds exclusive flock."""

    def test_writes_pid_to_lock_file(self, tmp_path):
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import hold_lock

            with hold_lock({lock!r}):
                content = open({lock!r}).read().strip()
                print(f"PID_MATCH:{{content == str(os.getpid())}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "PID_MATCH:True" in result.stdout

    def test_flock_is_exclusive(self, tmp_path):
        """A child process cannot acquire the flock while the parent holds it."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import fcntl, os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import hold_lock

            with hold_lock({lock!r}):
                r, w = os.pipe()
                pid = os.fork()
                if pid == 0:
                    os.close(r)
                    fd = os.open({lock!r}, os.O_RDONLY)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        os.write(w, b"got_lock")
                    except BlockingIOError:
                        os.write(w, b"blocked")
                    finally:
                        os.close(fd)
                        os.close(w)
                    os._exit(0)
                else:
                    os.close(w)
                    msg = os.read(r, 32).decode()
                    os.close(r)
                    os.waitpid(pid, 0)
                    print(f"CHILD:{{msg}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "CHILD:blocked" in result.stdout


# ── Stale lock recovery ──────────────────────────────────────────────────

class TestStaleLockRecovery:
    """A dead process must not permanently block new popups."""

    def test_stale_lock_from_dead_process_is_recovered(self, tmp_path):
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import fcntl, os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock

            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(r)
                fd = os.open({lock!r}, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
                fcntl.flock(fd, fcntl.LOCK_EX)
                os.write(fd, f"{{os.getpid()}}\\n".encode())
                os.fsync(fd)
                os.write(w, b"ready")
                os.close(w)
                os._exit(1)
            else:
                os.close(w)
                os.read(r, 16)
                os.close(r)
                os.waitpid(pid, 0)
                print(f"RECOVERED:{{try_acquire_lock({lock!r})}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "RECOVERED:True" in result.stdout

    def test_stale_lock_with_invalid_pid_is_recovered(self, tmp_path):
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock

            with open({lock!r}, "w") as f:
                f.write("not_a_pid\\n")
            print(f"RECOVERED:{{try_acquire_lock({lock!r})}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "RECOVERED:True" in result.stdout

    def test_stale_lock_with_empty_file_is_recovered(self, tmp_path):
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock

            open({lock!r}, "w").close()
            print(f"RECOVERED:{{try_acquire_lock({lock!r})}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "RECOVERED:True" in result.stdout

    def test_full_popup_lifecycle_allows_reacquisition(self, tmp_path):
        """parent spawns child → child holds lock → child exits → parent can spawn again."""
        lock = str(tmp_path / "test.lock")
        code = textwrap.dedent(f"""\
            import os, sys, time
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            from _alert.lock import try_acquire_lock, write_lock_pid, hold_lock

            # First alert: parent checks, spawns child, writes child PID.
            assert try_acquire_lock({lock!r}) is True
            r, w = os.pipe()
            r2, w2 = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(r)
                os.close(w2)
                with hold_lock({lock!r}):
                    os.write(w, b"ready")
                    os.close(w)
                    # Wait for parent to write our PID and verify.
                    os.read(r2, 16)
                    os.close(r2)
                os._exit(0)
            else:
                os.close(w)
                os.close(r2)
                os.read(r, 16)
                os.close(r)
                write_lock_pid({lock!r}, pid)
                # While child is alive, lock is held.
                assert try_acquire_lock({lock!r}) is False
                # Let child exit.
                os.write(w2, b"go")
                os.close(w2)
                os.waitpid(pid, 0)

            # Second alert: child is dead, parent can reacquire.
            result = try_acquire_lock({lock!r})
            print(f"SECOND_ACQUIRED:{{result}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "SECOND_ACQUIRED:True" in result.stdout


# ── Popup cleanup no longer deletes lock file ────────────────────────────

class TestPopupCleanup:
    """Verify _cleanup in popup.py only removes the IPC file, not the lock."""

    def test_cleanup_removes_ipc_but_not_lock(self, tmp_path):
        ipc = tmp_path / "alerts.json"
        lock = tmp_path / "popup.lock"
        ipc.write_text("[]")
        lock.write_text("12345")
        code = textwrap.dedent(f"""\
            import os, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})

            ipc_path = {str(ipc)!r}
            lock_path = {str(lock)!r}

            def _cleanup():
                try:
                    os.remove(ipc_path)
                except OSError:
                    pass

            _cleanup()
            print(f"IPC_EXISTS:{{os.path.exists(ipc_path)}}")
            print(f"LOCK_EXISTS:{{os.path.exists(lock_path)}}")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "IPC_EXISTS:False" in result.stdout
        assert "LOCK_EXISTS:True" in result.stdout
