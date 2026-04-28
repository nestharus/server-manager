from pathlib import Path

import pytest
import yaml


class ParsedBuildkitePipeline(dict):
    def __repr__(self) -> str:
        return "<ParsedBuildkitePipeline .buildkite/pipeline.yml>"


@pytest.fixture(scope="session")
def buildkite_pipeline() -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    pipeline_path = repo_root / ".buildkite" / "pipeline.yml"

    with pipeline_path.open(encoding="utf-8") as pipeline_file:
        pipeline = yaml.safe_load(pipeline_file)

    assert isinstance(pipeline, dict), "Buildkite pipeline must parse as a YAML mapping"
    return ParsedBuildkitePipeline(pipeline)
