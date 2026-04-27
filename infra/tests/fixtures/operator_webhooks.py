from __future__ import annotations

import json
import os
import shlex
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml


DATA_PATH = Path(__file__).resolve().parent / "data" / "operator_webhooks.yaml"
KUBECONFIG = Path("~/.kube/humility-local.yaml").expanduser()


@dataclass(frozen=True)
class KubectlResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)

    @property
    def diagnostic(self) -> str:
        return (
            f"kubectl exited {self.returncode}\n"
            f"stdout:\n{self.stdout}\n"
            f"stderr:\n{self.stderr}"
        )


@dataclass(frozen=True)
class WebhookEndpoint:
    namespace: str
    service_name: str
    service_port: int
    pod_ip: str
    pod_port: int
    service_probe_path: str
    direct_pod_probe_path: str
    metrics_probe_path: str

    @property
    def service_dns(self) -> str:
        return f"{self.service_name}.{self.namespace}.svc"

    @property
    def service_probe_url(self) -> str:
        return f"https://{self.service_dns}:{self.service_port}{self.service_probe_path}"

    @property
    def direct_pod_probe_url(self) -> str:
        return f"https://{self.pod_ip}:{self.pod_port}{self.direct_pod_probe_path}"

    @property
    def metrics_url(self) -> str:
        return f"https://{self.service_dns}:{self.service_port}{self.metrics_probe_path}"


@dataclass(frozen=True)
class UrlProbe:
    url: str
    http_status: str
    exit_code: int

    @property
    def reached(self) -> bool:
        return self.exit_code == 0 and self.http_status != "000"

    @property
    def denied(self) -> bool:
        return not self.reached


@dataclass(frozen=True)
class ProbeResult:
    namespace: str
    command: KubectlResult
    probes: tuple[UrlProbe, ...]

    @property
    def all_reached(self) -> bool:
        return bool(self.probes) and all(probe.reached for probe in self.probes)

    @property
    def all_denied(self) -> bool:
        return bool(self.probes) and all(probe.denied for probe in self.probes)

    @property
    def diagnostic(self) -> str:
        probe_lines = "\n".join(
            (
                f"{probe.url}: HTTP_STATUS={probe.http_status} "
                f"EXIT={probe.exit_code}"
            )
            for probe in self.probes
        )
        return f"{self.command.diagnostic}\nparsed probes:\n{probe_lines}"


@dataclass(frozen=True)
class ObservabilityScrapeResult:
    reached: bool
    source: str
    diagnostic: str


def _kubectl_base() -> list[str]:
    return ["kubectl", "--kubeconfig", str(KUBECONFIG)]


def _run_kubectl(
    args: list[str],
    *,
    stdin: str | None = None,
    timeout: int = 60,
) -> KubectlResult:
    env = os.environ.copy()
    result = subprocess.run(
        [*_kubectl_base(), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout,
    )
    return KubectlResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _run_kubectl_json(args: list[str]) -> dict[str, Any]:
    result = _run_kubectl([*args, "-o", "json"])
    assert result.returncode == 0, result.diagnostic
    return json.loads(result.stdout)


def _load_fixture_data() -> dict[str, Any]:
    return yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))


def _webhook_services_for_namespace(namespace: str) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for resource in (
        "validatingwebhookconfigurations.admissionregistration.k8s.io",
        "mutatingwebhookconfigurations.admissionregistration.k8s.io",
    ):
        configs = _run_kubectl_json(["get", resource])
        for config in configs.get("items", []):
            for webhook in config.get("webhooks", []):
                service = (
                    webhook.get("clientConfig", {})
                    .get("service")
                )
                if service and service.get("namespace") == namespace:
                    services.append(service)

    unique_services: dict[tuple[str, str, int], dict[str, Any]] = {}
    for service in services:
        port = int(service.get("port", 443))
        key = (service["namespace"], service["name"], port)
        unique_services[key] = service
    return list(unique_services.values())


def _first_endpoint_address(namespace: str, service_name: str) -> tuple[str, int]:
    endpoints = _run_kubectl_json(["get", "endpoints", service_name, "-n", namespace])
    for subset in endpoints.get("subsets", []):
        addresses = subset.get("addresses", [])
        ports = subset.get("ports", [])
        if addresses and ports:
            return addresses[0]["ip"], int(ports[0]["port"])

    pytest.fail(
        f"No ready endpoint address found for webhook service "
        f"{namespace}/{service_name}"
    )


def _parse_probe_output(output: str) -> tuple[UrlProbe, ...]:
    probes: list[UrlProbe] = []
    for line in output.splitlines():
        if not line.startswith("URL="):
            continue

        parts = line.split()
        values = {
            key: value
            for key, value in (
                part.split("=", 1)
                for part in parts
                if "=" in part
            )
        }
        probes.append(
            UrlProbe(
                url=values["URL"],
                http_status=values.get("HTTP_STATUS", "000"),
                exit_code=int(values.get("EXIT", "99")),
            )
        )
    return tuple(probes)


@pytest.fixture(scope="session")
def operator_webhook_data() -> dict[str, Any]:
    return _load_fixture_data()


@pytest.fixture(scope="session")
def webhook_endpoint(
    operator_webhook_data: dict[str, Any],
) -> Callable[[str], WebhookEndpoint]:
    def get_endpoint(namespace: str) -> WebhookEndpoint:
        services = _webhook_services_for_namespace(namespace)
        assert services, (
            f"No admission webhook service found for namespace {namespace}. "
            "The closed R.01 namespace list expects an operator webhook here."
        )
        service = services[0]
        pod_ip, pod_port = _first_endpoint_address(namespace, service["name"])
        defaults = operator_webhook_data["probe_defaults"]

        return WebhookEndpoint(
            namespace=namespace,
            service_name=service["name"],
            service_port=int(service.get("port", 443)),
            pod_ip=pod_ip,
            pod_port=pod_port,
            service_probe_path=defaults["service_probe_path"],
            direct_pod_probe_path=defaults["direct_pod_probe_path"],
            metrics_probe_path=defaults["metrics_probe_path"],
        )

    return get_endpoint


@pytest.fixture()
def probe_pod(
    operator_webhook_data: dict[str, Any],
) -> Callable[[str, list[str]], ProbeResult]:
    defaults = operator_webhook_data["probe_defaults"]

    def run_probe(namespace: str, urls: list[str]) -> ProbeResult:
        pod_name = f"op-webhook-{namespace[:24]}-{uuid.uuid4().hex[:8]}".replace(
            "_", "-"
        )
        timeout = int(defaults["curl_timeout_seconds"])

        # Step 1: create the probe pod, sleep so we can exec into it after
        # CNI convergence. This avoids the race where `kubectl run -i`
        # starts curl before kube-router/flannel has updated NetworkPolicy
        # ipsets/iptables for the newly-created pod.
        create = _run_kubectl(
            [
                "run",
                pod_name,
                "--restart=Never",
                "-n",
                namespace,
                f"--image={defaults['curl_image']}",
                "--command",
                "--",
                "sh",
                "-c",
                "sleep 600",
            ],
            timeout=60,
        )
        assert create.returncode == 0, create.diagnostic

        try:
            # Step 2: wait for Pod Ready (kubelet reports Ready independent
            # of CNI NetworkPolicy convergence).
            wait_ready = _run_kubectl(
                [
                    "wait",
                    "--for=condition=Ready",
                    f"pod/{pod_name}",
                    "-n",
                    namespace,
                    "--timeout=60s",
                ],
                timeout=90,
            )
            assert wait_ready.returncode == 0, wait_ready.diagnostic

            # Step 3: wait for CNI NetworkPolicy convergence by polling a
            # known-always-allowed path: DNS to kube-system/coredns. If DNS
            # works from inside this pod, NetworkPolicy ingress/egress rules
            # have applied for this pod's source IP.
            convergence_script = (
                "for i in $(seq 1 30); do "
                "  if nslookup kubernetes.default.svc.cluster.local "
                "    >/dev/null 2>&1; then "
                "    echo CNI_CONVERGED=true; "
                "    exit 0; "
                "  fi; "
                "  sleep 1; "
                "done; "
                "echo CNI_CONVERGED=false; "
                "exit 1"
            )
            convergence = _run_kubectl(
                [
                    "exec",
                    pod_name,
                    "-n",
                    namespace,
                    "--",
                    "sh",
                    "-c",
                    convergence_script,
                ],
                timeout=60,
            )
            assert convergence.returncode == 0, (
                "CNI NetworkPolicy convergence timeout; probe pod could not "
                f"resolve DNS within 30s.\n{convergence.diagnostic}"
            )

            # Step 4: now run the actual curls. By this point NetworkPolicy
            # is fully applied for this pod, so the test exercises real policy.
            probe_script = "\n".join(
                [
                    "set +e",
                    *[
                        (
                            f'code="$(curl -skm {timeout} -o /tmp/probe-body '
                            f'-w "%{{http_code}}" "{url}")"; '
                            "exit_code=$?; "
                            f'printf "URL={url} HTTP_STATUS=%s EXIT=%s\\n" '
                            '"$code" "$exit_code"'
                        )
                        for url in urls
                    ],
                    "exit 0",
                ]
            )
            result = _run_kubectl(
                [
                    "exec",
                    pod_name,
                    "-n",
                    namespace,
                    "--",
                    "sh",
                    "-c",
                    probe_script,
                ],
                timeout=120,
            )
        finally:
            _run_kubectl(
                [
                    "delete",
                    "pod",
                    pod_name,
                    "-n",
                    namespace,
                    "--ignore-not-found",
                    "--grace-period=0",
                    "--force",
                    "--wait=false",
                ],
                timeout=60,
            )

        assert result.returncode == 0, result.diagnostic
        probes = _parse_probe_output(result.stdout)
        assert probes, result.diagnostic
        return ProbeResult(namespace=namespace, command=result, probes=probes)

    return run_probe


@pytest.fixture()
def admission_dry_run(
    operator_webhook_data: dict[str, Any],
) -> Callable[[str], KubectlResult]:
    def run_dry_run(namespace: str) -> KubectlResult:
        manifest = operator_webhook_data["operator_webhooks"][namespace][
            "admission_probe"
        ]
        manifest_yaml = yaml.safe_dump(manifest, sort_keys=False)
        return _run_kubectl(
            ["apply", "--dry-run=server", "-f", "-"],
            stdin=manifest_yaml,
            timeout=60,
        )

    return run_dry_run


@pytest.fixture()
def observability_scrape(
    operator_webhook_data: dict[str, Any],
    probe_pod: Callable[[str, list[str]], ProbeResult],
    webhook_endpoint: Callable[[str], WebhookEndpoint],
) -> Callable[[str], ObservabilityScrapeResult]:
    def scrape(namespace: str) -> ObservabilityScrapeResult:
        defaults = operator_webhook_data["probe_defaults"]
        query = operator_webhook_data["operator_webhooks"][namespace][
            "prometheus_query"
        ]
        prometheus_url = f"{defaults['prometheus_base_url']}/api/v1/query"
        script = "\n".join(
            [
                "set +e",
                (
                    "curl -sS -m 8 -G --data-urlencode "
                    f"{shlex.quote(f'query={query}')} "
                    f"{shlex.quote(prometheus_url)}"
                ),
                'printf "\\nPROMETHEUS_EXIT=%s\\n" "$?"',
                "exit 0",
            ]
        )
        pod_name = f"op-webhook-prom-{namespace[:22]}-{uuid.uuid4().hex[:8]}".replace(
            "_", "-"
        )
        prometheus = _run_kubectl(
            [
                "run",
                pod_name,
                "--rm",
                "-i",
                "--restart=Never",
                "-n",
                defaults["allowed_probe_namespace"],
                f"--image={defaults['curl_image']}",
                "--command",
                "--",
                "sh",
                "-c",
                script,
            ],
            timeout=120,
        )
        _run_kubectl(
            [
                "delete",
                "pod",
                pod_name,
                "-n",
                defaults["allowed_probe_namespace"],
                "--ignore-not-found",
            ],
            timeout=30,
        )

        if prometheus.returncode == 0:
            json_start = prometheus.stdout.find("{")
            json_end = prometheus.stdout.rfind("}")
            if json_start != -1 and json_end != -1:
                payload = json.loads(prometheus.stdout[json_start : json_end + 1])
                values = [
                    float(result["value"][1])
                    for result in payload.get("data", {}).get("result", [])
                ]
                if any(value == 1 for value in values):
                    return ObservabilityScrapeResult(
                        reached=True,
                        source="prometheus-up",
                        diagnostic=prometheus.diagnostic,
                    )
                if values:
                    return ObservabilityScrapeResult(
                        reached=False,
                        source="prometheus-up",
                        diagnostic=prometheus.diagnostic,
                    )

        endpoint = webhook_endpoint(namespace)
        manual = probe_pod(
            defaults["allowed_probe_namespace"],
            [endpoint.metrics_url],
        )
        return ObservabilityScrapeResult(
            reached=manual.all_reached,
            source="manual-observability-namespace-scrape",
            diagnostic=(
                "Prometheus query had no matching up sample; used contract "
                f"fallback manual scrape.\nPrometheus:\n{prometheus.diagnostic}\n"
                f"Manual:\n{manual.diagnostic}"
            ),
        )

    return scrape


@pytest.fixture()
def denied_probe_namespace(operator_webhook_data: dict[str, Any]) -> str:
    return operator_webhook_data["probe_defaults"]["denied_probe_namespace"]
