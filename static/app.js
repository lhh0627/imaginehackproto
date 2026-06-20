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

  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 5) {
    return "just now";
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
    : "<span class=\"private\">No public ports</span>";

  card.innerHTML = `
    <div class="workload-top">
      <div>
        <p class="eyebrow">${escapeHtml(workload.project)}</p>
        <h3>${escapeHtml(workload.name)}</h3>
        <p>${escapeHtml(workload.role)}</p>
      </div>
      <span class="badge">${escapeHtml(riskLevel)}</span>
    </div>
    <div class="ports">${ports}</div>
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
    </dl>
    <p class="recommendation">${escapeHtml(workload.recommendation)}</p>
  `;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "fix-button";
  button.textContent = workload.can_autofix ? "Auto-Fix workload" : "Monitoring only";
  button.disabled = !workload.can_autofix;
  button.addEventListener("click", () => autoFix(workload));
  card.append(button);

  return card;
}

async function scan() {
  refreshButton.disabled = true;
  sourceLabel.textContent = "Scanning cloud environment...";

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
    protectedMetric.textContent = workloads.filter((item) => !item.can_autofix).length;
    intervalMetric.textContent = data.deployment.scan_interval_seconds;
    sourceLabel.textContent =
      data.source === "docker"
        ? `Connected to ${data.deployment.cluster} through Docker socket`
        : "Running deployed-style simulation because Docker is unavailable here";

    workloadsEl.replaceChildren(...workloads.map(workloadCard));
    renderEvents(data.events ?? []);
    log(
      `Scan #${data.scan.id} complete: ${workloads.length} workload(s), ` +
        `${data.scan.risk_counts.critical ?? 0} critical.`,
    );
  } catch (error) {
    sourceLabel.textContent = "Monitor is offline";
    log(error.message);
  } finally {
    refreshButton.disabled = false;
  }
}

async function autoFix(workload) {
  log(`Submitting remediation command for ${workload.name} to the Python agent...`);

  const response = await fetch(
    `/api/workloads/${encodeURIComponent(workload.id)}/autofix`,
    { method: "POST" },
  );
  const result = await response.json();

  if (!response.ok || !result.ok) {
    log(result.message || `Auto-fix failed with HTTP ${response.status}.`);
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

refreshButton.addEventListener("click", scan);
resetButton.addEventListener("click", resetSimulation);

scan();
setInterval(scan, 8000);
