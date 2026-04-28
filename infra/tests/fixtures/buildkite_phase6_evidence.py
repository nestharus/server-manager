from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml


@dataclass(frozen=True)
class Phase6ArtifactPath:
    name: str
    path: str


@dataclass(frozen=True)
class Phase6VerdictRule:
    name: str
    report_name: str
    accepted_verdict: str


@dataclass(frozen=True)
class Phase6EvidenceGateContract:
    scratch_root_glob: str
    required_artifact_paths: tuple[Phase6ArtifactPath, ...]
    verdict_rules: tuple[Phase6VerdictRule, ...]
    required_failure_inputs: tuple[str, ...]
    process_blocking_terms: tuple[str, ...]
    sample_report_root: Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _fixture_root() -> Path:
    return Path(__file__).resolve().parent / "buildkite-phase6"


def _load_contract() -> Phase6EvidenceGateContract:
    contract_path = _fixture_root() / "evidence-gate-contract.yml"
    with contract_path.open(encoding="utf-8") as contract_file:
        raw_contract = yaml.safe_load(contract_file)

    assert isinstance(raw_contract, dict), f"{contract_path} must be a YAML mapping"

    return Phase6EvidenceGateContract(
        scratch_root_glob=str(raw_contract["scratch_root_glob"]),
        required_artifact_paths=tuple(
            Phase6ArtifactPath(name=str(item["name"]), path=str(item["path"]))
            for item in raw_contract["required_artifact_paths"]
        ),
        verdict_rules=tuple(
            Phase6VerdictRule(
                name=str(item["name"]),
                report_name=str(item["report_name"]),
                accepted_verdict=str(item["accepted_verdict"]),
            )
            for item in raw_contract["verdict_rules"]
        ),
        required_failure_inputs=tuple(str(item) for item in raw_contract["required_failure_inputs"]),
        process_blocking_terms=tuple(str(item) for item in raw_contract["process_blocking_terms"]),
        sample_report_root=_fixture_root() / str(raw_contract["sample_report_root"]),
    )


@pytest.fixture(scope="session")
def phase6_evidence_gate_contract() -> Phase6EvidenceGateContract:
    return _load_contract()


@pytest.fixture(scope="session")
def phase6_sample_report_paths(
    phase6_evidence_gate_contract: Phase6EvidenceGateContract,
) -> tuple[Path, ...]:
    root = phase6_evidence_gate_contract.sample_report_root
    repo_root = _repo_root()
    paths = tuple(root / artifact.path.removeprefix(f"{phase6_evidence_gate_contract.scratch_root_glob}/") for artifact in phase6_evidence_gate_contract.required_artifact_paths)

    for path in paths:
        assert path.exists(), f"sample Phase 6 report fixture must exist: {path.relative_to(repo_root)}"

    return paths
