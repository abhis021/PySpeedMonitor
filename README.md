# PySpeedMonitor

PySpeedMonitor is a lightweight Flask-based internet speed monitoring dashboard.
The app runs browser-side LibreSpeed-style tests and sends results to the Flask backend, which stores a rolling history for each client session.

## What it does

- Serves a dashboard UI from `templates/index.html`.
- Measures latency, download, and upload speeds entirely from the browser.
- Uploads client-side test results to `/api/result`.
- Exposes `/api/status` to return the latest measurement and a history of results.
- Uses `/backend/empty` for ping/upload tests and `/backend/garbage` for download throughput testing.
- Computes client status as `excellent`, `stable`, or `poor` based on configurable thresholds.
- Persists per-client rolling history using in-memory state keyed by a browser-generated `client_id`.

## Files in this repository

- `app.py` - Flask application and backend API logic.
- `requirements.txt` - Python dependencies.
- `render.yaml` - Render.com service definition for deployment.
- `templates/index.html` - Client dashboard UI and browser-side speed test implementation.

## Key endpoints

- `/` - Dashboard page.
- `/api/status` - Returns the current client history and latest measurement.
- `/api/result` - Accepts POSTed speed test results from the browser.
- `/backend/empty` - No-op endpoint used for ping and upload testing.
- `/backend/garbage` - Returns a sized byte stream for download testing.
- `/backend/get-ip` - Returns a best-effort client IP address.

## Configuration

Environment variables supported by `app.py`:

- `TEST_INTERVAL` / `UPDATE_INTERVAL` - Browser polling interval in seconds (default: `60`).
- `HISTORY_LENGTH` - Maximum number of history points stored per client (default: `60`).
- `EXCELLENT_DOWNLOAD` - Download threshold in Mbps for "excellent" status (default: `100.0`).
- `EXCELLENT_UPLOAD` - Upload threshold in Mbps for "excellent" status (default: `20.0`).
- `EXCELLENT_LATENCY` - Ping threshold in ms for "excellent" status (default: `30.0`).
- `STABLE_DOWNLOAD` - Download threshold in Mbps for "stable" status (default: `25.0`).
- `STABLE_UPLOAD` - Upload threshold in Mbps for "stable" status (default: `5.0`).
- `STABLE_LATENCY` - Ping threshold in ms for "stable" status (default: `100.0`).
- `MAX_GARBAGE_BYTES` - Maximum bytes returnable by `/backend/garbage` (default: `25000000`).
- `FLASK_SECRET_KEY` - Flask secret key (default: `dev-secret-change-me`).
- `PORT` - Server port when running directly (default: `5000`).

## Dependencies

The app uses:

- `Flask==2.3.3`
- `gunicorn==22.0.0`

Install dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Running locally

1. Create a virtual environment and activate it.
2. Install dependencies.
3. Start the app:

```bash
python app.py
```

4. Open `http://127.0.0.1:5000` in your browser.

## Client-side behavior

- The browser generates or reuses a `client_id` stored in `localStorage`.
- It measures:
  - Ping via repeated requests to `/backend/empty`.
  - Download speed by fetching `/backend/garbage` chunks.
  - Upload speed by POSTing payloads to `/backend/empty`.
- Results are posted back to `/api/result` and rendered in the dashboard.
- Chart.js is used for the time-series chart of download, upload, and latency values.

## Notes

- The backend stores all history in memory, so data is lost on restart.
- This project is intended as a simple proof-of-concept speed monitor and dashboard.
