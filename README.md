# Secure & Energy-Aware Cloud Sentinel

Track 2 Hilti hackathon prototype for the theme **Sustainable Tomorrow**.

This demo shows a deployed-style construction-tech cloud monitor that finds two
kinds of problems at the same time:

- Security exposure: the Python agent really inspects Docker containers and
  discovers public host ports, Docker socket mounts, privileged mode, missing
  health checks, and mutable `latest` image tags.
- Sustainability waste: workloads carry cloud-style metadata for energy,
  carbon, cost, owner, and project so the dashboard can connect security risk
  to sustainability impact.

The dashboard looks like a daily company control plane: it shows agent status,
region, cluster, scan count, risk totals, workload owners, CPU/memory labels,
24-hour scan volume, compliance status, daily report time, remediation count,
estimated energy/carbon savings, and an incident timeline. The user can click
**Auto-Fix**, which sends a command back to Python. Python then removes the
risky Docker workload from the monitored environment.

## What is real vs demo metadata?

Real scanning:

- The backend lists Docker containers through the Docker socket.
- It reads the actual host ports Docker exposes, such as `8081:80`.
- It inspects container settings like health checks, privileged mode, mounted
  Docker socket, and image tags.
- Auto-Fix really removes containers that are explicitly marked safe with
  `sustainability.autofix: "true"`.

Demo/business metadata:

- Energy, carbon, monthly cost, owner, role, and project are labels in
  `docker-compose.yml`.
- Those labels simulate cloud tags that a real AWS/Azure/GCP deployment would
  provide through billing, asset inventory, and carbon reporting APIs.

## Architecture

```text
       START HERE
           |
           v
###################################################
#  BOX 1: DOCKER (Monitored Cloud Workloads)      #
#  - Has BIM-Render-04 running with open port.    #
###################################################
       |                               ^
       |                               |
  1. Python asks:                 4. Python says:
  "What's running?"               "REMOVE BIM-RENDER!"
       |                               |
       v                               |
###################################################
#  BOX 2: PYTHON (server.py)                      #
#  - Middle-man. Talks to Docker and dashboard.   #
###################################################
       |                               ^
       |                               |
  2. Python sends data:           3. User clicks:
  "BIM-Render is vulnerable!"     "Auto-Fix workload"
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
- Fake exposed BIM service: http://localhost:8081

Click **Auto-Fix workload** on `BIM-Render-04`. The dashboard calls
`server.py`, and `server.py` removes the `bim-render-04` container.

The dashboard updates every eight seconds and records the remediation in the
incident timeline.

The daily operations panel shows how the tool would run inside a company:

- Continuous guardrail mode.
- 24-hour scan count based on the configured scan interval.
- Compliance status from current critical findings.
- Daily report schedule for security and sustainability teams.
- Energy/carbon savings after safe remediation.

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
3. "It discovers that `BIM-Render-04` has a real host port exposed:
   `localhost:8081` maps to container port `80`."
4. "The dashboard shows environment health, scan count, risk totals, workload
   owner, CPU, memory, carbon, cost, daily operations KPIs, and the policy
   decision."
5. "When I click Auto-Fix, the dashboard sends a command to Python, Python
   removes the real Docker container, and the incident timeline records the
   remediation. The daily operations panel then updates the remediation count
   and estimated energy/carbon savings."

## API

- `GET /api/workloads` - scan Docker or simulation and return live workloads.
- `POST /api/workloads/<id>/autofix` - remove an auto-fixable demo workload.
- `POST /api/reset-simulation` - reset the Python-only fallback state.
- `GET /api/health` - health check with deployment and risk-count metadata.

## Files

- `server.py` - Flask backend, Docker integration, port scan, and rule engine.
- `static/index.html` - dashboard structure.
- `static/app.js` - scan and auto-fix client logic.
- `static/styles.css` - professional operations dashboard styling.
- `docker-compose.yml` - monitored Docker workloads and cloud-style metadata.
- `Dockerfile` - container for the dashboard/backend.
