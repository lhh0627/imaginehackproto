const workloadsEl = document.querySelector("#workloads");
const sourceLabel = document.querySelector("#sourceLabel");
const commandLog = document.querySelector("#commandLog");
const refreshButton = document.querySelector("#refreshButton");
const resetButton = document.querySelector("#resetButton");
const energyMetric = document.querySelector("#energyMetric");
const carbonMetric = document.querySelector("#carbonMetric");
const costMetric = document.querySelector("#costMetric");

const riskRank = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

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

function workloadCard(workload) {
  const card = document.createElement("article");
  card.className = `panel workload risk-${workload.risk_level}`;

  const ports = workload.public_ports.length
    ? workload.public_ports.map((port) => `<code>${port}</code>`).join("")
    : "<span class=\"private\">No public ports</span>";

  card.innerHTML = `
    <div class="workload-top">
      <div>
        <p class="eyebrow">${workload.project}</p>
        <h3>${workload.name}</h3>
        <p>${workload.role}</p>
      </div>
      <span class="badge">${workload.risk_level}</span>
    </div>
    <div class="ports">${ports}</div>
    <p class="issue">${workload.issue}</p>
    <dl class="stats">
      <div><dt>Energy</dt><dd>${fmt(workload.energy_kwh_hour)} kWh/h</dd></div>
      <div><dt>Carbon</dt><dd>${fmt(workload.carbon_kg_hour)} kg/h</dd></div>
      <div><dt>Cost</dt><dd>$${fmt(workload.monthly_cost_usd, 0)}/mo</dd></div>
      <div><dt>Status</dt><dd>${workload.status}</dd></div>
    </dl>
    <p class="recommendation">${workload.recommendation}</p>
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
  sourceLabel.textContent = "Scanning fake cloud...";

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
    sourceLabel.textContent =
      data.source === "docker"
        ? "Connected to Docker fake cloud"
        : "Docker unavailable: showing built-in simulation";

    workloadsEl.replaceChildren(...workloads.map(workloadCard));
    log(`Scan complete: ${workloads.length} workload(s) from ${data.source}.`);
  } catch (error) {
    sourceLabel.textContent = "Monitor is offline";
    log(error.message);
  } finally {
    refreshButton.disabled = false;
  }
}

async function autoFix(workload) {
  log(`Sending fix command for ${workload.name} to server.py...`);

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
