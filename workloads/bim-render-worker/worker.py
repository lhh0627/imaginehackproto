from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("PORT", "80"))
RENDER_INTENSITY = float(os.getenv("RENDER_INTENSITY", "0.82"))
CARBON_KG_PER_KWH = float(os.getenv("CARBON_KG_PER_KWH", "0.42"))
COST_USD_PER_KWH = float(os.getenv("COST_USD_PER_KWH", "0.10"))

RENDER_JOBS = [
    {
        "job_id": "render-hilti-tower-l23",
        "job_name": "Hilti Tower L23 coordination render",
        "model": "Hilti_Tower_Renovation.ifc",
        "frames_total": 96,
        "model_elements_total": 18420,
        "triangles_total": 4250000,
    },
    {
        "job_id": "render-jobsite-mep-clash",
        "job_name": "MEP clash review walkthrough",
        "model": "Jobsite_MEP_Clash_Model.ifc",
        "frames_total": 64,
        "model_elements_total": 12750,
        "triangles_total": 3180000,
    },
    {
        "job_id": "render-safety-logistics",
        "job_name": "Safety logistics 4D sequence",
        "model": "Site_Logistics_4D.ifc",
        "frames_total": 72,
        "model_elements_total": 15110,
        "triangles_total": 3660000,
    },
]

state = {
    "active": False,
    "jobs_completed": 0,
    "last_job_seconds": 0.0,
    "started_at": time.time(),
    "current_job": RENDER_JOBS[0],
    "job_index": 0,
    "frame": 0,
    "model_elements_processed": 0,
    "triangles_processed": 0,
    "render_queue_depth": len(RENDER_JOBS),
    "active_alert": None,
    "alerts_received": 0,
    "alerts_acknowledged": 0,
    "last_alert_acknowledged_at": None,
}
state_lock = threading.Lock()


def _render_loop() -> None:
    while True:
        with state_lock:
            job = RENDER_JOBS[state["job_index"]]
            state["current_job"] = job
            state["active"] = True
            state["render_queue_depth"] = len(RENDER_JOBS) - 1

        for frame in range(1, int(job["frames_total"]) + 1):
            started = time.perf_counter()

            # Short CPU bursts simulate BIM frame rendering without overloading a laptop.
            target_seconds = 0.035 + (RENDER_INTENSITY * 0.035)
            value = 0.0
            while time.perf_counter() - started < target_seconds:
                for item in range(1, 520):
                    value += math.sqrt(item) * math.sin(item)

            progress = frame / int(job["frames_total"])
            with state_lock:
                state["frame"] = frame
                state["model_elements_processed"] = int(job["model_elements_total"] * progress)
                state["triangles_processed"] = int(job["triangles_total"] * progress)
                state["last_job_seconds"] = round(time.perf_counter() - started, 3)

            time.sleep(0.035)

        with state_lock:
            state["active"] = False
            state["jobs_completed"] += 1
            state["frame"] = int(job["frames_total"])
            state["model_elements_processed"] = int(job["model_elements_total"])
            state["triangles_processed"] = int(job["triangles_total"])
            state["job_index"] = (int(state["job_index"]) + 1) % len(RENDER_JOBS)

        time.sleep(max(0.7, 1.6 - RENDER_INTENSITY))


def _metrics() -> dict[str, float | int | bool | str]:
    with state_lock:
        jobs_completed = int(state["jobs_completed"])
        active = bool(state["active"])
        last_job_seconds = float(state["last_job_seconds"])
        uptime_seconds = round(time.time() - float(state["started_at"]))
        job = dict(state["current_job"])
        current_frame = int(state["frame"])
        model_elements_processed = int(state["model_elements_processed"])
        triangles_processed = int(state["triangles_processed"])
        render_queue_depth = int(state["render_queue_depth"])
        active_alert = dict(state["active_alert"]) if state["active_alert"] else None
        alerts_received = int(state["alerts_received"])
        alerts_acknowledged = int(state["alerts_acknowledged"])
        last_alert_acknowledged_at = state["last_alert_acknowledged_at"]

    frame_progress = current_frame / max(1, int(job["frames_total"]))
    geometry_factor = min(1.0, float(job["triangles_total"]) / 5000000)
    activity_factor = 1 if active else 0.42
    cpu_pct = round(18 + (RENDER_INTENSITY * 58 * activity_factor) + (geometry_factor * 18), 1)
    memory_mb = round(640 + (geometry_factor * 1800) + (RENDER_INTENSITY * 420), 1)
    energy_kwh_hour = round(
        1.2 + (RENDER_INTENSITY * 6.4 * activity_factor) + (geometry_factor * 4.1), 2
    )
    carbon_kg_hour = round(energy_kwh_hour * CARBON_KG_PER_KWH, 2)
    monthly_cost_usd = round(energy_kwh_hour * 24 * 30 * COST_USD_PER_KWH, 2)

    return {
        "telemetry_source": "live-bim-render-worker",
        "workload_active": active,
        "active_render_jobs": 1 if active else 0,
        "current_task": job["job_name"],
        "current_job_id": job["job_id"],
        "current_model": job["model"],
        "current_frame": current_frame,
        "frames_total": job["frames_total"],
        "frame_progress_pct": round(frame_progress * 100, 1),
        "model_elements_processed": model_elements_processed,
        "model_elements_total": job["model_elements_total"],
        "triangles_processed": triangles_processed,
        "triangles_total": job["triangles_total"],
        "render_queue_depth": render_queue_depth,
        "active_alert": active_alert,
        "alerts_received": alerts_received,
        "alerts_acknowledged": alerts_acknowledged,
        "last_alert_acknowledged_at": last_alert_acknowledged_at,
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
    <section id="alertBanner" style="display: none; border: 2px solid #dc2626; background: #fef2f2; color: #991b1b; padding: 16px; border-radius: 12px; margin-bottom: 24px;">
      <strong>Cloud Sentinel Alert</strong>
      <p id="alertMessage"></p>
      <small id="alertMeta"></small>
      <form id="ackAlertForm" style="margin-top: 14px;">
        <button type="submit" style="border: 0; border-radius: 8px; background: #991b1b; color: white; cursor: pointer; font-weight: 700; padding: 10px 14px;">
          Yes, acknowledge and close
        </button>
      </form>
    </section>
    <h1>BIM-Render-04</h1>
    <p>Legacy BIM render worker is currently simulating render jobs.</p>
    <ul>
      <li>Current task: {metrics["current_task"]}</li>
      <li>Model: {metrics["current_model"]}</li>
      <li>Frame progress: {metrics["current_frame"]}/{metrics["frames_total"]} ({metrics["frame_progress_pct"]}%)</li>
      <li>Model elements processed: {metrics["model_elements_processed"]}/{metrics["model_elements_total"]}</li>
      <li>Triangles processed: {metrics["triangles_processed"]}/{metrics["triangles_total"]}</li>
      <li>Jobs completed: {metrics["jobs_completed"]}</li>
      <li>Active render jobs: {metrics["active_render_jobs"]}</li>
      <li>Alerts received: {metrics["alerts_received"]}</li>
      <li>Alerts acknowledged: {metrics["alerts_acknowledged"]}</li>
      <li>Estimated energy: {metrics["energy_kwh_hour"]} kWh/hour</li>
      <li>Estimated carbon: {metrics["carbon_kg_hour"]} kg CO2e/hour</li>
    </ul>
    <p><a href="/metrics">View live metrics JSON</a></p>
    <script>
      const alertBanner = document.querySelector("#alertBanner");
      const alertMessage = document.querySelector("#alertMessage");
      const alertMeta = document.querySelector("#alertMeta");
      const ackAlertForm = document.querySelector("#ackAlertForm");

      function showAlert(alert) {{
        alertBanner.style.display = "block";
        alertMessage.textContent = alert.message;
        alertMeta.textContent = `Severity: ${{alert.severity}} | Received: ${{alert.received_at}}`;
      }}

      function hideAlert() {{
        alertBanner.style.display = "none";
        alertMessage.textContent = "";
        alertMeta.textContent = "";
      }}

      async function refreshAlert() {{
        const response = await fetch("/metrics", {{ cache: "no-store" }});
        const metrics = await response.json();
        if (metrics.active_alert) {{
          showAlert(metrics.active_alert);
        }} else {{
          hideAlert();
        }}
      }}

      ackAlertForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        await fetch("/ack-alert", {{ method: "POST" }});
        await refreshAlert();
      }});

      refreshAlert();
      setInterval(refreshAlert, 2000);
    </script>
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

    def do_POST(self) -> None:
        if self.path == "/ack-alert":
            with state_lock:
                if state["active_alert"]:
                    state["alerts_acknowledged"] += 1
                    state["last_alert_acknowledged_at"] = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ).replace("+00:00", "Z")
                state["active_alert"] = None

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if self.path != "/alert":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}

        message = str(payload.get("message", "Cloud Sentinel alert received."))
        severity = str(payload.get("severity", "critical"))
        with state_lock:
            state["alerts_received"] += 1
            state["active_alert"] = {
                "message": message,
                "severity": severity,
                "received_at": datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            }

        self._send_json({"ok": True, "message": "Alert displayed on BIM worker screen."})

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    threading.Thread(target=_render_loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
