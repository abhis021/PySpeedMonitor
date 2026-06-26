#!/usr/bin/env python3
"""
Realtime Internet Speed Monitor
--------------------------------
Flask + SocketIO web app that measures download/upload speed and latency,
stores a rolling history, and pushes updates to a browser dashboard.
The whole UI changes colour according to the current network quality:
    Green = Excellent
    Blue  = Stable
    Red   = Slow/Bad
"""

import threading
import time
from collections import deque
from datetime import datetime

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

import speedtest  # from speedtest-cli

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
UPDATE_INTERVAL = 5          # seconds between speedtests
HISTORY_LENGTH = 60          # how many points to keep (5 s * 60 = 5 min)
# Thresholds (feel free to tweak)
EXCELLENT_DOWNLOAD = 10.0    # MB/s
EXCELLENT_UPLOAD   = 10.0    # MB/s
EXCELLENT_LATENCY  = 30.0    # ms

STABLE_DOWNLOAD = 2.0        # MB/s
STABLE_UPLOAD   = 1.0        # MB/s
STABLE_LATENCY  = 100.0      # ms

# ----------------------------------------------------------------------
# Flask / SocketIO setup
# ----------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "replace‑with‑a‑random‑secret"
socketio = SocketIO(app, async_mode="eventlet")  # eventlet gives good performance

# ----------------------------------------------------------------------
# Shared state (thread‑safe because only the background thread writes,
# and SocketIO reads only via the main thread)
# ----------------------------------------------------------------------
latest = {
    "download": 0.0,   # MB/s
    "upload":   0.0,   # MB/s
    "ping":     0.0,   # ms
    "timestamp": None,
}
# Rolling buffers for the chart
history_download = deque(maxlen=HISTORY_LENGTH)
history_upload   = deque(maxlen=HISTORY_LENGTH)
history_ping     = deque(maxlen=HISTORY_LENGTH)
history_time     = deque(maxlen=HISTORY_LENGTH)  # strings for X‑axis

# ----------------------------------------------------------------------
# Helper: colour / status determination
# ----------------------------------------------------------------------
def get_status(download, upload, ping):
    """
    Returns a tuple (status_string, css_class) where:
        status_string ∈ {"excellent","stable","poor"}
        css_class     ∈ {"excellent","stable","poor"} (used for <body> class)
    """
    if (download >= EXCELLENT_DOWNLOAD and
        upload   >= EXCELLENT_UPLOAD   and
        ping     <= EXCELLENT_LATENCY):
        return "excellent", "excellent"
    if (download >= STABLE_DOWNLOAD and
        upload   >= STABLE_UPLOAD   and
        ping     <= STABLE_LATENCY):
        return "stable", "stable"
    return "poor", "poor"

# ----------------------------------------------------------------------
# Background worker that runs speedtest every UPDATE_INTERVAL seconds
# ----------------------------------------------------------------------
def speedtest_worker():
    while True:
        try:
            s = speedtest.Speedtest()
            s.get_best_server()   # find low‑latency server
            download_bps = s.download()   # bits per second
            upload_bps   = s.upload()
            ping_ms      = s.results.ping

            # Convert to MB/s (1 byte = 8 bits)
            download_mbps = download_bps / 1_000_000 / 8
            upload_mbps   = upload_bps   / 1_000_000 / 8

            timestamp = datetime.now().strftime("%H:%M:%S")

            # Update shared state
            latest["download"] = round(download_mbps, 2)
            latest["upload"]   = round(upload_mbps,   2)
            latest["ping"]     = round(ping_ms,      1)
            latest["timestamp"]= timestamp

            # Push to rolling buffers (used by the chart)
            history_download.append(latest["download"])
            history_upload.append(latest["upload"])
            history_ping.append(latest["ping"])
            history_time.append(timestamp)

            # Determine status and broadcast to all connected clients
            status_str, css_class = get_status(latest["download"],
                                               latest["upload"],
                                               latest["ping"])
            socketio.emit("update",
                          {"download": latest["download"],
                           "upload":   latest["upload"],
                           "ping":     latest["ping"],
                           "timestamp": timestamp,
                           "status":   status_str,
                           "body_class": css_class})
        except Exception as e:
            # In case of failure we still emit something so the UI doesn't freeze
            print(f"[speedtest] Error: {e}")
            socketio.emit("update", {"error": str(e)})

        time.sleep(UPDATE_INTERVAL)

# ----------------------------------------------------------------------
# Flask routes
# ----------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")

# ----------------------------------------------------------------------
# SocketIO event handlers (optional, we could rely solely on server‑emit)
# ----------------------------------------------------------------------
@socketio.on("connect")
def handle_connect():
    """When a client connects, send the current state immediately."""
    emit("initial_state",
         {"download": latest["download"],
          "upload":   latest["upload"],
          "ping":     latest["ping"],
          "timestamp": latest["timestamp"],
          "status":   get_status(latest["download"], latest["upload"], latest["ping"])[0],
          "body_class": get_status(latest["download"], latest["upload"], latest["ping"])[1]})

# ----------------------------------------------------------------------
# Application entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Start the background measurement thread
    worker = threading.Thread(target=speedtest_worker, daemon=True)
    worker.start()
    # Run the Flask‑SocketIO server
    # Use host='0.0.0.0' to make it reachable from other devices on your LAN
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
