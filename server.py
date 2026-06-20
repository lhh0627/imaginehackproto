from __future__ import annotations

import json
import os
import time
import urllib.request
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

IGNORE_LABEL = "sustainability.ignore"
METRICS_URL_LABEL = "sustainability.metrics_url"
ALERT_URL_LABEL = "sustainability.alert_url"
APP_STARTED_AT = time.time()
ENVIRONMENT_NAME = os.getenv("SENTINEL_ENVIRONMENT", "hilti-jobsite-prod-demo")
REGION = os.getenv("SENTINEL_REGION", "eu-central-1")
CLUSTER_NAME = os.getenv("SENTINEL_CLUSTER", "docker-edge-node-01")
SCAN_INTERVAL_SECONDS = int(os.getenv("SENTINEL_SCAN_INTERVAL_SECONDS", "8"))
OPERATING_SINCE = os.getenv("SENTINEL_OPERATING_SINCE", "2026-06-20T00:00:00Z")
DAILY_REPORT_UTC = os.getenv("SENTINEL_DAILY_REPORT_UTC", "17:00")
CLOUD_RULES_PATH = Path(os.getenv("SENTINEL_CLOUD_RULES", "cloud_firewall_rules.json"))

_simulated_fixed = False
_simulated_alert_message = ""
_simulated_alerts_received = 0
_scan_count = 0
_alerts_count = 0
_telemetry_history = deque(maxlen=18)
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
    public_endpoints: list[str]
    exposure_paths: list[str]
    internet_reachable: bool
    risk_level: str
    issue: str
    energy_kwh_hour: float
    carbon_kg_hour: float
    monthly_cost_usd: float
    cpu_pct: float
    expected_cpu_pct: float
    expected_energy_kwh_hour: float
    energy_over_baseline_kwh_hour: float
    efficiency_status: str
    efficiency_issue: str
    alert_recommended: bool
    memory_mb: float
    workload_active: bool
    jobs_completed: int
    active_render_jobs: int
    telemetry_source: str
    current_task: str
    current_model: str
    frame_progress_pct: float
    model_elements_processed: int
    triangles_processed: int
    render_queue_depth: int
    alert_active: bool
    alert_message: str
    alerts_received: int
    alerts_acknowledged: int
    last_alert_acknowledged_at: str
    findings: list[str]
    recommendation: str
    can_alert: bool


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


def _live_metrics(labels: dict[str, str]) -> dict[str, Any]:
    metrics_url = labels.get(METRICS_URL_LABEL)
    if not metrics_url:
        return {}

    try:
        with urllib.request.urlopen(metrics_url, timeout=0.6) as response:
            if response.status != 200:
                return {}
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
    except (OSError, TimeoutError, json.JSONDecodeError):
        return {}


def _float_metric(metrics: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(metrics.get(key, default))
    except (TypeError, ValueError):
        return default


def _int_metric(metrics: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(metrics.get(key, default))
    except (TypeError, ValueError):
        return default


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=1.2) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


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


def _cloud_endpoints_for_service(service_name: str) -> list[dict[str, Any]]:
    inventory = _load_cloud_rules()
    return [
        endpoint
        for endpoint in inventory.get("endpoints", [])
        if str(endpoint.get("service", "")).lower() == service_name.lower()
    ]


def _is_public_source(source: Any) -> bool:
    return str(source).lower() in {"0.0.0.0/0", "::/0", "internet", "any"}


def _host_ports(public_ports: list[str]) -> set[int]:
    ports = set()
    for port in public_ports:
        try:
            host_side = port.split("->", 1)[0]
            host_port = host_side.rsplit(":", 1)[1]
            ports.add(int(host_port))
        except (IndexError, ValueError):
            continue
    return ports


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
                "port": port,
                "protocol": protocol,
                "target": rule.get("target", "unknown-target"),
            }
        )
    return exposures


def _public_endpoints(service_name: str) -> list[str]:
    endpoints = []
    for endpoint in _cloud_endpoints_for_service(service_name):
        scheme = endpoint.get("scheme", "internal")
        dns = endpoint.get("dns", "unknown-endpoint")
        public_ip = endpoint.get("public_ip")
        ports = ",".join(str(port) for port in endpoint.get("ports", [])) or "unknown"
        if public_ip:
            endpoints.append(f"{scheme} {dns} ({public_ip}) ports {ports}")
        else:
            endpoints.append(f"{scheme} {dns} ports {ports}")
    return endpoints


def _internet_paths(
    service_name: str,
    public_ports: list[str],
    cloud_exposures: list[dict[str, Any]],
) -> list[str]:
    host_ports = _host_ports(public_ports)
    endpoint_lookup = {
        str(endpoint.get("dns", "")): endpoint for endpoint in _cloud_endpoints_for_service(service_name)
    }
    paths = []

    for exposure in cloud_exposures:
        if not any(_is_public_source(source) for source in exposure.get("sources", [])):
            continue

        target = str(exposure.get("target", "unknown-target"))
        endpoint = endpoint_lookup.get(target, {})
        port = exposure.get("port")
        endpoint_label = endpoint.get("dns", target)
        public_ip = endpoint.get("public_ip")
        destination = f"{endpoint_label} ({public_ip})" if public_ip else endpoint_label
        docker_status = (
            f"matched Docker host port {port}"
            if isinstance(port, int) and port in host_ports
            else "no matching Docker host port in local simulation"
        )
        paths.append(
            f"internet -> {exposure['summary']} -> {destination} -> {docker_status}"
        )

    return paths


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
    exposure_paths: list[str],
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

    if exposure_paths:
        findings.append(f"Internet reachable path confirmed: {' | '.join(exposure_paths)}")
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


def _recommendation_from_findings(risk_level: str, can_alert: bool) -> str:
    if can_alert and risk_level in {"critical", "high"}:
        return "Send an alert to the BIM worker/team to pause, secure, or move this workload private."
    if risk_level in {"critical", "high"}:
        return "Restrict public access, remove privileged settings, and review this workload before restart."
    if risk_level == "medium":
        return "Review image/version policy and operational hygiene during the next maintenance window."
    return "Keep monitoring for exposure, inefficient utilization, and policy drift."


def _baseline_assessment(
    name: str,
    role: str,
    workload_active: bool,
    active_render_jobs: int,
    cpu_pct: float,
    energy_kwh_hour: float,
) -> dict[str, Any]:
    descriptor = f"{name} {role}".lower()
    is_render = "render" in descriptor
    is_cache = "cache" in descriptor
    is_api = "api" in descriptor

    if is_render and (workload_active or active_render_jobs > 0):
        expected_cpu = 82.0
        expected_energy = 8.8
        baseline_name = "active BIM render baseline"
    elif is_render:
        expected_cpu = 18.0
        expected_energy = 1.8
        baseline_name = "idle BIM render baseline"
    elif is_cache:
        expected_cpu = 12.0
        expected_energy = 0.65
        baseline_name = "idle cache baseline"
    elif is_api:
        expected_cpu = 18.0
        expected_energy = 0.55
        baseline_name = "private API baseline"
    else:
        expected_cpu = 20.0
        expected_energy = 0.75
        baseline_name = "general workload baseline"

    energy_over = max(0.0, energy_kwh_hour - expected_energy)
    cpu_ratio = cpu_pct / max(expected_cpu, 1.0)
    energy_ratio = energy_kwh_hour / max(expected_energy, 0.1)

    if not workload_active and (energy_ratio >= 1.5 or cpu_ratio >= 1.5):
        status = "zombie suspected"
        issue = (
            f"Idle workload exceeds {baseline_name}: expected {expected_energy:.2f} kWh/h "
            f"and {expected_cpu:.0f}% CPU, observed {energy_kwh_hour:.2f} kWh/h and {cpu_pct:.0f}% CPU."
        )
    elif energy_ratio >= 1.2 or cpu_ratio >= 1.25:
        status = "over baseline"
        issue = (
            f"Workload is above {baseline_name}: expected {expected_energy:.2f} kWh/h "
            f"and {expected_cpu:.0f}% CPU, observed {energy_kwh_hour:.2f} kWh/h and {cpu_pct:.0f}% CPU."
        )
    else:
        status = "normal"
        issue = (
            f"Within {baseline_name}: expected about {expected_energy:.2f} kWh/h "
            f"and {expected_cpu:.0f}% CPU."
        )

    return {
        "expected_cpu_pct": expected_cpu,
        "expected_energy_kwh_hour": expected_energy,
        "energy_over_baseline_kwh_hour": round(energy_over, 2),
        "efficiency_status": status,
        "efficiency_issue": issue,
        "alert_recommended": status in {"over baseline", "zombie suspected"},
    }


def _workload_from_container(container: Any) -> Workload:
    labels = container.labels or {}
    name = _label(labels, "sustainability.name", container.name)
    metrics = _live_metrics(labels)
    public_ports = _public_ports(container)
    cloud_exposure_rules = _cloud_exposures(name)
    endpoint_summaries = _public_endpoints(name)
    exposure_paths = _internet_paths(name, public_ports, cloud_exposure_rules)
    energy_kwh_hour = _float_metric(
        metrics,
        "energy_kwh_hour",
        _float_label(labels, "sustainability.energy_kwh_hour", 0.4),
    )
    role = _label(labels, "sustainability.role", "Cloud workload")
    cpu_pct = _float_metric(metrics, "cpu_pct", _float_label(labels, "sustainability.cpu_pct", 12.0))
    workload_active = bool(metrics.get("workload_active", False))
    active_render_jobs = _int_metric(metrics, "active_render_jobs")
    baseline = _baseline_assessment(
        name=name,
        role=role,
        workload_active=workload_active,
        active_render_jobs=active_render_jobs,
        cpu_pct=cpu_pct,
        energy_kwh_hour=energy_kwh_hour,
    )
    detected_risk, findings = _container_findings(
        container,
        public_ports,
        cloud_exposure_rules,
        exposure_paths,
        energy_kwh_hour,
    )
    if baseline["efficiency_status"] != "normal":
        findings.append(f"Efficiency baseline warning: {baseline['efficiency_issue']}")
        detected_risk = _max_risk(detected_risk, "medium")
    can_alert = bool(labels.get(ALERT_URL_LABEL))
    risk_level = detected_risk
    active_alert = metrics.get("active_alert") if isinstance(metrics.get("active_alert"), dict) else {}

    return Workload(
        id=container.id,
        name=name,
        role=role,
        project=_label(labels, "sustainability.project", "Construction Tech"),
        owner=_label(labels, "sustainability.owner", "platform-ops"),
        status=container.status,
        image=", ".join(container.image.tags) or container.image.short_id,
        public_ports=public_ports,
        cloud_exposures=[exposure["summary"] for exposure in cloud_exposure_rules],
        public_endpoints=endpoint_summaries,
        exposure_paths=exposure_paths,
        internet_reachable=bool(exposure_paths),
        risk_level=risk_level,
        issue=_issue_from_findings(risk_level, findings),
        energy_kwh_hour=energy_kwh_hour,
        carbon_kg_hour=_float_metric(
            metrics,
            "carbon_kg_hour",
            _float_label(labels, "sustainability.carbon_kg_hour", 0.18),
        ),
        monthly_cost_usd=_float_metric(
            metrics,
            "monthly_cost_usd",
            _float_label(labels, "sustainability.monthly_cost_usd", 28.0),
        ),
        cpu_pct=cpu_pct,
        expected_cpu_pct=baseline["expected_cpu_pct"],
        expected_energy_kwh_hour=baseline["expected_energy_kwh_hour"],
        energy_over_baseline_kwh_hour=baseline["energy_over_baseline_kwh_hour"],
        efficiency_status=baseline["efficiency_status"],
        efficiency_issue=baseline["efficiency_issue"],
        alert_recommended=bool(baseline["alert_recommended"] or risk_level in {"critical", "high"}),
        memory_mb=_float_metric(
            metrics,
            "memory_mb",
            _float_label(labels, "sustainability.memory_mb", 256.0),
        ),
        workload_active=workload_active,
        jobs_completed=_int_metric(metrics, "jobs_completed"),
        active_render_jobs=active_render_jobs,
        telemetry_source=str(metrics.get("telemetry_source", "cloud-labels")),
        current_task=str(metrics.get("current_task", "No active render task")),
        current_model=str(metrics.get("current_model", "unknown")),
        frame_progress_pct=_float_metric(metrics, "frame_progress_pct", 0.0),
        model_elements_processed=_int_metric(metrics, "model_elements_processed"),
        triangles_processed=_int_metric(metrics, "triangles_processed"),
        render_queue_depth=_int_metric(metrics, "render_queue_depth"),
        alert_active=bool(active_alert),
        alert_message=str(active_alert.get("message", "")),
        alerts_received=_int_metric(metrics, "alerts_received"),
        alerts_acknowledged=_int_metric(metrics, "alerts_acknowledged"),
        last_alert_acknowledged_at=str(metrics.get("last_alert_acknowledged_at") or ""),
        findings=[
            *(
                [
                    f"Live workload telemetry received from {metrics.get('telemetry_source', 'metrics endpoint')}."
                ]
                if metrics
                else []
            ),
            *findings,
        ],
        recommendation=_recommendation_from_findings(risk_level, can_alert),
        can_alert=can_alert,
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
            public_endpoints=[
                "internal site-data-api.internal.hilti-demo.local ports 80",
            ],
            exposure_paths=[],
            internet_reachable=False,
            risk_level="low",
            issue="Private API with normal utilization.",
            energy_kwh_hour=0.35,
            carbon_kg_hour=0.14,
            monthly_cost_usd=22.0,
            cpu_pct=8.0,
            expected_cpu_pct=18.0,
            expected_energy_kwh_hour=0.55,
            energy_over_baseline_kwh_hour=0.0,
            efficiency_status="normal",
            efficiency_issue="Within private API baseline: expected about 0.55 kWh/h and 18% CPU.",
            alert_recommended=False,
            memory_mb=192.0,
            workload_active=False,
            jobs_completed=0,
            active_render_jobs=0,
            telemetry_source="cloud-labels",
            current_task="No active render task",
            current_model="unknown",
            frame_progress_pct=0.0,
            model_elements_processed=0,
            triangles_processed=0,
            render_queue_depth=0,
            alert_active=False,
            alert_message="",
            alerts_received=0,
            alerts_acknowledged=0,
            last_alert_acknowledged_at="",
            findings=["No exposed ports or risky container settings detected."],
            recommendation="Keep private networking and normal autoscaling policy.",
            can_alert=False,
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
            public_endpoints=[
                "internal model-cache.internal.hilti-demo.local ports 443",
            ],
            exposure_paths=[],
            internet_reachable=False,
            risk_level="medium",
            issue="Internal cache is healthy, but storage growth should be watched.",
            energy_kwh_hour=1.1,
            carbon_kg_hour=0.43,
            monthly_cost_usd=84.0,
            cpu_pct=22.0,
            expected_cpu_pct=12.0,
            expected_energy_kwh_hour=0.65,
            energy_over_baseline_kwh_hour=0.45,
            efficiency_status="zombie suspected",
            efficiency_issue="Idle workload exceeds idle cache baseline: expected 0.65 kWh/h and 12% CPU, observed 1.10 kWh/h and 22% CPU.",
            alert_recommended=True,
            memory_mb=768.0,
            workload_active=False,
            jobs_completed=0,
            active_render_jobs=0,
            telemetry_source="cloud-labels",
            current_task="No active render task",
            current_model="unknown",
            frame_progress_pct=0.0,
            model_elements_processed=0,
            triangles_processed=0,
            render_queue_depth=0,
            alert_active=False,
            alert_message="",
            alerts_received=0,
            alerts_acknowledged=0,
            last_alert_acknowledged_at="",
            findings=["Image uses the mutable 'latest' tag."],
            recommendation="Apply lifecycle cleanup to old BIM artifacts before the next scan.",
            can_alert=False,
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
                public_endpoints=[
                    "internet-facing bim-render-04.prod.hilti-demo.local (203.0.113.42) ports 8081",
                ],
                exposure_paths=[
                    "internet -> sg-hilti-bim-render-prod: allow tcp/8081 from 0.0.0.0/0 -> bim-render-04.prod.hilti-demo.local (203.0.113.42) -> matched Docker host port 8081",
                ],
                internet_reachable=True,
                risk_level="critical",
                issue="Public HTTP port exposed while the render node is burning idle energy.",
                energy_kwh_hour=9.8,
                carbon_kg_hour=4.1,
                monthly_cost_usd=706.0,
                cpu_pct=91.0,
                expected_cpu_pct=82.0,
                expected_energy_kwh_hour=8.8,
                energy_over_baseline_kwh_hour=1.0,
                efficiency_status="normal",
                efficiency_issue="Within active BIM render baseline: expected about 8.80 kWh/h and 82% CPU.",
                alert_recommended=True,
                memory_mb=2048.0,
                workload_active=True,
                jobs_completed=42,
                active_render_jobs=1,
                telemetry_source="live-bim-render-worker",
                current_task="Hilti Tower L23 coordination render",
                current_model="Hilti_Tower_Renovation.ifc",
                frame_progress_pct=48.0,
                model_elements_processed=8842,
                triangles_processed=2040000,
                render_queue_depth=2,
                alert_active=bool(_simulated_alert_message),
                alert_message=_simulated_alert_message,
                alerts_received=_simulated_alerts_received,
                alerts_acknowledged=0,
                last_alert_acknowledged_at="",
                findings=[
                    "Live workload telemetry received from live-bim-render-worker.",
                    "Cloud firewall rule allows internet ingress: sg-hilti-bim-render-prod: allow tcp/8081 from 0.0.0.0/0",
                    "Internet reachable path confirmed: internet -> sg-hilti-bim-render-prod: allow tcp/8081 from 0.0.0.0/0 -> bim-render-04.prod.hilti-demo.local (203.0.113.42) -> matched Docker host port 8081",
                    "Public host port detected: 0.0.0.0:8081->80/tcp",
                    "Publicly exposed workload is also high energy consumption.",
                ],
                recommendation="Send an alert to the BIM worker/team to pause, secure, or move this workload private.",
                can_alert=True,
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


def _record_telemetry(workloads: list[Workload]) -> None:
    target = next((workload for workload in workloads if workload.name == "BIM-Render-04"), None)
    if target is None:
        return

    _telemetry_history.append(
        {
            "scan_id": _scan_count,
            "at": _now_iso(),
            "cpu_pct": round(target.cpu_pct, 2),
            "energy_kwh_hour": round(target.energy_kwh_hour, 2),
            "carbon_kg_hour": round(target.carbon_kg_hour, 2),
            "expected_energy_kwh_hour": round(target.expected_energy_kwh_hour, 2),
            "critical": target.risk_level == "critical",
            "alert_recommended": target.alert_recommended,
            "efficiency_status": target.efficiency_status,
        }
    )


def _telemetry_thresholds() -> dict[str, float]:
    return {
        "cpu_critical_pct": 85.0,
        "energy_critical_kwh_hour": 8.0,
        "carbon_critical_kg_hour": 3.0,
    }


def _telemetry_status() -> dict[str, Any]:
    latest = _telemetry_history[-1] if _telemetry_history else {}
    thresholds = _telemetry_thresholds()
    exceeded = []

    if latest.get("cpu_pct", 0) >= thresholds["cpu_critical_pct"]:
        exceeded.append("CPU")
    if latest.get("energy_kwh_hour", 0) >= thresholds["energy_critical_kwh_hour"]:
        exceeded.append("Energy")
    if latest.get("carbon_kg_hour", 0) >= thresholds["carbon_critical_kg_hour"]:
        exceeded.append("Carbon")

    return {
        "workload": "BIM-Render-04",
        "history": list(_telemetry_history),
        "thresholds": thresholds,
        "latest_exceeded": exceeded,
        "alert_recommended": bool(exceeded or latest.get("alert_recommended")),
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
    inefficient_workloads = [
        workload for workload in workloads if workload.efficiency_status != "normal"
    ]
    compliance_status = "attention required" if risk_counts.get("critical", 0) else "compliant"
    energy_at_risk = sum(
        workload.energy_kwh_hour for workload in workloads if workload.risk_level == "critical"
    )
    carbon_at_risk = sum(
        workload.carbon_kg_hour for workload in workloads if workload.risk_level == "critical"
    )

    return {
        "operating_mode": "continuous guardrail",
        "policy_mode": "monitor, alert, and guide response",
        "scans_24h": daily_scan_capacity + _scan_count,
        "alerts_24h": _alerts_count,
        "active_findings": active_findings,
        "inefficient_workloads": len(inefficient_workloads),
        "compliance_status": compliance_status,
        "coverage": "all visible Docker containers + cloud firewall rules",
        "daily_report_utc": DAILY_REPORT_UTC,
        "estimated_daily_energy_at_risk_kwh": round(energy_at_risk * 24, 2),
        "estimated_daily_carbon_at_risk_kg": round(carbon_at_risk * 24, 2),
    }


def _critical_summary(workload: Workload) -> str:
    return (
        f"Scan {_scan_count}: critical {workload.name} detected in {ENVIRONMENT_NAME}. "
        f"Task='{workload.current_task}', CPU={workload.cpu_pct:.0f}%, "
        f"energy={workload.energy_kwh_hour:.2f} kWh/h, "
        f"expected_energy={workload.expected_energy_kwh_hour:.2f} kWh/h, "
        f"efficiency='{workload.efficiency_status}', "
        f"carbon={workload.carbon_kg_hour:.2f} kgCO2e/h, "
        f"internet_reachable={workload.internet_reachable}."
    )


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/workloads")
def workloads():
    global _scan_count

    current, source = _current_workloads()
    _scan_count += 1
    _record_telemetry(current)

    critical_workloads = [workload for workload in current if workload.risk_level == "critical"]
    if critical_workloads:
        _add_event(
            "scan",
            "critical",
            _critical_summary(critical_workloads[0]),
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
            "telemetry": _telemetry_status(),
            "workloads": [asdict(workload) for workload in current],
            "totals": _totals(current),
            "events": list(_events)[:8],
        }
    )


@app.post("/api/workloads/<workload_id>/alert")
def alert_workload(workload_id: str):
    global _alerts_count, _simulated_alert_message, _simulated_alerts_received

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
        alert_url = target.labels.get(ALERT_URL_LABEL)
        if not alert_url:
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": f"{target.name} does not expose an alert channel.",
                    }
                ),
                403,
            )

        workload = _workload_from_container(target)
        message = (
            f"Critical Cloud Sentinel alert: {workload.name} is internet reachable while "
            f"running '{workload.current_task}'. CPU={workload.cpu_pct:.0f}%, "
            f"energy={workload.energy_kwh_hour:.2f} kWh/h, "
            f"expected={workload.expected_energy_kwh_hour:.2f} kWh/h, "
            f"efficiency={workload.efficiency_status}, "
            f"carbon={workload.carbon_kg_hour:.2f} kgCO2e/h. "
            "Pause the render or move it behind private networking."
        )
        try:
            result = _post_json(alert_url, {"severity": workload.risk_level, "message": message})
        except (OSError, TimeoutError, json.JSONDecodeError):
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": f"Could not reach alert endpoint for {target.name}.",
                    }
                ),
                502,
            )
        _alerts_count += 1
        _add_event(
            "alert",
            "critical",
            f"Alert sent to {target.name}: {message}",
        )
        return jsonify(
            {
                "ok": True,
                "message": result.get("message", f"Alert sent to {target.name}."),
            }
        )
    except DockerException:
        if workload_id in {"sim-bim-render-04", "BIM-Render-04"}:
            _simulated_alert_message = (
                "Critical Cloud Sentinel alert: BIM-Render-04 is internet reachable while "
                "running 'Hilti Tower L23 coordination render'. CPU=91%, energy=9.80 kWh/h, "
                "expected=8.80 kWh/h, efficiency=normal, carbon=4.10 kgCO2e/h. "
                "Pause the render or move it behind private networking."
            )
            _simulated_alerts_received += 1
            _alerts_count += 1
            _add_event(
                "alert",
                "critical",
                f"Simulation alert sent to BIM-Render-04: {_simulated_alert_message}",
            )
            return jsonify(
                {
                    "ok": True,
                    "message": "Simulation alert displayed on BIM worker screen.",
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
    global _alerts_count, _simulated_alert_message, _simulated_alerts_received, _simulated_fixed
    _simulated_fixed = False
    _simulated_alert_message = ""
    _simulated_alerts_received = 0
    _alerts_count = 0
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
