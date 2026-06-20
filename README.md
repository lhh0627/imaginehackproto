# Secure & Energy-Aware Cloud Sentinel

Track 2 Hilti hackathon prototype for the theme **Sustainable Tomorrow**.

This demo shows a deployed-style construction-tech cloud monitor that finds two
kinds of problems at the same time:

- Security exposure: the Python agent really inspects Docker containers and
  discovers public host ports, Docker socket mounts, privileged mode, missing
  health checks, mutable `latest` image tags, and cloud-style firewall rules
  that allow internet ingress.
- Sustainability waste: workloads carry cloud-style metadata for energy,
  carbon, cost, owner, and project so the dashboard can connect security risk
  to sustainability impact. `BIM-Render-04` also runs a small render-worker loop
  and exposes `/metrics` so the scanner can use live workload telemetry when
  Docker is running.
- Efficiency drift: the scanner compares live CPU and energy against a simple
  expected baseline for the workload type. If an idle service uses too much
  energy, it is flagged as `zombie suspected`; if an active service exceeds its
  normal range, it is flagged as `over baseline`.

The dashboard looks like a daily company control plane: it shows agent status,
region, cluster, scan count, risk totals, workload owners, CPU/memory labels,
24-hour scan volume, compliance status, daily report time, alert count,
energy/carbon at risk, and an incident timeline. The user can click
**Send worker alert**, which sends a warning through Python to the active BIM
render worker. The worker screen then displays a visible Cloud Sentinel alert
with a **Yes, acknowledge and close** button.

## What is real vs demo metadata?

Real scanning:

- The backend lists Docker containers through the Docker socket.
- It reads the actual host ports Docker exposes, such as `8081:80`.
- It reads live workload telemetry from `BIM-Render-04` at `/metrics`, including
  current BIM render task, model file, frame progress, model elements processed,
  triangles processed, active render jobs, jobs completed, CPU, memory, energy,
  carbon, and cost estimates.
- It estimates expected CPU and energy for active render jobs, idle render
  workers, APIs, caches, and general workloads, then compares actual telemetry
  against that baseline.
- It loads `cloud_firewall_rules.json`, which represents AWS Security Group /
  Azure NSG / GCP Firewall style rules, and flags rules like
  `allow tcp/8081 from 0.0.0.0/0`.
- It correlates cloud endpoint data, firewall rules, and Docker published ports
  to build an exposure route, for example:
  `internet -> security group -> public endpoint -> Docker host port 8081`.
- It explains the root cause of the open port, including the cloud rule that
  opened it, who created the rule, the change ticket, why it was opened, whether
  public exposure is approved, likely consequences, and recommended fixes.
- It inspects container settings like health checks, privileged mode, mounted
  Docker socket, and image tags.
- Alerts are really posted to the BIM worker's internal `/alert` endpoint when
  the workload exposes `sustainability.alert_url`.
- The worker can acknowledge and close the banner through `/ack-alert`, and the
  scanner reads the acknowledgement state back from `/metrics`.

Demo/business metadata:

- Energy, carbon, monthly cost, owner, role, and project are labels in
  `docker-compose.yml` for services that do not expose live metrics.
- `BIM-Render-04` calculates live demo estimates from its render activity. In a
  real company deployment, those values would come from billing, monitoring,
  carbon, utilization, and asset inventory APIs.
- `cloud_firewall_rules.json` is the local demo equivalent of querying cloud
  networking APIs for security groups, firewall rules, or network security
  groups. It includes endpoint DNS names, public IPs, security-group resources,
  source CIDRs, and target ports.

## Architecture

```text
       START HERE
           |
           v
###################################################
#  BOX 1: DOCKER + CLOUD FIREWALL RULES           #
#  - BIM-Render-04 has Docker port 8081 and       #
#    cloud rule: allow tcp/8081 from 0.0.0.0/0.   #
###################################################
       |                               ^
       |                               |
  1. Python asks:                 4. Python says:
  "What's running?"               "SHOW ALERT!"
       |                               |
       v                               |
###################################################
#  BOX 2: PYTHON (server.py)                      #
#  - Middle-man. Talks to Docker and dashboard.   #
###################################################
       |                               ^
       |                               |
  2. Python sends data:           3. User clicks:
  "BIM-Render is vulnerable!"     "Send worker alert"
       |                               |
       v                               |
###################################################
#  BOX 3: DASHBOARD (static/index.html + app.js)  #
#  - Shows security, carbon, energy, and cost.    #
###################################################
```

## Quick start

### Option A: Full Docker demo

```bash
docker compose up --build
```

Open:

- Dashboard: http://localhost:5000
- Exposed BIM service: http://localhost:8081

Click **Send worker alert** on `BIM-Render-04`. The dashboard calls
`server.py`, and `server.py` posts an alert to the worker's `/alert` endpoint.
The BIM worker page then shows a red Cloud Sentinel alert banner.
Click **Yes, acknowledge and close** on the worker page to clear the banner.

The dashboard updates every eight seconds and records the alert in the incident
timeline.

The daily operations panel shows how the tool would run inside a company:

- Continuous guardrail mode.
- 24-hour scan count based on the configured scan interval.
- Compliance status from current critical findings.
- Daily report schedule for security and sustainability teams.
- Energy/carbon currently at risk for critical workloads.
- Baseline status for each workload, including normal, over baseline, and zombie
  suspected.

To bring the vulnerable workload back for another demo:

```bash
docker compose up -d bim-render-04
```

### Option B: Python-only fallback

If Docker is not available, the app still runs with a built-in simulation:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open http://localhost:5000 and use the same dashboard flow.

## What to say in the demo

1. "Construction teams run cloud workloads for BIM rendering, telemetry, and
   project data. These workloads can be both cyber-risky and carbon-heavy."
2. "Our Python agent is deployed as `cloud-sentinel-dashboard`. It continuously
   scans the Docker environment through the Docker socket. Docker is our
   realistic mini cloud for the hackathon."
3. "BIM-Render-04 is actively simulating BIM render jobs and publishing live
   telemetry. The scanner reads its `/metrics` endpoint to get current render
   task, model, frame progress, geometry processed, energy, carbon, cost, CPU,
   and job count estimates."
4. "It discovers that `BIM-Render-04` has a cloud firewall rule open to the
   internet: `allow tcp/8081 from 0.0.0.0/0`. It then matches that to a public
   endpoint and the Docker host port, giving a full route from internet to
   workload."
5. "The exposure diagnosis explains what caused the port to open, what triggered
   it, whether it should be closed, the consequences, and the recommended
   solution."
6. "The dashboard shows environment health, scan count, risk totals, workload
   owner, CPU, memory, carbon, cost, daily operations KPIs, and the policy
   decision."
7. "It also compares actual energy and CPU against expected workload baselines.
   If a workload is idle but still consuming too much, Cloud Sentinel marks it
   as zombie suspected and recommends sending an alert."
8. "When I click Send worker alert, the dashboard sends a command to Python,
   Python posts an alert to the BIM worker, and the worker screen displays the
   warning. The BIM worker can click Yes to acknowledge and close the alert.
   The daily operations panel then updates the alert count and energy/carbon
   at-risk values."

## API

- `GET /api/workloads` - scan Docker or simulation and return live workloads.
- `POST /api/workloads/<id>/alert` - notify an alert-capable workload.
- `POST /api/reset-simulation` - reset the Python-only fallback state.
- `GET /api/health` - health check with deployment and risk-count metadata.

## Files

- `server.py` - Flask backend, Docker integration, port scan, and rule engine.
- `cloud_firewall_rules.json` - local cloud security-group/firewall rule
  inventory used by the scanner.
- `static/index.html` - dashboard structure.
- `static/app.js` - scan and alert client logic.
- `static/styles.css` - professional operations dashboard styling.
- `docker-compose.yml` - monitored Docker workloads and cloud-style metadata.
- `Dockerfile` - container for the dashboard/backend.
- `workloads/bim-render-worker/` - active BIM render workload simulator with
  live `/metrics` telemetry.
