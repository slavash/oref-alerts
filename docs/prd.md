# OREF Alert Tool -- Product Requirements Document

## Problem Statement

During rocket and missile attacks in Israel, the Home Front Command (OREF) publishes real-time alerts via a public API. Existing consumer apps (e.g. the official OREF app, Red Alert) are mobile-only and provide no desktop experience for people working at a computer. There is no lightweight, always-on desktop tool that shows alert locations on a map and notifies users when their specific area is affected.

## Goal

Build a personal macOS desktop tool that:

1. Continuously monitors the OREF alert API.
2. Displays every new alert on an interactive map in a floating popup window.
3. Plays an audible notification when the user's configured location is affected.
4. Logs all alerts for later review.

## Target User

A single developer running the tool locally on macOS. No multi-user, server, or mobile requirements.

## Functional Requirements

### FR-1: Real-time Alert Polling
- Poll the OREF alert API at a configurable interval (default: 2 seconds).
- Handle UTF-8 BOM-encoded responses from the API.
- Gracefully handle network errors and empty responses without crashing.

### FR-2: Alert Deduplication
- Track seen alert IDs in memory.
- Only process each unique alert once per session.

### FR-3: Raw JSON Logging
- Append every new alert as a timestamped JSON line to a local log file (`alerts_raw.txt`).
- The log serves as both an audit trail and sample data for development.

### FR-4: Local Audio Notification
- When a new alert's affected areas include the user's configured location, play an audible beep via macOS `osascript`.
- The beep is location-specific; the map popup shows all alerts regardless of location.

### FR-5: Map Popup
- Display alert locations on an interactive Leaflet map inside a floating macOS WebKit window.
- Plot red markers for each affected city using a local cities database (`cities.json`).
- The popup auto-closes after 60 seconds of inactivity (no new alerts).
- Only one popup process runs at a time, enforced by a lock file.

### FR-6: Inter-Process Communication
- The poller and popup run as separate processes.
- A shared JSON file (`/tmp/oref_alerts.json`) acts as the IPC channel: the poller appends alerts, the popup reads them.
- A lock file (`/tmp/oref_popup.lock`) prevents duplicate popup processes.

### FR-7: Alert History Page
- A standalone HTML page (`history.html`) for browsing past alerts.
- Interactive map view with alert markers.
- Filterable by alert category and date.
- Paginated alert list.

## Non-Functional Requirements

### NFR-1: Configuration
- All settings (API URL, poll interval, location, file paths) configurable via environment variables.
- Sensible defaults that work out of the box.

### NFR-2: Reliability
- The tool should run unattended for hours/days without memory leaks or crashes.
- Corrupt or missing IPC/log files should be handled gracefully.

### NFR-3: Minimal Dependencies
- macOS-native UI via pyobjc (no Electron or browser dependency).
- Leaflet.js for map rendering (loaded from CDN in the HTML template).
- No database; plain files for all persistence.

### NFR-4: Testability
- Core logic should be importable and testable in-process.
- E2e tests validate the full pipeline via module imports.

## Out of Scope

- Mobile or cross-platform support.
- Multi-user or server deployment.
- Push notifications (APNs, FCM).
- Historical alert persistence across sessions (in-memory dedup resets on restart).
- Alert severity classification or escalation logic.
- Integration with external notification services (Slack, Telegram, etc.).

## Success Criteria

- The tool runs continuously on macOS and displays a map popup within seconds of a new OREF alert.
- Audible beep fires reliably for the user's configured location.
- All alerts are logged to `alerts_raw.txt` without data loss.
- The alert history page renders correctly from the logged data.
