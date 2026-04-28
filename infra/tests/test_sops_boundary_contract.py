import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "infra/tests/fixtures/sops"
LINT_SCRIPT = REPO_ROOT / "infra/scripts/lint-sops-boundary.py"


def _copy_fixture_to_repo_shape(tmp_path: Path, fixture_name: str) -> Path:
    destination = tmp_path / "gitops/bootstrap" / fixture_name
    destination.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURE_ROOT / fixture_name, destination)
    return destination


def _run_sops_boundary_lint(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), str(root)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sops_boundary_lint_rejects_plaintext_secret_leaks(tmp_path: Path) -> None:
    leaked_file = _copy_fixture_to_repo_shape(tmp_path, "plaintext-secret-leak.yaml")

    result = _run_sops_boundary_lint(tmp_path)

    assert result.returncode != 0
    assert leaked_file.name in f"{result.stdout}\n{result.stderr}"


def test_sops_boundary_lint_accepts_sops_encrypted_sentinel(tmp_path: Path) -> None:
    _copy_fixture_to_repo_shape(tmp_path, "sops-encrypted-sentinel.enc.yaml")

    result = _run_sops_boundary_lint(tmp_path)

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
