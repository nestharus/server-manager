import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.contracts as contracts_package
import app.contracts.base as contracts_base


def test_contracts_package_exports_are_empty_after_versioned_mixin_removal() -> None:
    assert contracts_package.__all__ == []


def test_contracts_base_exports_are_empty_after_versioned_mixin_removal() -> None:
    assert contracts_base.__all__ == []


def test_versioned_mixin_is_not_present_in_contract_modules() -> None:
    assert not hasattr(contracts_package, "VersionedMixin")
    assert not hasattr(contracts_base, "VersionedMixin")
