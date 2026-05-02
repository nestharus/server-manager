from pathlib import Path

import pytest
import yaml

REQUIRED_CLUSTER_RUNTIME_VALIDATORS = (
    "infra/tests/validate_object_storage_local.sh",
    "infra/tests/validate_tls_dns_local.sh",
    "infra/tests/validate_app_clusters_local.sh",
    "infra/tests/validate_cluster_security_local.sh",
    "infra/tests/validate_container_delivery_local.sh",
    "infra/tests/validate_kong_kic_translation_local.sh",
)


class ParsedBuildkitePipeline(dict):
    def __init__(self, path: Path, pipeline: dict):
        super().__init__(pipeline)
        self.path = path

    def __repr__(self) -> str:
        return f"<ParsedBuildkitePipeline {self.path}>"


class BuildkitePipelineFamily:
    def __init__(
        self,
        *,
        main: ParsedBuildkitePipeline,
        cluster: ParsedBuildkitePipeline | None,
        nightly: ParsedBuildkitePipeline | None,
    ):
        self.main = main
        self.cluster = cluster
        self.nightly = nightly

    @property
    def pipelines(self) -> tuple[ParsedBuildkitePipeline, ...]:
        return tuple(
            pipeline
            for pipeline in (self.main, self.cluster, self.nightly)
            if pipeline is not None
        )

    @property
    def cluster_sources(self) -> tuple[ParsedBuildkitePipeline, ...]:
        if self.cluster is not None:
            return (self.cluster,)
        return (self.main,)

    @property
    def nightly_sources(self) -> tuple[ParsedBuildkitePipeline, ...]:
        if self.nightly is not None:
            return (self.nightly,)
        return (self.main,)

    @property
    def combined_steps(self) -> tuple[dict, ...]:
        steps: list[dict] = []
        for pipeline in self.pipelines:
            steps.extend(_flatten_steps(pipeline.get("steps", [])))
        return tuple(steps)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_pipeline(path: Path, *, required: bool = False) -> ParsedBuildkitePipeline | None:
    if not path.exists():
        if required:
            raise AssertionError(f"Buildkite pipeline file must exist: {path}")
        return None

    with path.open(encoding="utf-8") as pipeline_file:
        pipeline = yaml.safe_load(pipeline_file)

    assert isinstance(pipeline, dict), f"{path} must parse as a YAML mapping"
    return ParsedBuildkitePipeline(path, pipeline)


def _flatten_steps(steps: object) -> list[dict]:
    if not isinstance(steps, list):
        return []

    flattened: list[dict] = []
    for step in steps:
        if isinstance(step, dict):
            flattened.append(step)
            flattened.extend(_flatten_steps(step.get("steps")))
    return flattened


@pytest.fixture(scope="session")
def buildkite_pipeline() -> dict:
    pipeline_path = _repo_root() / ".buildkite" / "pipeline.yml"

    pipeline = _load_pipeline(pipeline_path, required=True)
    assert pipeline is not None
    return pipeline


@pytest.fixture(scope="session")
def buildkite_pipeline_family() -> BuildkitePipelineFamily:
    repo_root = _repo_root()
    main = _load_pipeline(repo_root / ".buildkite" / "pipeline.yml", required=True)
    assert main is not None
    return BuildkitePipelineFamily(
        main=main,
        cluster=_load_pipeline(repo_root / ".buildkite" / "pipeline-cluster.yml"),
        nightly=_load_pipeline(repo_root / ".buildkite" / "pipeline-nightly.yml"),
    )


@pytest.fixture(scope="session")
def required_cluster_runtime_validators() -> tuple[str, ...]:
    repo_root = _repo_root()
    validators = list(REQUIRED_CLUSTER_RUNTIME_VALIDATORS)
    image_registry_validator = "infra/tests/validate_image_registry_local.sh"
    if (repo_root / image_registry_validator).exists():
        validators.append(image_registry_validator)
    return tuple(validators)
