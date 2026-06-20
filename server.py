from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, send_from_directory

try:
    import docker
    from docker.errors import DockerException, NotFound
except ImportError:  # pragma: no cover - lets the fallback demo run without Docker SDK.
    docker = None
    DockerException = Exception
    NotFound = Exception


app = Flask(__name__, static_folder="static", static_url_path="")

AUTOFIX_LABEL = "sustainability.autofix"
IGNORE_LABEL = "sustainability.ignore"
APP_STARTED_AT = time.time()
ENVIRONMENT_NAME = os.getenv("SENTINEL_ENVIRONMENT", "hilti-jobsite-prod-demo")
REGION = os.getenv("SENTINEL_REGION", "eu-central-1")
CLUSTER_NAME = os.getenv("SENTINEL_CLUSTER", "docker-edge-node-01")
SCAN_INTERVAL_SECONDS = int(os.getenv("SENTINEL_SCAN_INTERVAL_SECONDS", "8"))
OPERATING_SINCE = os.getenv("SENTINEL_OPERATING_SINCE", "2026-06-20T00:00:00Z")
DAILY_REPORT_UTC = os.getenv("SENTINEL_DAILY_REPORT_UTC", "17:00")
CLOUD_RULES_PATH = Path(os.getenv("SENTINEL_CLOUD_RULES", "cloud_firewall_rules.json"))

_simulated_fixed = False
_scan_count = 0
_remediations_count = 0
_saved_energy_kwh_hour = 0.0
_saved_carbon_kg_hour = 0.0
_events = deque(
    [
        {
            "type": "daily-report",
            "severity": "success",
            "message": "Daily cloud posture report delivered to platform, security, and sustainability teams.",
            "at": "2026-06-20T00:30:00Z",
        },
        {
            "type": "scheduled-scan",
            "severity": "info",
            "message": "Continuous scan schedule active: inventory refresh every 8 seconds.",
            "at": "2026-06-20T00:05:00Z",
        },
        {
            "type": "deployment",
            "severity": "info",
            "message": "Cloud Sentinel agent registered with the construction cloud environment.",
            "at": "2026-06-20T01:00:00Z",
        },
        {
            "type": "policy",
            "severity": "info",
            "message": "Policy loaded: flag public ports with high idle energy as critical.",
            "at": "2026-06-20T01:02:00Z",
        },
    ],
    maxlen=25,
)


@dataclass
class Workload:
    id: str
    name: str
    role: str
    project: str
    owner: str
    status: str
    image: str
    public_ports: list[str]
    cloud_exposures: list[str]
    risk_level: str
    issue: str
    energy_kwh_hour: float
    carbon_kg_hour: float
    monthly_cost_usd: float
    cpu_pct: float
    memory_mb: float
    findings: list[str]
    recommendation: str
    can_autofix: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _add_event(event_type: str, severity: str, message: str) -> None:
    _events.appendleft(
        {
            "type": event_type,
            "severity": severity,
            "message": message,
            "at": _now_iso(),
        }
    )


def _docker_client():
    if docker is None:
        raise DockerException("Docker SDK is not installed")
    return docker.from_env()


def _label(labels: dict[str, str], key: str, default: str) -> str:
    value = labels.get(key)
    return value if value not in (None, "") else default


def _float_label(labels: dict[str, str], key: str, default: float) -> float:
    try:
        return float(labels.get(key, default))
    except (TypeError, ValueError):
        return default


def _rank_value(risk_level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(risk_level, 0)


def _max_risk(*risk_levels: str) -> str:
    return max(risk_levels, key=_rank_value)


def _load_cloud_rules() -> dict[str, Any]:
    try:
        return json.loads(CLOUD_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"provider": "none", "rules": []}


def _cloud_rules_for_service(service_name: str) -> list[dict[str, Any]]:
    inventory = _load_cloud_rules()
    return [
        rule
        for rule in inventory.get("rules", [])
        if str(rule.get("service", "")).lower() == service_name.lower()
    ]


def _is_public_source(source: Any) -> bool:
    return str(source).lower() in {"0.0.0.0/0", "::/0", "internet", "any"}


def _cloud_exposures(service_name: str) -> list[dict[str, Any]]:
    exposures = []
    for rule in _cloud_rules_for_service(service_name):
        if rule.get("direction") != "ingress":
            continue
        protocol = rule.get("protocol", "tcp")
        port = rule.get("port", "any")
        source = rule.get("source", "unknown")
        resource = rule.get("resource", "cloud-firewall")
        exposures.append(
            {
                "summary": f"{resource}: allow {protocol}/{port} from {source}",
                "sources": [source],
            }
        )
    return exposures


def _public_ports(container: Any) -> list[str]:
    ports = []
    for container_port, bindings in (container.ports or {}).items():
        if not bindings:
            continue
        for binding in bindings:
            host_ip = binding.get("HostIp", "0.0.0.0")
            host_port = binding.get("HostPort")
            if host_port:
                ports.append(f"{host_ip}:{host_port}->{container_port}")
    return ports


def _container_findings(
    container: Any,
    public_ports: list[str],
    cloud_exposures: list[dict[str, Any]],
    energy_kwh_hour: float,
) -> tuple[str, list[str]]:
    attrs = container.attrs or {}
    config = attrs.get("Config") or {}
    host_config = attrs.get("HostConfig") or {}
    findings = []
    risk_level = "low"

    if public_ports:
        findings.append(f"Public host port detected: {', '.join(public_ports)}")
        risk_level = _max_risk(risk_level, "high")

    public_cloud_exposures = [
        exposure
        for exposure in cloud_exposures
        if any(_is_public_source(source) for source in exposure.get("sources", []))
    ]
    if public_cloud_exposures:
        exposure_text = ", ".join(exposure["summary"] for exposure in public_cloud_exposures)
        findings.append(
            f"Cloud firewall rule allows internet ingress: {exposure_text}"
        )
        risk_level = _max_risk(risk_level, "high")

    if (public_ports or public_cloud_exposures) and energy_kwh_hour >= 2:
        findings.append("Publicly exposed workload is also high energy consumption.")
        risk_level = _max_risk(risk_level, "critical")

    if host_config.get("Privileged"):
        findings.append("Container is running in privileged mode.")
        risk_level = _max_risk(risk_level, "critical")

    binds = host_config.get("Binds") or []
    if any("/var/run/docker.sock" in bind for bind in binds):
        findings.append("Docker socket is mounted; this container can control Docker.")
        risk_level = _max_risk(risk_level, "high")

    healthcheck = config.get("Healthcheck")
    if not healthcheck:
        findings.append("No container health check configured.")
        risk_level = _max_risk(risk_level, "low")

    image_name = ", ".join(container.image.tags) or container.image.short_id
    if image_name.endswith(":latest"):
        findings.append("Image uses the mutable 'latest' tag.")
        risk_level = _max_risk(risk_level, "medium")

    if not findings:
        findings.append("No exposed ports or risky container settings detected.")

    return risk_level, findings


def _issue_from_findings(risk_level: str, findings: list[str]) -> str:
    if risk_level == "critical":
        return "Critical policy violation: " + findings[0]
    if risk_level == "high":
        return "High-risk container configuration detected: " + findings[0]
    if risk_level == "medium":
        return "Medium-risk operational finding detected: " + findings[0]
    return "No critical security exposure detected."


def _recommendation_from_findings(risk_level: str, can_autofix: bool) -> str:
    if can_autofix and risk_level in {"critical", "high"}:
        return "Auto-fix is available for this workload; remove it from the exposed environment."
    if risk_level in {"critical", "high"}:
        return "Restrict public access, remove privileged settings, and review this workload before restart."
    if risk_level == "medium":
        return "Review image/version policy and operational hygiene during the next maintenance window."
    return "Keep monitoring for exposure, inefficient utilization, and policy drift."


def _workload_from_container(container: Any) -> Workload:
    labels = container.labels or {}
    name = _label(labels, "sustainability.name", container.name)
    public_ports = _public_ports(container)
    cloud_exposure_rules = _cloud_exposures(name)
    energy_kwh_hour = _float_label(labels, "sustainability.energy_kwh_hour", 0.4)
    detected_risk, findings = _container_findings(
        container,
        public_ports,
        cloud_exposure_rules,
        energy_kwh_hour,
    )
    can_autofix = labels.get(AUTOFIX_LABEL, "false").lower() == "true"
    risk_level = detected_risk

    return Workload(
        id=container.id,
        name=name,
        role=_label(labels, "sustainability.role", "Cloud workload"),
        project=_label(labels, "sustainability.project", "Construction Tech"),
        owner=_label(labels, "sustainability.owner", "platform-ops"),
        status=container.status,
        image=", ".join(container.image.tags) or container.image.short_id,
        public_ports=public_ports,
        cloud_exposures=[exposure["summary"] for exposure in cloud_exposure_rules],
        risk_level=risk_level,
        issue=_issue_from_findings(risk_level, findings),
        energy_kwh_hour=energy_kwh_hour,
        carbon_kg_hour=_float_label(labels, "sustainability.carbon_kg_hour", 0.18),
        monthly_cost_usd=_float_label(labels, "sustainability.monthly_cost_usd", 28.0),
        cpu_pct=_float_label(labels, "sustainability.cpu_pct", 12.0),
        memory_mb=_float_label(labels, "sustainability.memory_mb", 256.0),
        findings=findings,
        recommendation=_recommendation_from_findings(risk_level, can_autofix),
        can_autofix=can_autofix,
    )


def _docker_workloads() -> list[Workload]:
    client = _docker_client()
    containers = [
        container
        for container in client.containers.list(all=True)
        if (container.labels or {}).get(IGNORE_LABEL, "false").lower() != "true"
    ]
    return sorted(
        [_workload_from_container(container) for container in containers],
        key=lambda workload: (-_rank_value(workload.risk_level), workload.name),
    )


def _simulated_workloads() -> list[Workload]:
    workloads = [
        Workload(
            id="sim-site-data-api",
            name="Site-Data-API",
            role="Construction telemetry API",
            project="Hilti Connected Jobsite",
            owner="jobsite-platform",
            status="running",
            image="python:3.12-slim",
            public_ports=[],
            cloud_exposures=[
                "sg-hilti-site-api-prod: allow tcp/80 from 10.24.0.0/16",
            ],
            risk_level="low",
            issue="Private API with normal utilization.",
            energy_kwh_hour=0.35,
            carbon_kg_hour=0.14,
            monthly_cost_usd=22.0,
            cpu_pct=8.0,
            memory_mb=192.0,
            findings=["No exposed ports or risky container settings detected."],
            recommendation="Keep private networking and normal autoscaling policy.",
            can_autofix=False,
        ),
        Workload(
            id="sim-model-cache",
            name="Model-Cache",
            role="BIM model cache for project drawings",
            project="Hilti Connected Jobsite",
            owner="digital-twin-team",
            status="running",
            image="alpine:3.20",
            public_ports=[],
            cloud_exposures=[
                "sg-hilti-model-cache-prod: allow tcp/443 from 10.24.0.0/16",
            ],
            risk_level="medium",
            issue="Internal cache is healthy, but storage growth should be watched.",
            energy_kwh_hour=1.1,
            carbon_kg_hour=0.43,
            monthly_cost_usd=84.0,
            cpu_pct=22.0,
            memory_mb=768.0,
            findings=["Image uses the mutable 'latest' tag."],
            recommendation="Apply lifecycle cleanup to old BIM artifacts before the next scan.",
            can_autofix=False,
        ),
    ]

    if not _simulated_fixed:
        workloads.insert(
            0,
            Workload(
                id="sim-bim-render-04",
                name="BIM-Render-04",
                role="Legacy BIM render worker",
                project="Hilti Tower Renovation",
                owner="bim-rendering-team",
                status="running",
                image="nginx:alpine",
                public_ports=["0.0.0.0:8081->80/tcp"],
                cloud_exposures=[
                    "sg-hilti-bim-render-prod: allow tcp/8081 from 0.0.0.0/0",
                ],
                risk_level="critical",
                issue="Public HTTP port exposed while the render node is burning idle energy.",
                energy_kwh_hour=9.8,
                carbon_kg_hour=4.1,
                monthly_cost_usd=706.0,
                cpu_pct=91.0,
                memory_mb=2048.0,
                findings=[
                    "Cloud firewall rule allows internet ingress: sg-hilti-bim-render-prod: allow tcp/8081 from 0.0.0.0/0",
                    "Public host port detected: 0.0.0.0:8081->80/tcp",
                    "Publicly exposed workload is also high energy consumption.",
                ],
                recommendation="Auto-fix by removing this exposed idle render node.",
                can_autofix=True,
            ),
        )

    return workloads


def _current_workloads() -> tuple[list[Workload], str]:
    try:
        workloads = _docker_workloads()
        if workloads:
            return workloads, "docker"
    except DockerException:
        pass
    return _simulated_workloads(), "simulation"


def _totals(workloads: list[Workload]) -> dict[str, float]:
    return {
        "energy_kwh_hour": round(sum(item.energy_kwh_hour for item in workloads), 2),
        "carbon_kg_hour": round(sum(item.carbon_kg_hour for item in workloads), 2),
        "monthly_cost_usd": round(sum(item.monthly_cost_usd for item in workloads), 2),
    }


def _risk_counts(workloads: list[Workload]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for workload in workloads:
        counts[workload.risk_level] = counts.get(workload.risk_level, 0) + 1
    return counts


def _deployment(source: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "environment": ENVIRONMENT_NAME,
        "region": REGION,
        "cluster": CLUSTER_NAME,
        "agent_status": "online",
        "source": source,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        "uptime_seconds": round(time.time() - APP_STARTED_AT),
        "last_scan_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "next_scan_at": (now + timedelta(seconds=SCAN_INTERVAL_SECONDS))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "operating_since": OPERATING_SINCE,
    }


def _operations(workloads: list[Workload]) -> dict[str, Any]:
    risk_counts = _risk_counts(workloads)
    daily_scan_capacity = max(1, 24 * 60 * 60 // SCAN_INTERVAL_SECONDS)
    active_findings = sum(
        1 for workload in workloads if workload.risk_level in {"critical", "high", "medium"}
    )
    compliance_status = "attention required" if risk_counts.get("critical", 0) else "compliant"

    return {
        "operating_mode": "continuous guardrail",
        "policy_mode": "monitor, alert, and safe auto-remediate",
        "scans_24h": daily_scan_capacity + _scan_count,
        "remediations_24h": _remediations_count,
        "active_findings": active_findings,
        "compliance_status": compliance_status,
        "coverage": "all visible Docker containers + cloud firewall rules",
        "daily_report_utc": DAILY_REPORT_UTC,
        "estimated_daily_energy_saved_kwh": round(_saved_energy_kwh_hour * 24, 2),
        "estimated_daily_carbon_saved_kg": round(_saved_carbon_kg_hour * 24, 2),
    }


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/workloads")
def workloads():
    global _scan_count

    current, source = _current_workloads()
    _scan_count += 1

    critical_count = _risk_counts(current).get("critical", 0)
    if critical_count:
        _add_event(
            "scan",
            "critical",
            f"Scan {_scan_count}: {critical_count} critical workload detected in {ENVIRONMENT_NAME}.",
        )

    return jsonify(
        {
            "source": source,
            "deployment": _deployment(source),
            "scan": {
                "id": _scan_count,
                "policy": "Public exposure + high energy waste = critical incident",
                "risk_counts": _risk_counts(current),
                "workload_count": len(current),
            },
            "operations": _operations(current),
            "workloads": [asdict(workload) for workload in current],
            "totals": _totals(current),
            "events": list(_events)[:8],
        }
    )


@app.post("/api/workloads/<workload_id>/autofix")
def autofix(workload_id: str):
    global _remediations_count, _saved_carbon_kg_hour, _saved_energy_kwh_hour, _simulated_fixed

    try:
        client = _docker_client()
        candidates = client.containers.list(all=True)
        target = next(
            (
                container
                for container in candidates
                if container.id.startswith(workload_id)
                or container.name == workload_id
                or container.labels.get("sustainability.name") == workload_id
            ),
            None,
        )

        if target is None:
            raise NotFound(f"No demo workload matched {workload_id}")
        if target.labels.get(AUTOFIX_LABEL, "false").lower() != "true":
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": f"{target.name} is protected and cannot be auto-fixed.",
                    }
                ),
                403,
            )

        fixed_workload = _workload_from_container(target)
        target.remove(force=True)
        _remediations_count += 1
        _saved_energy_kwh_hour += fixed_workload.energy_kwh_hour
        _saved_carbon_kg_hour += fixed_workload.carbon_kg_hour
        _add_event(
            "remediation",
            "success",
            f"Auto-fix removed {target.name}; exposed port and idle energy load eliminated.",
        )
        return jsonify(
            {
                "ok": True,
                "message": f"Auto-fix complete: removed {target.name} from the monitored environment.",
            }
        )
    except DockerException:
        if workload_id in {"sim-bim-render-04", "BIM-Render-04"}:
            _simulated_fixed = True
            _remediations_count += 1
            _saved_energy_kwh_hour += 9.8
            _saved_carbon_kg_hour += 4.1
            _add_event(
                "remediation",
                "success",
                "Simulation auto-fix removed BIM-Render-04; critical risk cleared.",
            )
            return jsonify(
                {
                    "ok": True,
                    "message": "Simulation auto-fix complete: BIM-Render-04 removed.",
                }
            )

    return (
        jsonify(
            {
                "ok": False,
                "message": "Workload was not found or Docker is unavailable.",
            }
        ),
        404,
    )


@app.post("/api/reset-simulation")
def reset_simulation():
    global _remediations_count, _saved_carbon_kg_hour, _saved_energy_kwh_hour, _simulated_fixed
    _simulated_fixed = False
    _remediations_count = 0
    _saved_energy_kwh_hour = 0.0
    _saved_carbon_kg_hour = 0.0
    _add_event("simulation", "info", "Simulation reset: BIM-Render-04 restored for another demo.")
    return jsonify({"ok": True, "message": "Simulation reset."})


@app.get("/api/health")
def health():
    current, source = _current_workloads()
    return jsonify(
        {
            "ok": True,
            "deployment": _deployment(source),
            "operations": _operations(current),
            "workload_count": len(current),
            "risk_counts": _risk_counts(current),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
