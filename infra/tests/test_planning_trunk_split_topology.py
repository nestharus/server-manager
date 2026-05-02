from __future__ import annotations

import re
from pathlib import Path


TRUNK_ROOT = Path(__file__).resolve().parents[2]

ROOT_PLANNING_DIR_NAMES = (
    "proposals",
    "research",
    "risk",
    "plans",
    "prototyping",
    "product-strategy",
    "docs",
    ".pipeline",
)
ROOT_PLANNING_FILE_NAMES = ("DECISIONS" + ".md", "NOTES" + ".md")
OLD_STATUS_REL = "docs" + "/infra-e2e-status.md"
NEW_STATUS_REL = "infra/tests/e2e/status.md"
REPO_DOCS_PREFIX = "${REPO_ROOT}/" + "docs" + "/"
PITCH_DECK_RENDERER_REL = "scripts/render-pitch-deck.py"
PITCH_DECK_PDF_EXCLUDE = "product-strategy" + "/*.pdf"
DEPLOYMENT_SUBSTRATE_REL = "docs" + "/deployment-substrate.md"
PLANNING_DECISIONS_REL = "../planning/" + ROOT_PLANNING_FILE_NAMES[0]
PLANNING_DEPLOYMENT_REL = "../planning/" + DEPLOYMENT_SUBSTRATE_REL

BULK_SCAN_DIRS = (
    ("infra", "tests"),
    ("services", "api", "tests"),
    ("tests",),
)
BULK_SCAN_SUFFIXES = {".py", ".sh", ".json", ".yml", ".yaml"}
PLANNING_PATH_PATTERN = re.compile(
    r"(?<![\w./-])(proposals|research|risk|plans|prototyping|product-strategy|docs)/"
)
DECISION_LOG_PATTERN = re.compile(r"(?<![\w./-])(DECISIONS\.md|NOTES\.md)\b")


def _assert_trunk_root(repo_root: Path) -> Path:
    assert repo_root == TRUNK_ROOT, (
        f"path: {Path(__file__).relative_to(TRUNK_ROOT)}; "
        f"offending content: repo_root fixture resolved {repo_root}; "
        f"contract requires trunk root to resolve from this test file location as {TRUNK_ROOT}"
    )
    return TRUNK_ROOT


def _rel(path: Path) -> str:
    return path.relative_to(TRUNK_ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return _read(path).splitlines()


def _iter_bulk_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for parts in BULK_SCAN_DIRS:
        base = root.joinpath(*parts)
        if not base.exists():
            continue
        files.extend(
            path
            for path in base.rglob("*")
            if path.is_file() and path.suffix in BULK_SCAN_SUFFIXES
        )
    return sorted(files)


def _already_prefixed_with_planning(line: str, match_start: int) -> bool:
    return line[max(0, match_start - len("planning/")) : match_start] == "planning/"


def test_trunk_root_contains_no_planning_only_paths(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    findings: list[str] = []

    for name in ROOT_PLANNING_DIR_NAMES:
        path = root / name
        if path.exists():
            kind = "directory" if path.is_dir() else "file"
            findings.append(
                f"{_rel(path)}: offending content: exists as {kind}; "
                f"contract requires no trunk-root {name}/ planning path after INIT-141"
            )

    for name in ROOT_PLANNING_FILE_NAMES:
        path = root / name
        if path.exists():
            findings.append(
                f"{_rel(path)}: offending content: file exists; "
                f"contract requires {name} to be absent from trunk root after INIT-141"
            )

    assert findings == [], "planning-only trunk-root paths remain:\n" + "\n".join(findings)


def test_trunk_root_contains_no_agents_md(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / "AGENTS.md"

    assert not path.exists(), (
        f"path: {_rel(path)}; offending content: file exists; "
        "contract requires trunk root to contain no AGENTS.md after INIT-141"
    )


def test_trunk_root_contains_no_pitch_deck_renderer(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / PITCH_DECK_RENDERER_REL

    assert not path.exists(), (
        f"path: {_rel(path)}; offending content: file exists; "
        f"contract requires {PITCH_DECK_RENDERER_REL} to be absent from trunk after INIT-141"
    )


def test_e2e_status_document_lives_under_infra_tests(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    new_path = root / NEW_STATUS_REL
    old_path = root / OLD_STATUS_REL
    findings: list[str] = []

    if not new_path.is_file():
        findings.append(
            f"{NEW_STATUS_REL}: offending content: file is missing; "
            f"contract requires trunk-local e2e status artifact at {NEW_STATUS_REL}"
        )
    if old_path.exists():
        findings.append(
            f"{OLD_STATUS_REL}: offending content: path exists; "
            f"contract requires previous e2e status path to be removed from trunk"
        )

    assert findings == [], "e2e status document topology is wrong:\n" + "\n".join(findings)


def test_run_fullstack_status_path_points_to_infra_tests(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / "infra/tests/e2e/run-fullstack.sh"
    text = _read(path)
    findings: list[str] = []

    if REPO_DOCS_PREFIX in text:
        findings.append(
            f"{_rel(path)}: offending content: {REPO_DOCS_PREFIX}; "
            f"contract requires run-fullstack to stop writing e2e status under {OLD_STATUS_REL}"
        )
    required = "${REPO_ROOT}/" + NEW_STATUS_REL
    if required not in text:
        findings.append(
            f"{_rel(path)}: offending content: missing {required}; "
            f"contract requires DOC_PATH to resolve to {required}"
        )

    assert findings == [], "run-fullstack e2e status path is wrong:\n" + "\n".join(findings)


def test_buildkite_e2e_artifact_path_points_to_infra_tests(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / ".buildkite/e2e-fullstack.yml"
    text = _read(path)
    findings: list[str] = []

    if NEW_STATUS_REL not in text:
        findings.append(
            f"{_rel(path)}: offending content: missing {NEW_STATUS_REL}; "
            f"contract requires Buildkite to upload {NEW_STATUS_REL}"
        )
    if OLD_STATUS_REL in text:
        findings.append(
            f"{_rel(path)}: offending content: {OLD_STATUS_REL}; "
            f"contract requires no Buildkite reference to the previous e2e status path"
        )

    assert findings == [], "Buildkite e2e artifact path is wrong:\n" + "\n".join(findings)


def test_e2e_readme_documents_infra_tests_status_path(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / "infra/tests/e2e/README.md"
    text = _read(path)
    findings: list[str] = []

    if NEW_STATUS_REL not in text:
        findings.append(
            f"{_rel(path)}: offending content: missing {NEW_STATUS_REL}; "
            f"contract requires README prose to reference {NEW_STATUS_REL}"
        )
    if OLD_STATUS_REL in text:
        findings.append(
            f"{_rel(path)}: offending content: {OLD_STATUS_REL}; "
            f"contract requires README prose to drop the previous e2e status path"
        )

    assert findings == [], "e2e README status path is wrong:\n" + "\n".join(findings)


def test_dockerignore_does_not_exclude_planning_pitch_deck_output(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / ".dockerignore"
    findings = [
        f"{_rel(path)}:{line_number}:{line}; "
        f"contract requires .dockerignore to omit {PITCH_DECK_PDF_EXCLUDE}"
        for line_number, line in enumerate(_lines(path), start=1)
        if line.strip() == PITCH_DECK_PDF_EXCLUDE
    ]

    assert findings == [], "planning pitch-deck output is still excluded:\n" + "\n".join(findings)


def test_infra_readme_links_resolve_to_sibling_planning_repo(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    path = root / "infra/README.md"
    text = _read(path)
    findings: list[str] = []

    if PLANNING_DECISIONS_REL not in text:
        findings.append(
            f"{_rel(path)}: offending content: missing {PLANNING_DECISIONS_REL}; "
            f"contract requires the decision log link to resolve to sibling planning repo"
        )
    if PLANNING_DEPLOYMENT_REL not in text:
        findings.append(
            f"{_rel(path)}: offending content: missing {PLANNING_DEPLOYMENT_REL}; "
            f"contract requires deployment substrate link to resolve to sibling planning repo"
        )

    bare_decisions = re.compile(r"(?<!planning/)" + re.escape(ROOT_PLANNING_FILE_NAMES[0]))
    bare_deployment = re.compile(r"(?<!planning/)" + re.escape(DEPLOYMENT_SUBSTRATE_REL))
    for line_number, line in enumerate(text.splitlines(), start=1):
        if bare_decisions.search(line):
            findings.append(
                f"{_rel(path)}:{line_number}:{line}; "
                f"contract requires bare {ROOT_PLANNING_FILE_NAMES[0]} references to become "
                f"{PLANNING_DECISIONS_REL}"
            )
        if bare_deployment.search(line):
            findings.append(
                f"{_rel(path)}:{line_number}:{line}; "
                f"contract requires bare {DEPLOYMENT_SUBSTRATE_REL} references to become "
                f"{PLANNING_DEPLOYMENT_REL}"
            )

    assert findings == [], "infra README planning links are wrong:\n" + "\n".join(findings)


def test_bulk_annotation_planning_paths_are_prefixed(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    findings: list[str] = []

    for path in _iter_bulk_scan_files(root):
        for line_number, line in enumerate(_lines(path), start=1):
            for match in PLANNING_PATH_PATTERN.finditer(line):
                if _already_prefixed_with_planning(line, match.start()):
                    continue
                findings.append(
                    f"{_rel(path)}:{line_number}:{line.strip()}; "
                    "contract requires trunk test annotations and fixture provenance "
                    "to prefix planning-path references with planning/"
                )

    assert findings == [], "bare planning-path annotations remain:\n" + "\n".join(findings)


def test_bulk_annotation_decision_logs_are_prefixed(repo_root: Path) -> None:
    root = _assert_trunk_root(repo_root)
    findings: list[str] = []

    for path in _iter_bulk_scan_files(root):
        for line_number, line in enumerate(_lines(path), start=1):
            for match in DECISION_LOG_PATTERN.finditer(line):
                if _already_prefixed_with_planning(line, match.start()):
                    continue
                findings.append(
                    f"{_rel(path)}:{line_number}:{line.strip()}; "
                    "contract requires trunk test annotations and fixture provenance "
                    "to prefix decision-log references with planning/"
                )

    assert findings == [], "bare decision-log annotations remain:\n" + "\n".join(findings)
