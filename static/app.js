const workloadsEl = document.querySelector("#workloads");
const sourceLabel = document.querySelector("#sourceLabel");
const commandLog = document.querySelector("#commandLog");
const refreshButton = document.querySelector("#refreshButton");
const resetButton = document.querySelector("#resetButton");
const energyMetric = document.querySelector("#energyMetric");
const carbonMetric = document.querySelector("#carbonMetric");
const costMetric = document.querySelector("#costMetric");
const environmentName = document.querySelector("#environmentName");
const regionMetric = document.querySelector("#regionMetric");
const clusterMetric = document.querySelector("#clusterMetric");
const lastScanMetric = document.querySelector("#lastScanMetric");
const scanIdMetric = document.querySelector("#scanIdMetric");
const criticalMetric = document.querySelector("#criticalMetric");
const protectedMetric = document.querySelector("#protectedMetric");
const intervalMetric = document.querySelector("#intervalMetric");
const eventFeed = document.querySelector("#eventFeed");
const modeMetric = document.querySelector("#modeMetric");
const coverageMetric = document.querySelector("#coverageMetric");
const scans24Metric = document.querySelector("#scans24Metric");
const complianceMetric = document.querySelector("#complianceMetric");
const activeFindingsMetric = document.querySelector("#activeFindingsMetric");
const alertsMetric = document.querySelector("#alertsMetric");
const nextScanMetric = document.querySelector("#nextScanMetric");
const reportMetric = document.querySelector("#reportMetric");
const savedEnergyMetric = document.querySelector("#savedEnergyMetric");
const savedCarbonMetric = document.querySelector("#savedCarbonMetric");

const riskRank = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;",
      })[char],
  );
}

function log(message) {
  const now = new Date().toLocaleTimeString();
  commandLog.textContent = `[${now}] ${message}\n${commandLog.textContent}`;
}

function fmt(value, digits = 1) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function relativeTime(isoValue) {
  const timestamp = new Date(isoValue).getTime();
  if (Number.isNaN(timestamp)) {
    return "--";
  }

  const seconds = Math.round((Date.now() - timestamp) / 1000);
  const absoluteSeconds = Math.abs(seconds);
  if (absoluteSeconds < 5) {
    return "just now";
  }

  if (seconds < 0) {
    if (absoluteSeconds < 60) {
      return `in ${absoluteSeconds}s`;
    }
    return `in ${Math.round(absoluteSeconds / 60)}m`;
  }

  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  return `${Math.round(seconds / 60)}m ago`;
}

function renderEvents(events) {
  if (!events.length) {
    eventFeed.textContent = "No incidents recorded yet.";
    return;
  }

  eventFeed.replaceChildren(
    ...events.map((event) => {
      const row = document.createElement("article");
      row.className = `event severity-${event.severity}`;
      row.innerHTML = `
        <div>
          <strong>${escapeHtml(event.type)}</strong>
          <p>${escapeHtml(event.message)}</p>
        </div>
        <time>${escapeHtml(relativeTime(event.at))}</time>
      `;
      return row;
    }),
  );
}

function workloadCard(workload) {
  const riskLevel = Object.hasOwn(riskRank, workload.risk_level)
    ? workload.risk_level
    : "low";
  const card = document.createElement("article");
  card.className = `panel workload risk-${riskLevel}`;

  const ports = workload.public_ports.length
    ? workload.public_ports.map((port) => `<code>${escapeHtml(port)}</code>`).join("")
    : "<span class=\"private\">No Docker published ports</span>";
  const cloudExposures = workload.cloud_exposures?.length
    ? workload.cloud_exposures
        .map((exposure) => `<code>${escapeHtml(exposure)}</code>`)
        .join("")
    : "<span class=\"private\">No cloud ingress rules</span>";
  const publicEndpoints = workload.public_endpoints?.length
    ? workload.public_endpoints
        .map((endpoint) => `<code>${escapeHtml(endpoint)}</code>`)
        .join("")
    : "<span class=\"private\">No cloud endpoint</span>";
  const exposurePaths = workload.exposure_paths?.length
    ? workload.exposure_paths
        .map((path) => `<li>${escapeHtml(path)}</li>`)
        .join("")
    : "<li>No internet route matched for this workload.</li>";
  const findings = workload.findings?.length
    ? workload.findings
        .map((finding) => `<li>${escapeHtml(finding)}</li>`)
        .join("")
    : "<li>No findings reported by scanner.</li>";

  card.innerHTML = `
    <div class="workload-top">
      <div>
        <p class="eyebrow">${escapeHtml(workload.project)}</p>
        <h3>${escapeHtml(workload.name)}</h3>
        <p>${escapeHtml(workload.role)}</p>
      </div>
      <span class="badge">${escapeHtml(riskLevel)}</span>
    </div>
    <div class="exposure-block">
      <span>Docker published ports</span>
      <div class="ports">${ports}</div>
    </div>
    <div class="exposure-block">
      <span>Cloud firewall / security group rules</span>
      <div class="ports">${cloudExposures}</div>
    </div>
    <p class="issue">${escapeHtml(workload.issue)}</p>
    <dl class="stats">
      <div><dt>Energy</dt><dd>${fmt(workload.energy_kwh_hour)} kWh/h</dd></div>
      <div><dt>Carbon</dt><dd>${fmt(workload.carbon_kg_hour)} kg/h</dd></div>
      <div><dt>Cost</dt><dd>$${fmt(workload.monthly_cost_usd, 0)}/mo</dd></div>
      <div><dt>Status</dt><dd>${escapeHtml(workload.status)}</dd></div>
      <div><dt>Owner</dt><dd>${escapeHtml(workload.owner)}</dd></div>
      <div><dt>CPU</dt><dd>${fmt(workload.cpu_pct, 0)}%</dd></div>
      <div><dt>Memory</dt><dd>${fmt(workload.memory_mb, 0)} MB</dd></div>
      <div><dt>Image</dt><dd>${escapeHtml(workload.image)}</dd></div>
      <div><dt>Internet</dt><dd>${workload.internet_reachable ? "Reachable" : "Private"}</dd></div>
      <div><dt>Workload</dt><dd>${workload.workload_active ? "Active" : "Idle"}</dd></div>
      <div><dt>Jobs</dt><dd>${fmt(workload.jobs_completed ?? 0, 0)}</dd></div>
      <div><dt>Telemetry</dt><dd>${escapeHtml(workload.telemetry_source ?? "cloud-labels")}</dd></div>
      <div><dt>Task</dt><dd>${escapeHtml(workload.current_task ?? "No active render task")}</dd></div>
      <div><dt>Model</dt><dd>${escapeHtml(workload.current_model ?? "unknown")}</dd></div>
      <div><dt>Progress</dt><dd>${fmt(workload.frame_progress_pct ?? 0)}%</dd></div>
      <div><dt>Elements</dt><dd>${fmt(workload.model_elements_processed ?? 0, 0)}</dd></div>
      <div><dt>Triangles</dt><dd>${fmt(workload.triangles_processed ?? 0, 0)}</dd></div>
      <div><dt>Queue</dt><dd>${fmt(workload.render_queue_depth ?? 0, 0)}</dd></div>
    </dl>
    <div class="exposure-block">
      <span>Cloud endpoint</span>
      <div class="ports">${publicEndpoints}</div>
    </div>
    <div class="findings">
      <strong>Detected findings</strong>
      <ul>${findings}</ul>
    </div>
    <div class="findings route">
      <strong>Exposure route</strong>
      <ul>${exposurePaths}</ul>
    </div>
    <p class="recommendation">${escapeHtml(workload.recommendation)}</p>
  `;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "fix-button";
  button.textContent = workload.can_alert ? "Send worker alert" : "Monitoring only";
  button.disabled = !workload.can_alert;
  button.addEventListener("click", () => sendAlert(workload));
  card.append(button);

  return card;
}

async function scan() {
  if (refreshButton) {
    refreshButton.disabled = true;
  }
  if (sourceLabel) {
    sourceLabel.textContent = "Scanning cloud environment...";
  }

  try {
    const response = await fetch("/api/workloads");
    if (!response.ok) {
      throw new Error(`Scan failed with HTTP ${response.status}`);
    }

    const data = await response.json();
    const workloads = [...data.workloads].sort(
      (a, b) => (riskRank[a.risk_level] ?? 9) - (riskRank[b.risk_level] ?? 9),
    );

    energyMetric.textContent = fmt(data.totals.energy_kwh_hour);
    carbonMetric.textContent = fmt(data.totals.carbon_kg_hour);
    costMetric.textContent = `$${fmt(data.totals.monthly_cost_usd, 0)}`;
    environmentName.textContent = data.deployment.environment;
    regionMetric.textContent = data.deployment.region;
    clusterMetric.textContent = data.deployment.cluster;
    lastScanMetric.textContent = relativeTime(data.deployment.last_scan_at);
    scanIdMetric.textContent = `#${data.scan.id}`;
    criticalMetric.textContent = data.scan.risk_counts.critical ?? 0;
    protectedMetric.textContent = workloads.filter((item) => !item.can_alert).length;
    intervalMetric.textContent = data.deployment.scan_interval_seconds;
    modeMetric.textContent = data.operations.operating_mode;
    coverageMetric.textContent = data.operations.coverage;
    scans24Metric.textContent = fmt(data.operations.scans_24h, 0);
    complianceMetric.textContent = data.operations.compliance_status;
    activeFindingsMetric.textContent = `${data.operations.active_findings} active finding(s)`;
    alertsMetric.textContent = fmt(data.operations.alerts_24h, 0);
    nextScanMetric.textContent = relativeTime(data.deployment.next_scan_at);
    reportMetric.textContent = `${data.operations.daily_report_utc} UTC`;
    savedEnergyMetric.textContent = `${fmt(data.operations.estimated_daily_energy_at_risk_kwh)} kWh`;
    savedCarbonMetric.textContent = `${fmt(data.operations.estimated_daily_carbon_at_risk_kg)} kg`;
    if (sourceLabel) {
      sourceLabel.textContent =
        data.source === "docker"
          ? `Connected to ${data.deployment.cluster} through Docker socket`
          : "Running deployed-style simulation because Docker is unavailable here";
    }

    workloadsEl.replaceChildren(...workloads.map(workloadCard));
    renderEvents(data.events ?? []);
    log(
      `Scan #${data.scan.id} complete: ${workloads.length} workload(s), ` +
        `${data.scan.risk_counts.critical ?? 0} critical.`,
    );
  } catch (error) {
    if (sourceLabel) {
      sourceLabel.textContent = "Monitor is offline";
    }
    log(error.message);
  } finally {
    if (refreshButton) {
      refreshButton.disabled = false;
    }
  }
}

async function sendAlert(workload) {
  log(`Sending critical alert for ${workload.name} to the BIM worker screen...`);

  const response = await fetch(
    `/api/workloads/${encodeURIComponent(workload.id)}/alert`,
    { method: "POST" },
  );
  const result = await response.json();

  if (!response.ok || !result.ok) {
    log(result.message || `Alert failed with HTTP ${response.status}.`);
    return;
  }

  log(result.message);
  await scan();
}

async function resetSimulation() {
  const response = await fetch("/api/reset-simulation", { method: "POST" });
  const result = await response.json();
  log(result.message || "Simulation reset requested.");
  await scan();
}

refreshButton?.addEventListener("click", scan);
resetButton?.addEventListener("click", resetSimulation);

scan();
setInterval(scan, 8000);
