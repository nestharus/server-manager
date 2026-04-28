from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "infra/tests/fixtures/gitops/local_flux_contract.yml"
FLUX_ROOT = REPO_ROOT / "gitops/flux"


def _load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def _load_yaml_documents(root: Path) -> list[tuple[Path, dict]]:
    documents: list[tuple[Path, dict]] = []
    for path in sorted(root.rglob("*.y*ml")):
        for document in yaml.safe_load_all(path.read_text()):
            if isinstance(document, dict) and document.get("kind"):
                documents.append((path, document))
    return documents


def _flux_api_group(document: dict) -> str:
    api_version = str(document.get("apiVersion", ""))
    return api_version.split("/", maxsplit=1)[0]


def _metadata(document: dict) -> dict:
    metadata = document.get("metadata")
    assert isinstance(metadata, dict), f"{document.get('kind')} is missing metadata"
    return metadata


def _spec(document: dict) -> dict:
    spec = document.get("spec")
    assert isinstance(spec, dict), f"{document.get('kind')} is missing spec"
    return spec


def _local_flux_kustomizations() -> list[tuple[Path, dict]]:
    return [
        (path, document)
        for path, document in _load_yaml_documents(FLUX_ROOT)
        if document.get("kind") == "Kustomization"
        and _flux_api_group(document) == "kustomize.toolkit.fluxcd.io"
    ]


def test_local_flux_has_one_scoped_root_for_the_approved_path() -> None:
    contract = _load_contract()
    approved = contract["approved_flux_root"]
    kustomizations = _local_flux_kustomizations()

    roots = [
        (path, document)
        for path, document in kustomizations
        if _metadata(document).get("namespace") == approved["namespace"]
    ]

    assert len(roots) == 1, [
        (path.relative_to(REPO_ROOT).as_posix(), _metadata(document).get("name"))
        for path, document in roots
    ]

    path, root = roots[0]
    metadata = _metadata(root)
    spec = _spec(root)

    assert metadata.get("name") == approved["kustomization_name"]
    assert spec.get("path") == approved["path"]
    assert spec.get("path") not in set(contract["forbidden_root_paths"])
    assert spec.get("prune") is True, path.relative_to(REPO_ROOT).as_posix()
    assert spec.get("sourceRef") == {
        "kind": approved["source_kind"],
        "name": approved["source_name"],
    }


def test_local_flux_uses_git_as_the_only_desired_state_source() -> None:
    contract = _load_contract()
    approved = contract["approved_flux_root"]
    documents = _load_yaml_documents(FLUX_ROOT)

    git_repositories = [
        document
        for _path, document in documents
        if document.get("kind") == approved["source_kind"]
        and _flux_api_group(document) == "source.toolkit.fluxcd.io"
    ]
    forbidden_sources = [
        (_path.relative_to(REPO_ROOT).as_posix(), document.get("kind"), _metadata(document).get("name"))
        for _path, document in documents
        if document.get("kind") in set(contract["forbidden_flux_source_kinds"])
        and _flux_api_group(document) == "source.toolkit.fluxcd.io"
    ]

    assert [
        (_metadata(document).get("namespace"), _metadata(document).get("name"))
        for document in git_repositories
    ] == [(approved["namespace"], approved["source_name"])]
    assert forbidden_sources == []


def test_flux_drift_probe_marker_records_the_reconciled_git_revision() -> None:
    contract = _load_contract()
    approved = contract["approved_flux_root"]
    marker_path = REPO_ROOT / approved["marker_path"]

    documents = [
        document
        for document in yaml.safe_load_all(marker_path.read_text())
        if isinstance(document, dict) and document.get("kind")
    ]
    matching_markers = [
        document
        for document in documents
        if document.get("kind") == approved["marker_kind"]
        and _metadata(document).get("name") == approved["marker_name"]
    ]

    assert len(matching_markers) == 1
    marker = matching_markers[0]
    data = marker.get("data")
    assert isinstance(data, dict)
    assert data.get(approved["marker_required_data_key"])
