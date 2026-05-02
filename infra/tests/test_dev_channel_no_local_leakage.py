from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_GITOPS = REPO_ROOT / "gitops" / "channels" / "dev"
DEV_CEDAR_POLICY = (
    REPO_ROOT / "policy" / "cedar" / "channels" / "dev" / "services" / "server-manager-api" / "policies.json"
)
ALLOWED_LOCAL_SUBSTRINGS = {".svc.cluster.local"}
BANNED_PATTERNS = [
    re.compile(r"\b[a-z0-9-]+\.local\.humility\.local\b"),
    re.compile(r'Public::"web-intake\.local"'),
    re.compile(r"/auth/local/"),
    re.compile(r"/postgres/local/"),
    re.compile(r"/object-storage/local/"),
    re.compile(r"/runtime/local\b"),
    re.compile(r"humility-local-step-ca"),
    re.compile(r"StepClusterIssuer"),
    re.compile(r"certmanager\.step\.sm"),
    re.compile(r"\b[^\s\"']+-local-ingress-tls\b"),
    re.compile(r"policy/cedar/channels/local"),
    re.compile(r"\benvSlug:\s*local\b"),
    re.compile(r"\bsecretsPath:\s*/auth/local/"),
    re.compile(r'Service::"[^"]*\.local"'),
    re.compile(r'User::"[^"]*@local\.humility\.local"'),
    re.compile(r'TenantChannel::"[^"]*:local"'),
]


def _dev_files() -> Iterable[Path]:
    assert DEV_GITOPS.is_dir(), f"missing dev GitOps channel: {DEV_GITOPS.relative_to(REPO_ROOT)}"
    yield from sorted(DEV_GITOPS.glob("**/*.yaml"))
    yield from sorted(DEV_GITOPS.glob("**/*.yml"))
    yield DEV_CEDAR_POLICY


def _allowed_line(line: str) -> bool:
    return any(allowed in line for allowed in ALLOWED_LOCAL_SUBSTRINGS)


def test_dev_channel_has_no_local_hostname_or_principal_leakage() -> None:
    findings: list[str] = []
    for path in _dev_files():
        assert path.is_file(), f"missing expected dev file: {path.relative_to(REPO_ROOT)}"
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in BANNED_PATTERNS:
                match = pattern.search(line)
                if match is None:
                    continue
                if _allowed_line(line):
                    continue
                findings.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {match.group(0)}")

    assert findings == [], "local leakage found in dev channel:\n" + "\n".join(findings)
