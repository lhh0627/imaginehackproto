---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0f172a;
    color: #f8fafc;
  }
  h1, h2 { color: #f8fafc; }
  strong { color: #38bdf8; }
  em { color: #86efac; font-style: normal; }
  section.lead {
    text-align: center;
    justify-content: center;
  }
  section.lead h1 { font-size: 2.4em; margin-bottom: 0.2em; }
  section.lead p { font-size: 1.2em; color: #94a3b8; }
  .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
  .pill {
    display: inline-block;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 999px;
    padding: 0.35em 1em;
    margin: 0.2em;
    font-size: 0.85em;
  }
  .metric {
    background: #1e293b;
    border-left: 4px solid #38bdf8;
    padding: 0.8em 1em;
    margin: 0.5em 0;
    border-radius: 0 8px 8px 0;
  }
  footer { color: #64748b; font-size: 0.7em; }
---

<!-- _class: lead -->

# Secure & Energy-Aware Cloud Sentinel

**One dashboard. Security + sustainability. Built for construction cloud.**

Track 2 · Hilti · Sustainable Tomorrow

<!--
SPEAKER (~20s): Open with confidence. You're not pitching a school project — you're pitching an operations product Hilti could deploy tomorrow.
-->

---

## The hidden problem on every jobsite cloud

Construction teams run **BIM rendering**, **site telemetry**, and **project data** in the cloud every day.

But those workloads are often:

- **Exposed to the internet** — open ports, weak container settings
- **Wasting energy** — idle services still burning power and carbon
- **Hard to fix** — security and sustainability live in separate tools

> *A single misconfigured render server can be both a cyber risk and a carbon leak.*

<!--
SPEAKER (~35s): Paint the pain. Hilti customers trust physical tools on site — digital infrastructure should meet the same bar. Most teams don't know what's exposed OR what's wasting money until it's too late.
-->

---

## Why this matters for Hilti

<div class="columns">

<div>

### Hilti's promise
**Reliability on the jobsite** — physical and digital.

### Today's gap
Cloud workloads grow faster than guardrails.

</div>

<div>

<div class="metric"><strong>Security</strong> — protect project data & BIM assets</div>
<div class="metric"><strong>Sustainability</strong> — cut idle cloud waste & carbon</div>
<div class="metric"><strong>Cost</strong> — stop paying for zombie workloads</div>
<div class="metric"><strong>Compliance</strong> — continuous posture, not annual audits</div>

</div>

</div>

<!--
SPEAKER (~35s): Connect directly to Hilti's brand. They sell trust and reliability. Cloud Sentinel extends that promise into the digital layer — security AND sustainability in one place, not two separate dashboards.
-->

---

<!-- _class: lead -->

# Meet **Cloud Sentinel**

### Your automated guardrail for construction-tech cloud

<span class="pill">Continuous scanning</span>
<span class="pill">Root-cause diagnosis</span>
<span class="pill">Carbon & cost visibility</span>
<span class="pill">1-click worker alerts</span>

*Like a Hilti tool for your cloud — always on, always checking.*

<!--
SPEAKER (~25s): Name the product clearly. Position it as an operations control plane, not just a scanner. One sentence: "Cloud Sentinel is the guardrail that keeps Hilti's cloud as reliable as its tools on site."
-->

---

## How it works

```
Internet ──► Cloud firewall ──► Public endpoint ──► Docker workload
                    ▲                                      │
                    │         Cloud Sentinel scans         │
                    └──────────── every 8 seconds ◄────────┘
                                      │
                                      ▼
                         Operations dashboard + alerts
```

1. **Scan** live workloads & cloud firewall rules
2. **Correlate** exposure routes end-to-end
3. **Diagnose** root cause, owner, ticket, consequences
4. **Alert** the right worker with one click

<!--
SPEAKER (~30s): Keep it simple — don't go deep on Docker. Say: "The agent runs continuously, finds problems, explains why they exist, and helps teams fix them fast."
-->

---

## Security: find exposure before attackers do

**Cloud Sentinel discovers:**

- Public ports open to `0.0.0.0/0`
- Privileged containers & Docker socket mounts
- Missing health checks & risky image tags
- Full exposure route: *internet → firewall → endpoint → workload*

**Exposure Diagnosis tells you:**
- Who opened the port & which change ticket
- Why it was opened & whether it's still needed
- Consequences & recommended fix

*Not just "you have a risk" — **why it happened and what to do.***

<!--
SPEAKER (~40s): This is your wow slide for security judges. Use the BIM-Render-04 example: port 8081 open to the world. The dashboard doesn't just flag it — it explains the full chain and the business context.
-->

---

## Sustainability: stop paying for idle cloud

**Cloud Sentinel tracks per workload:**

- Energy use · Carbon · Monthly cost
- Owner · Project · Workload type

**Baseline engine flags:**

| Status | Meaning |
|--------|---------|
| **Normal** | Healthy usage for workload type |
| **Over baseline** | Active but consuming too much |
| **Zombie suspected** | Idle but still wasting energy |

> *Security risk and carbon waste often live on the **same forgotten server.***

<!--
SPEAKER (~35s): Tie to Sustainable Tomorrow theme. Hilti cares about carbon — this shows which workloads are burning energy for no value. One dashboard shows security AND sustainability impact together.
-->

---

## Remediation: human-in-the-loop, not blind auto-fix

### The workflow

1. Operator sees risk on the **operations dashboard**
2. Clicks **Send worker alert**
3. BIM worker screen shows a **visible red alert banner**
4. Worker clicks **Yes, acknowledge and close**
5. Incident logged · alert count updated · posture refreshed

**Why this matters for Hilti:**
- Respects real operations — alerts the **owner**, not a silent script
- Creates an **audit trail** for compliance
- Closes the loop in seconds, not days

<!--
SPEAKER (~35s): Demo this live if possible. The click → alert → acknowledge flow is your most memorable moment. Emphasize: responsible remediation, not reckless automation.
-->

---

## Business impact for Hilti

<div class="columns">

<div>

### For operations teams
- One control plane for daily cloud health
- 24h scan volume & compliance status
- Incident timeline & daily report schedule

</div>

<div>

### For the business
- **Lower cloud spend** — kill zombie workloads
- **Lower carbon** — align with sustainability goals
- **Stronger security** — catch exposure early
- **Digital trust** — reliability on par with physical tools

</div>

</div>

<!--
SPEAKER (~30s): Speak to ROI. Even demo numbers matter: "If one idle BIM render node costs hundreds per month and leaks carbon 24/7, Cloud Sentinel finds it in the first scan cycle."
-->

---

<!-- _class: lead -->

# Live demo

**Dashboard** → exposed BIM workload → diagnosis → alert → acknowledge

### Thank you

**Secure & Energy-Aware Cloud Sentinel**
*Security & sustainability operations for construction cloud*

Questions?

<!--
SPEAKER (~45s): Transition to demo. Hit these beats in order: (1) dashboard overview, (2) BIM-Render-04 risk card, (3) exposure diagnosis panel, (4) baseline/zombie status, (5) Send worker alert, (6) worker banner acknowledge. Close: "Cloud Sentinel — because Hilti's digital infrastructure should be as dependable as everything on the jobsite."
-->
