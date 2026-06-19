from __future__ import annotations

from dataclasses import dataclass, asdict
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

DEMO_LABEL = "sustainability.demo"
AUTOFIX_LABEL = "sustainability.autofix"

_simulated_fixed = False


@dataclass
class Workload:
    id: str
    name: str
    role: str
    project: str
    status: str
    image: str
    public_ports: list[str]
    risk_level: str
    issue: str
    energy_kwh_hour: float
    carbon_kg_hour: float
    monthly_cost_usd: float
    recommendation: str
    can_autofix: bool


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


def _workload_from_container(container: Any) -> Workload:
    labels = container.labels or {}
    public_ports = _public_ports(container)
    default_risk = "critical" if public_ports else "low"
    risk_level = _label(labels, "sustainability.risk", default_risk)

    return Workload(
        id=container.id,
        name=_label(labels, "sustainability.name", container.name),
        role=_label(labels, "sustainability.role", "Cloud workload"),
        project=_label(labels, "sustainability.project", "Construction Tech"),
        status=container.status,
        image=", ".join(container.image.tags) or container.image.short_id,
        public_ports=public_ports,
        risk_level=risk_level,
        issue=_label(
            labels,
            "sustainability.issue",
            "No critical security or energy issue detected.",
        ),
        energy_kwh_hour=_float_label(labels, "sustainability.energy_kwh_hour", 0.4),
        carbon_kg_hour=_float_label(labels, "sustainability.carbon_kg_hour", 0.18),
        monthly_cost_usd=_float_label(labels, "sustainability.monthly_cost_usd", 28.0),
        recommendation=_label(
            labels,
            "sustainability.recommendation",
            "Keep monitoring for exposure, idle load, and carbon spikes.",
        ),
        can_autofix=labels.get(AUTOFIX_LABEL, "false").lower() == "true",
    )


def _docker_workloads() -> list[Workload]:
    client = _docker_client()
    containers = client.containers.list(
        all=True,
        filters={"label": f"{DEMO_LABEL}=true"},
    )
    return sorted(
        [_workload_from_container(container) for container in containers],
        key=lambda workload: (workload.risk_level != "critical", workload.name),
    )


def _simulated_workloads() -> list[Workload]:
    workloads = [
        Workload(
            id="sim-site-data-api",
            name="Site-Data-API",
            role="Construction telemetry API",
            project="Hilti Connected Jobsite",
            status="running",
            image="python:3.12-slim",
            public_ports=[],
            risk_level="low",
            issue="Private API with normal utilization.",
            energy_kwh_hour=0.35,
            carbon_kg_hour=0.14,
            monthly_cost_usd=22.0,
            recommendation="Keep private networking and normal autoscaling policy.",
            can_autofix=False,
        )
    ]

    if not _simulated_fixed:
        workloads.insert(
            0,
            Workload(
                id="sim-bim-render-04",
                name="BIM-Render-04",
                role="Legacy BIM render worker",
                project="Hilti Tower Renovation",
                status="running",
                image="nginx:alpine",
                public_ports=["0.0.0.0:8081->80/tcp"],
                risk_level="critical",
                issue="Public HTTP port exposed while the render node is burning idle energy.",
                energy_kwh_hour=9.8,
                carbon_kg_hour=4.1,
                monthly_cost_usd=706.0,
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


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/workloads")
def workloads():
    current, source = _current_workloads()
    return jsonify(
        {
            "source": source,
            "workloads": [asdict(workload) for workload in current],
            "totals": _totals(current),
        }
    )


@app.post("/api/workloads/<workload_id>/autofix")
def autofix(workload_id: str):
    global _simulated_fixed

    try:
        client = _docker_client()
        candidates = client.containers.list(
            all=True,
            filters={"label": f"{DEMO_LABEL}=true"},
        )
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

        target.remove(force=True)
        return jsonify(
            {
                "ok": True,
                "message": f"Auto-fix complete: removed {target.name} from the fake cloud.",
            }
        )
    except DockerException:
        if workload_id in {"sim-bim-render-04", "BIM-Render-04"}:
            _simulated_fixed = True
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
    global _simulated_fixed
    _simulated_fixed = False
    return jsonify({"ok": True, "message": "Simulation reset."})


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
