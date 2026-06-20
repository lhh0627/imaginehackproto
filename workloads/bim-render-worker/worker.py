from __future__ import annotations

import json
import math
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("PORT", "80"))
RENDER_INTENSITY = float(os.getenv("RENDER_INTENSITY", "0.82"))
CARBON_KG_PER_KWH = float(os.getenv("CARBON_KG_PER_KWH", "0.42"))
COST_USD_PER_KWH = float(os.getenv("COST_USD_PER_KWH", "0.10"))

state = {
    "active": False,
    "jobs_completed": 0,
    "last_job_seconds": 0.0,
    "started_at": time.time(),
}
state_lock = threading.Lock()


def _render_loop() -> None:
    while True:
        started = time.perf_counter()
        with state_lock:
            state["active"] = True

        # Short CPU bursts simulate a BIM render job without overloading a laptop.
        target_seconds = 0.16 + (RENDER_INTENSITY * 0.22)
        value = 0.0
        while time.perf_counter() - started < target_seconds:
            for item in range(1, 900):
                value += math.sqrt(item) * math.sin(item)

        elapsed = time.perf_counter() - started
        with state_lock:
            state["active"] = False
            state["jobs_completed"] += 1
            state["last_job_seconds"] = round(elapsed, 3)

        time.sleep(max(0.45, 1.4 - RENDER_INTENSITY))


def _metrics() -> dict[str, float | int | bool | str]:
    with state_lock:
        jobs_completed = int(state["jobs_completed"])
        active = bool(state["active"])
        last_job_seconds = float(state["last_job_seconds"])
        uptime_seconds = round(time.time() - float(state["started_at"]))

    cpu_pct = round(24 + (RENDER_INTENSITY * 68) + (6 if active else 0), 1)
    memory_mb = round(768 + (RENDER_INTENSITY * 1280), 1)
    energy_kwh_hour = round(1.4 + (RENDER_INTENSITY * 10.2) + (0.5 if active else 0), 2)
    carbon_kg_hour = round(energy_kwh_hour * CARBON_KG_PER_KWH, 2)
    monthly_cost_usd = round(energy_kwh_hour * 24 * 30 * COST_USD_PER_KWH, 2)

    return {
        "telemetry_source": "live-bim-render-worker",
        "workload_active": active,
        "active_render_jobs": 1 if active else 0,
        "jobs_completed": jobs_completed,
        "last_job_seconds": last_job_seconds,
        "uptime_seconds": uptime_seconds,
        "cpu_pct": cpu_pct,
        "memory_mb": memory_mb,
        "energy_kwh_hour": energy_kwh_hour,
        "carbon_kg_hour": carbon_kg_hour,
        "monthly_cost_usd": monthly_cost_usd,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self) -> None:
        metrics = _metrics()
        body = f"""<!doctype html>
<html lang="en">
  <head><title>BIM-Render-04</title></head>
  <body style="font-family: system-ui; max-width: 760px; margin: 48px auto;">
    <h1>BIM-Render-04</h1>
    <p>Legacy BIM render worker is currently simulating render jobs.</p>
    <ul>
      <li>Jobs completed: {metrics["jobs_completed"]}</li>
      <li>Active render jobs: {metrics["active_render_jobs"]}</li>
      <li>Estimated energy: {metrics["energy_kwh_hour"]} kWh/hour</li>
      <li>Estimated carbon: {metrics["carbon_kg_hour"]} kg CO2e/hour</li>
    </ul>
    <p><a href="/metrics">View live metrics JSON</a></p>
  </body>
</html>""".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/metrics":
            self._send_json(_metrics())
            return
        if self.path == "/health":
            self._send_json({"ok": True})
            return
        self._send_html()

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    threading.Thread(target=_render_loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
