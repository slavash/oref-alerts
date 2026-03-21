#!/bin/bash
# oref-ctl.sh — start / stop / status for the OREF alert monitor (macOS Launch Agent)
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.local.oref-alert"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="$DIR/.venv/bin/python3"
LOG="$DIR/oref-ctl.log"

_install_plist() {
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$DIR/alert.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DIR</string>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OREF_MY_LOCATION</key>
        <string>${OREF_MY_LOCATION:-חיפה}</string>
    </dict>
</dict>
</plist>
EOF
}

start() {
    if launchctl list "$LABEL" &>/dev/null; then
        echo "Already running."
        return
    fi
    _install_plist
    launchctl load "$PLIST"
    echo "Started. Log: $LOG"
}

stop() {
    if ! launchctl list "$LABEL" &>/dev/null; then
        echo "Not running."
        return
    fi
    launchctl unload "$PLIST"
    rm -f "$PLIST"
    echo "Stopped."
}

status() {
    if launchctl list "$LABEL" &>/dev/null; then
        local pid
        pid=$(launchctl list "$LABEL" | awk -F= '/PID/{gsub(/[^0-9]/,"",$2); print $2}')
        if [ -n "$pid" ]; then
            echo "Running (PID: $pid)"
        else
            echo "Loaded but not running (may be restarting)."
        fi
    else
        echo "Not running."
    fi
}

log() {
    tail -f "$LOG"
}

case "${1:-}" in
    start)  start  ;;
    stop)   stop   ;;
    restart) stop; start ;;
    status) status ;;
    log)    log    ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|log}"
        exit 1
        ;;
esac
