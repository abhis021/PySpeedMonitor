#!/usr/bin/env python3
"""
Client-side Internet speed monitor.

The browser runs LibreSpeed-style tests against this Flask server, then posts
each result back to Flask so the dashboard can log a rolling history over time.
That means results reflect the client's connection to this deployed app, similar
to how Fast.com measures from the viewer's location.
"""

import os
import threading
from collections import defaultdict, deque

from flask import Flask, jsonify, render_template, request

# ----------------------------------------------------------------------
# Configuration - can be overridden with environment variables
# ----------------------------------------------------------------------
TEST_INTERVAL = int(os.getenv("TEST_INTERVAL", os.getenv("UPDATE_INTERVAL", "60")))
HISTORY_LENGTH = int(os.getenv("HISTORY_LENGTH", "60"))

# Thresholds in Mbps/ms.
EXCELLENT_DOWNLOAD = float(os.getenv("EXCELLENT_DOWNLOAD", "100.0"))
EXCELLENT_UPLOAD = float(os.getenv("EXCELLENT_UPLOAD", "20.0"))
EXCELLENT_LATENCY = float(os.getenv("EXCELLENT_LATENCY", "30.0"))

STABLE_DOWNLOAD = float(os.getenv("STABLE_DOWNLOAD", "25.0"))
STABLE_UPLOAD = float(os.getenv("STABLE_UPLOAD", "5.0"))
STABLE_LATENCY = float(os.getenv("STABLE_LATENCY", "100.0"))

MAX_GARBAGE_BYTES = int(os.getenv("MAX_GARBAGE_BYTES", "25000000"))
_GARBAGE_CHUNK = b"0" * 1024 * 1024

# ----------------------------------------------------------------------
# Flask app
# ----------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

_state_lock = threading.Lock()
_client_state = defaultdict(
    lambda: {
        "latest": {
            "download": 0.0,
            "upload": 0.0,
            "ping": 0.0,
            "timestamp": "--:--:--",
        },
        "history": {
            "download": deque(maxlen=HISTORY_LENGTH),
            "upload": deque(maxlen=HISTORY_LENGTH),
            "ping": deque(maxlen=HISTORY_LENGTH),
            "time": deque(maxlen=HISTORY_LENGTH),
        },
    }
)


def _get_status(download, upload, ping):
    """Return (status_string, css_class) as excellent, stable, or poor."""
    if (
        download >= EXCELLENT_DOWNLOAD
        and upload >= EXCELLENT_UPLOAD
        and ping <= EXCELLENT_LATENCY
    ):
        return "excellent", "excellent"
    if (
        download >= STABLE_DOWNLOAD
        and upload >= STABLE_UPLOAD
        and ping <= STABLE_LATENCY
    ):
        return "stable", "stable"
    return "poor", "poor"


def _history_payload(client_id):
    state = _client_state[client_id]
    latest = state["latest"]
    history = state["history"]
    status_str, css_class = _get_status(
        latest["download"], latest["upload"], latest["ping"]
    )
    return {
        "download": latest["download"],
        "upload": latest["upload"],
        "ping": latest["ping"],
        "timestamp": latest["timestamp"],
        "status": status_str,
        "body_class": css_class,
        "history": {
            "time": list(history["time"]),
            "download": list(history["download"]),
            "upload": list(history["upload"]),
            "ping": list(history["ping"]),
        },
    }


@app.route("/")
def index():
    """Serve the dashboard."""
    return render_template(
        "index.html",
        history_length=HISTORY_LENGTH,
        test_interval=TEST_INTERVAL,
    )


@app.route("/api/status")
def api_status():
    """Return the rolling history for this browser/client id."""
    client_id = request.args.get("client_id", "default")
    with _state_lock:
        return jsonify(_history_payload(client_id))


@app.route("/api/result", methods=["POST"])
def api_result():
    """Accept one browser-measured speed test result and add it to history."""
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id", "default")
    download = round(float(data.get("download", 0.0)), 2)
    upload = round(float(data.get("upload", 0.0)), 2)
    ping = round(float(data.get("ping", 0.0)), 1)
    timestamp = str(data.get("timestamp") or "--:--:--")[:64]

    with _state_lock:
        state = _client_state[client_id]
        state["latest"] = {
            "download": download,
            "upload": upload,
            "ping": ping,
            "timestamp": timestamp,
        }
        state["history"]["download"].append(download)
        state["history"]["upload"].append(upload)
        state["history"]["ping"].append(ping)
        state["history"]["time"].append(timestamp)
        return jsonify(_history_payload(client_id))


@app.route("/backend/empty", methods=["GET", "POST"])
def backend_empty():
    """Small no-op endpoint used for ping and upload tests."""
    if request.method == "POST":
        request.get_data(cache=False)
    response = app.response_class("", mimetype="text/plain")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/backend/garbage")
def backend_garbage():
    """Return a cache-busted byte stream used by browser download tests."""
    try:
        requested_size = int(request.args.get("size", "10000000"))
    except ValueError:
        requested_size = 10_000_000
    size = max(0, min(requested_size, MAX_GARBAGE_BYTES))

    def generate():
        remaining = size
        while remaining > 0:
            chunk_size = min(len(_GARBAGE_CHUNK), remaining)
            remaining -= chunk_size
            yield _GARBAGE_CHUNK[:chunk_size]

    response = app.response_class(generate(), mimetype="application/octet-stream")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Length"] = str(size)
    return response


@app.route("/backend/get-ip")
def backend_get_ip():
    """Return the best-effort client address."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr
    return jsonify({"ip": ip})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
