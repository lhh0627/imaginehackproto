# Secure & Energy-Aware Cloud Sentinel

Track 2 Hilti hackathon prototype for the theme **Sustainable Tomorrow**.

This demo shows a construction-tech cloud monitor that finds two kinds of
problems at the same time:

- Security exposure: a fake BIM render server is running with a public port.
- Sustainability waste: that same workload is labeled as high energy and
  high-carbon while idle.

The dashboard lets the user click **Auto-Fix**, which sends a command back to
Python. Python then removes the risky Docker workload from the fake cloud.

## Architecture

```text
       START HERE
           |
           v
###################################################
#  BOX 1: DOCKER (Fake Cloud Servers)             #
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
2. "Our Python agent continuously scans the cloud environment. In this demo,
   Docker is the fake cloud."
3. "It finds `BIM-Render-04`, which exposes a public HTTP port and has a high
   idle energy/carbon label."
4. "The dashboard gives the operator one safe recommendation: remove the
   exposed idle render node."
5. "When I click Auto-Fix, the dashboard sends a command to Python, and Python
   removes the container from Docker."

## API

- `GET /api/workloads` - scan Docker or simulation and return live workloads.
- `POST /api/workloads/<id>/autofix` - remove an auto-fixable demo workload.
- `POST /api/reset-simulation` - reset the Python-only fallback state.
- `GET /api/health` - health check.

## Files

- `server.py` - Flask backend and Docker integration.
- `static/index.html` - dashboard structure.
- `static/app.js` - scan and auto-fix client logic.
- `static/styles.css` - cyberpunk dashboard styling.
- `docker-compose.yml` - fake cloud workloads.
- `Dockerfile` - container for the dashboard/backend.
