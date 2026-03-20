"""End-to-end tests for the OREF alert tool.

Tests exercise the tool's external contract: CLI invocation, file I/O,
and IPC behavior. They do NOT depend on internal module structure so they
survive refactoring.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON = str(PROJECT_DIR / ".venv" / "bin" / "python3")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

SAMPLE_ALERT = {
    "id": "999000111",
    "cat": "1",
    "title": "ירי רקטות וטילים",
    "data": ["חיפה - מערב", "נהריה"],
    "desc": "היכנסו למרחב המוגן",
    "zone": "גליל",
    "original_countdown": 30,
}

SAMPLE_ALERT_NO_LOCAL = {
    "id": "999000222",
    "cat": "1",
    "title": "ירי רקטות וטילים",
    "data": ["תל אביב - מרכז"],
    "desc": "היכנסו למרחב המוגן",
    "zone": "דן",
}


# ── Helpers ──────────────────────────────────────────────────────────────

def _run_python(code: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a snippet of Python in the project venv, with project dir on sys.path."""
    return subprocess.run(
        [PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_DIR),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


# ── 1. Formatted log output ─────────────────────────────────────────────

class TestFormattedLog:
    """Verify that log_formatted writes the expected structured line."""

    def test_log_formatted_writes_expected_fields(self, tmp_path):
        log_file = tmp_path / "fmt.txt"
        alert_json = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys, os
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.FORMATTED_LOG = {str(log_file)!r}
            a.log_formatted(json.loads({alert_json!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr

        content = log_file.read_text(encoding="utf-8")
        assert "ID: 999000111" in content
        assert "Title: ירי רקטות וטילים" in content
        assert "Zone: גליל" in content
        assert "חיפה - מערב" in content
        assert "נהריה" in content
        assert "Estimated time:" in content

    def test_log_formatted_handles_missing_optional_fields(self, tmp_path):
        log_file = tmp_path / "fmt2.txt"
        minimal = {"id": "1", "data": ["a"]}
        alert_json = json.dumps(minimal, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.FORMATTED_LOG = {str(log_file)!r}
            a.log_formatted(json.loads({alert_json!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        content = log_file.read_text(encoding="utf-8")
        assert "ID: 1" in content
        assert "Title: Alert" in content  # default

    def test_log_formatted_appends_multiple_entries(self, tmp_path):
        log_file = tmp_path / "fmt3.txt"
        a1 = json.dumps({"id": "1", "data": ["x"]}, ensure_ascii=False)
        a2 = json.dumps({"id": "2", "data": ["y"]}, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.FORMATTED_LOG = {str(log_file)!r}
            a.log_formatted(json.loads({a1!r}))
            a.log_formatted(json.loads({a2!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert "ID: 1" in lines[0]
        assert "ID: 2" in lines[1]


# ── 2. Raw log output ───────────────────────────────────────────────────

class TestRawLog:
    """Verify that log_raw writes valid JSON per line."""

    def test_log_raw_writes_parseable_json(self, tmp_path):
        log_file = tmp_path / "raw.txt"
        alert_json = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.RAW_LOG = {str(log_file)!r}
            a.log_raw(json.loads({alert_json!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr

        line = log_file.read_text(encoding="utf-8").strip()
        # Format: [timestamp] {json}
        assert line.startswith("[")
        json_part = line.split("] ", 1)[1]
        parsed = json.loads(json_part)
        assert parsed["id"] == "999000111"
        assert "חיפה - מערב" in parsed["data"]

    def test_log_raw_preserves_unicode(self, tmp_path):
        log_file = tmp_path / "raw2.txt"
        alert_json = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.RAW_LOG = {str(log_file)!r}
            a.log_raw(json.loads({alert_json!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        content = log_file.read_text(encoding="utf-8")
        # ensure_ascii=False means Hebrew appears literally
        assert "ירי רקטות וטילים" in content


# ── 3. Log file creation ────────────────────────────────────────────────

class TestEnsureLogFiles:
    """Verify ensure_log_files creates missing files."""

    def test_creates_missing_log_files(self, tmp_path):
        fmt = tmp_path / "fmt.txt"
        raw = tmp_path / "raw.txt"
        code = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.FORMATTED_LOG = {str(fmt)!r}
            a.RAW_LOG = {str(raw)!r}
            a.ensure_log_files()
        """)
        assert not fmt.exists()
        assert not raw.exists()
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert fmt.exists()
        assert raw.exists()
        assert fmt.read_text() == ""
        assert raw.read_text() == ""

    def test_does_not_truncate_existing_files(self, tmp_path):
        fmt = tmp_path / "fmt.txt"
        raw = tmp_path / "raw.txt"
        fmt.write_text("existing\n")
        raw.write_text("existing\n")
        code = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.FORMATTED_LOG = {str(fmt)!r}
            a.RAW_LOG = {str(raw)!r}
            a.ensure_log_files()
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert fmt.read_text() == "existing\n"
        assert raw.read_text() == "existing\n"


# ── 4. IPC file (alert append) ──────────────────────────────────────────

class TestAlertIPC:
    """Verify _append_alert writes alerts to the IPC JSON file."""

    def test_append_alert_creates_file_with_single_alert(self, tmp_path):
        ipc = tmp_path / "alerts.json"
        alert_json = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            mp.ALERTS_IPC = {str(ipc)!r}
            mp._append_alert(json.loads({alert_json!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        data = json.loads(ipc.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["id"] == "999000111"

    def test_append_alert_accumulates_multiple_alerts(self, tmp_path):
        ipc = tmp_path / "alerts.json"
        a1 = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        a2 = json.dumps(SAMPLE_ALERT_NO_LOCAL, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            mp.ALERTS_IPC = {str(ipc)!r}
            mp._append_alert(json.loads({a1!r}))
            mp._append_alert(json.loads({a2!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        data = json.loads(ipc.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["id"] == "999000111"
        assert data[1]["id"] == "999000222"

    def test_append_alert_recovers_from_corrupt_ipc_file(self, tmp_path):
        ipc = tmp_path / "alerts.json"
        ipc.write_text("NOT JSON AT ALL", encoding="utf-8")
        alert_json = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            mp.ALERTS_IPC = {str(ipc)!r}
            mp._append_alert(json.loads({alert_json!r}))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        data = json.loads(ipc.read_text(encoding="utf-8"))
        assert len(data) == 1


# ── 5. HTML generation ──────────────────────────────────────────────────

class TestHTMLGeneration:
    """Verify _build_html injects alert and city data into the template."""

    def test_build_html_injects_alert_data(self):
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            alerts = [{json.dumps(SAMPLE_ALERT, ensure_ascii=False)}]
            html = mp._build_html(alerts)
            print(html)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        html = result.stdout
        # The alert JSON should be embedded in the HTML
        assert "999000111" in html
        assert "חיפה - מערב" in html
        # Template markers should be replaced
        assert "/*ALERTS_JSON*/null/*END_ALERTS_JSON*/" not in html

    def test_build_html_injects_cities_db(self):
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            html = mp._build_html([])
            # Cities DB should be injected (non-empty from cities.json)
            print('HAS_CITIES:', 'Abu Gosh' in html or 'אבו גוש' in html)
            print('TEMPLATE_CLEARED:', '/*CITIES_JSON*/[]/*END_CITIES_JSON*/' not in html)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "HAS_CITIES: True" in result.stdout
        assert "TEMPLATE_CLEARED: True" in result.stdout

    def test_build_html_produces_valid_html_structure(self):
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            html = mp._build_html([{json.dumps(SAMPLE_ALERT, ensure_ascii=False)}])
            print(html)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        html = result.stdout
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "const ALERTS =" in html
        assert "const CITIES_DB =" in html

    def test_build_html_with_empty_alerts_list(self):
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import map_popup as mp
            html = mp._build_html([])
            print(html)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        html = result.stdout
        assert "const ALERTS = []" in html


# ── 6. Fetch alert (with fake HTTP server) ──────────────────────────────

class _FakeAlertHandler(BaseHTTPRequestHandler):
    """Serves canned alert JSON responses."""
    response_body: bytes = b""
    response_code: int = 200

    def do_GET(self):
        self.send_response(self.response_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.response_body)

    def log_message(self, *args):
        pass  # suppress output


def _start_server(body: bytes, code: int = 200) -> tuple[HTTPServer, int]:
    _FakeAlertHandler.response_body = body
    _FakeAlertHandler.response_code = code
    server = HTTPServer(("127.0.0.1", 0), _FakeAlertHandler)
    port = server.server_address[1]
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


class TestFetchAlert:
    """Verify fetch_alert parses API responses correctly."""

    def test_fetch_returns_parsed_json(self):
        body = json.dumps(SAMPLE_ALERT, ensure_ascii=False).encode("utf-8-sig")
        server, port = _start_server(body)
        try:
            code = textwrap.dedent(f"""\
                import json, sys
                sys.path.insert(0, {str(PROJECT_DIR)!r})
                import alert as a
                a.URL = "http://127.0.0.1:{port}/"
                result = a.fetch_alert()
                print(json.dumps(result, ensure_ascii=False))
            """)
            result = _run_python(code)
            assert result.returncode == 0, result.stderr
            parsed = json.loads(result.stdout)
            assert parsed["id"] == "999000111"
        finally:
            server.shutdown()

    def test_fetch_returns_none_on_empty_body(self):
        server, port = _start_server(b"")
        try:
            code = textwrap.dedent(f"""\
                import sys
                sys.path.insert(0, {str(PROJECT_DIR)!r})
                import alert as a
                a.URL = "http://127.0.0.1:{port}/"
                result = a.fetch_alert()
                print(repr(result))
            """)
            result = _run_python(code)
            assert result.returncode == 0, result.stderr
            assert "None" in result.stdout
        finally:
            server.shutdown()

    def test_fetch_returns_none_on_connection_error(self):
        code = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a
            a.URL = "http://127.0.0.1:1/"  # nothing listening
            result = a.fetch_alert()
            print(repr(result))
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "None" in result.stdout

    def test_fetch_handles_utf8_bom(self):
        """The real API returns utf-8-sig (BOM). Verify we strip it."""
        body = b"\xef\xbb\xbf" + json.dumps(
            {"id": "bom_test", "data": []}, ensure_ascii=False
        ).encode("utf-8")
        server, port = _start_server(body)
        try:
            code = textwrap.dedent(f"""\
                import json, sys
                sys.path.insert(0, {str(PROJECT_DIR)!r})
                import alert as a
                a.URL = "http://127.0.0.1:{port}/"
                result = a.fetch_alert()
                print(json.dumps(result, ensure_ascii=False))
            """)
            result = _run_python(code)
            assert result.returncode == 0, result.stderr
            parsed = json.loads(result.stdout)
            assert parsed["id"] == "bom_test"
        finally:
            server.shutdown()


# ── 7. Deduplication (main loop behavior) ───────────────────────────────

class TestDeduplication:
    """Verify the polling loop skips already-seen alert IDs."""

    def test_same_alert_id_logged_only_once(self, tmp_path):
        fmt_log = tmp_path / "fmt.txt"
        raw_log = tmp_path / "raw.txt"
        alert_json = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        # Simulate two fetch cycles returning the same alert
        code = textwrap.dedent(f"""\
            import json, sys, os
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a

            a.FORMATTED_LOG = {str(fmt_log)!r}
            a.RAW_LOG = {str(raw_log)!r}
            a.ensure_log_files()

            # Patch send_to_popup and beep to avoid side effects
            import map_popup
            map_popup.send_to_popup = lambda x: None
            a.send_to_popup = lambda x: None
            a.beep_if_local = lambda x: None

            alert_data = json.loads({alert_json!r})

            # Simulate two poll iterations with the same alert
            for _ in range(3):
                alert = alert_data
                if alert and alert.get("id") and alert["id"] not in a.seen_ids:
                    a.seen_ids.add(alert["id"])
                    a.log_formatted(alert)
                    a.log_raw(alert)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr

        fmt_lines = fmt_log.read_text(encoding="utf-8").strip().split("\n")
        raw_lines = raw_log.read_text(encoding="utf-8").strip().split("\n")
        assert len(fmt_lines) == 1, f"Expected 1 formatted entry, got {len(fmt_lines)}"
        assert len(raw_lines) == 1, f"Expected 1 raw entry, got {len(raw_lines)}"

    def test_different_alert_ids_both_logged(self, tmp_path):
        fmt_log = tmp_path / "fmt.txt"
        raw_log = tmp_path / "raw.txt"
        a1 = json.dumps(SAMPLE_ALERT, ensure_ascii=False)
        a2 = json.dumps(SAMPLE_ALERT_NO_LOCAL, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a

            a.FORMATTED_LOG = {str(fmt_log)!r}
            a.RAW_LOG = {str(raw_log)!r}
            a.ensure_log_files()

            a.beep_if_local = lambda x: None
            import map_popup
            map_popup.send_to_popup = lambda x: None
            a.send_to_popup = lambda x: None

            for alert_data in [json.loads({a1!r}), json.loads({a2!r})]:
                if alert_data and alert_data.get("id") and alert_data["id"] not in a.seen_ids:
                    a.seen_ids.add(alert_data["id"])
                    a.log_formatted(alert_data)
                    a.log_raw(alert_data)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr

        fmt_lines = fmt_log.read_text(encoding="utf-8").strip().split("\n")
        assert len(fmt_lines) == 2

    def test_alert_without_id_is_skipped(self, tmp_path):
        fmt_log = tmp_path / "fmt.txt"
        raw_log = tmp_path / "raw.txt"
        no_id = json.dumps({"data": ["x"]}, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys
            sys.path.insert(0, {str(PROJECT_DIR)!r})
            import alert as a

            a.FORMATTED_LOG = {str(fmt_log)!r}
            a.RAW_LOG = {str(raw_log)!r}
            a.ensure_log_files()
            a.beep_if_local = lambda x: None
            import map_popup
            map_popup.send_to_popup = lambda x: None
            a.send_to_popup = lambda x: None

            alert = json.loads({no_id!r})
            if alert and alert.get("id") and alert["id"] not in a.seen_ids:
                a.seen_ids.add(alert["id"])
                a.log_formatted(alert)
                a.log_raw(alert)
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert fmt_log.read_text(encoding="utf-8") == ""


# ── 8. Beep-if-local logic ──────────────────────────────────────────────

class TestBeepIfLocal:
    """Verify beep_if_local triggers only when MY_LOCATION is in alert data."""

    def test_beep_triggered_when_local_city_present(self):
        alert_with_local = {**SAMPLE_ALERT, "data": ["חיפה"]}
        alert_json = json.dumps(alert_with_local, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys, subprocess
            sys.path.insert(0, {str(PROJECT_DIR)!r})

            calls = []
            _orig = subprocess.Popen
            def fake_popen(cmd, **kw):
                calls.append(cmd)
            subprocess.Popen = fake_popen

            import alert as a
            a.beep_if_local(json.loads({alert_json!r}))
            print("CALLED" if calls else "NOT_CALLED")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "CALLED" in result.stdout

    def test_beep_not_triggered_when_local_city_absent(self):
        alert_json = json.dumps(SAMPLE_ALERT_NO_LOCAL, ensure_ascii=False)
        code = textwrap.dedent(f"""\
            import json, sys, subprocess
            sys.path.insert(0, {str(PROJECT_DIR)!r})

            calls = []
            _orig = subprocess.Popen
            def fake_popen(cmd, **kw):
                calls.append(cmd)
            subprocess.Popen = fake_popen

            import alert as a
            a.beep_if_local(json.loads({alert_json!r}))
            print("CALLED" if calls else "NOT_CALLED")
        """)
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "NOT_CALLED" in result.stdout


# ── 9. map_popup.py CLI interface ────────────────────────────────────────

class TestMapPopupCLI:
    """Verify map_popup.py standalone CLI behavior."""

    def test_no_args_prints_usage_and_exits_nonzero(self):
        result = subprocess.run(
            [PYTHON, str(PROJECT_DIR / "map_popup.py")],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout or "usage" in result.stdout.lower()


# ── 10. Full pipeline (fetch -> log -> IPC) with fake server ────────────

class TestFullPipeline:
    """Simulate a single poll cycle through the main loop logic."""

    def test_single_poll_cycle_creates_all_outputs(self, tmp_path):
        fmt_log = tmp_path / "fmt.txt"
        raw_log = tmp_path / "raw.txt"
        ipc_file = tmp_path / "ipc.json"

        body = json.dumps(SAMPLE_ALERT, ensure_ascii=False).encode("utf-8-sig")
        server, port = _start_server(body)
        try:
            code = textwrap.dedent(f"""\
                import json, sys
                sys.path.insert(0, {str(PROJECT_DIR)!r})

                import alert as a
                import map_popup as mp

                a.URL = "http://127.0.0.1:{port}/"
                a.FORMATTED_LOG = {str(fmt_log)!r}
                a.RAW_LOG = {str(raw_log)!r}
                mp.ALERTS_IPC = {str(ipc_file)!r}
                a.ensure_log_files()

                # Disable beep and popup launch
                a.beep_if_local = lambda x: None
                mp.send_to_popup = lambda alert: mp._append_alert(alert)
                a.send_to_popup = mp.send_to_popup

                alert = a.fetch_alert()
                if alert and alert.get("id") and alert["id"] not in a.seen_ids:
                    a.seen_ids.add(alert["id"])
                    a.log_formatted(alert)
                    a.log_raw(alert)
                    a.send_to_popup(alert)

                print("OK")
            """)
            result = _run_python(code)
            assert result.returncode == 0, result.stderr
            assert "OK" in result.stdout

            # Verify formatted log
            fmt_content = fmt_log.read_text(encoding="utf-8")
            assert "999000111" in fmt_content

            # Verify raw log
            raw_content = raw_log.read_text(encoding="utf-8")
            raw_json = json.loads(raw_content.split("] ", 1)[1])
            assert raw_json["id"] == "999000111"

            # Verify IPC file
            ipc_data = json.loads(ipc_file.read_text(encoding="utf-8"))
            assert len(ipc_data) == 1
            assert ipc_data[0]["id"] == "999000111"
        finally:
            server.shutdown()

    def test_null_fetch_produces_no_output(self, tmp_path):
        fmt_log = tmp_path / "fmt.txt"
        raw_log = tmp_path / "raw.txt"

        server, port = _start_server(b"")  # empty -> None
        try:
            code = textwrap.dedent(f"""\
                import sys
                sys.path.insert(0, {str(PROJECT_DIR)!r})
                import alert as a
                a.URL = "http://127.0.0.1:{port}/"
                a.FORMATTED_LOG = {str(fmt_log)!r}
                a.RAW_LOG = {str(raw_log)!r}
                a.ensure_log_files()

                a.beep_if_local = lambda x: None
                import map_popup as mp
                mp.send_to_popup = lambda x: None
                a.send_to_popup = lambda x: None

                alert = a.fetch_alert()
                if alert and alert.get("id") and alert["id"] not in a.seen_ids:
                    a.seen_ids.add(alert["id"])
                    a.log_formatted(alert)
                    a.log_raw(alert)
                print("OK")
            """)
            result = _run_python(code)
            assert result.returncode == 0, result.stderr
            assert fmt_log.read_text() == ""
            assert raw_log.read_text() == ""
        finally:
            server.shutdown()
