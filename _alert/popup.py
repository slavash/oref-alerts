"""macOS WebKit popup window for displaying alert locations on a map."""
from __future__ import annotations

import os
import signal

from _alert.cities import load_cities
from _alert.config import Config
from _alert.html_builder import build_html
from _alert.ipc import read_alerts
from _alert.lock import hold_lock


def run_popup(config: Config) -> None:  # pylint: disable=too-many-locals,too-many-statements
    """Launch a floating WebKit popup showing alert locations on a Leaflet map."""
    import AppKit  # pylint: disable=import-outside-toplevel,import-error
    import WebKit  # pylint: disable=import-outside-toplevel,import-error
    from Foundation import NSObject, NSURL, NSTimer  # pylint: disable=import-outside-toplevel,import-error

    with hold_lock(config.popup_lock_path) as _lock_fd:
        alerts = read_alerts(config.alerts_ipc_path)
        cities_db = load_cities(config.cities_json_path)
        seen_count = len(alerts)
        html = build_html(alerts, cities_db, config.map_template_path)

        class AppDelegate(NSObject):  # pylint: disable=too-few-public-methods
            """Minimal NSApp delegate."""

            def applicationDidFinishLaunching_(self, _note):  # pylint: disable=invalid-name
                """Called when the application finishes launching."""

        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        screen = AppKit.NSScreen.mainScreen().frame()
        w, h = 520, 420
        x = screen.size.width - w - 20
        y = 20

        style = (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskResizable
        )
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (w, h)),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setTitle_(alerts[0].get("title", "Alert") if alerts else "Alert")
        window.setLevel_(AppKit.NSFloatingWindowLevel)
        window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        webview = WebKit.WKWebView.alloc().initWithFrame_(((0, 0), (w, h)))
        webview.loadHTMLString_baseURL_(html, NSURL.URLWithString_("about:blank"))
        window.setContentView_(webview)

        delegate = AppDelegate.alloc().init()
        app.setDelegate_(delegate)
        window.orderFrontRegardless()

        close_timer_holder = [None]
        ipc_path = config.alerts_ipc_path
        lock_path = config.popup_lock_path
        auto_close = config.auto_close_seconds

        def _cleanup():
            for path in (ipc_path, lock_path):
                try:
                    os.remove(path)
                except OSError:
                    pass

        def schedule_close():
            if close_timer_holder[0] is not None:
                close_timer_holder[0].invalidate()

            def do_close(_timer):
                _cleanup()
                window.close()
                app.stop_(None)

            close_timer_holder[0] = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                float(auto_close), False, do_close
            )

        schedule_close()

        def poll_alerts(_timer):
            nonlocal seen_count, alerts
            current = read_alerts(ipc_path)
            if len(current) > seen_count:
                alerts = current
                seen_count = len(current)
                new_html = build_html(alerts, cities_db, config.map_template_path)
                webview.loadHTMLString_baseURL_(
                    new_html, NSURL.URLWithString_("about:blank")
                )
                schedule_close()

        NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1.0, True, poll_alerts)

        def handle_term(*_):
            _cleanup()
            app.stop_(None)

        signal.signal(signal.SIGTERM, handle_term)
        app.run()
