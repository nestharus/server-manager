import importlib
import types

import pytest


SUBMODULES = (
    "config",
    "db",
    "claim",
    "applications",
    "tickets",
    "chapters",
    "util",
)


def import_daemon():
    return importlib.import_module("daemon")


def test_daemon_package_is_importable():
    module = import_daemon()

    assert isinstance(module, types.ModuleType)
    assert module.__name__ == "daemon"


def test_daemon_package_has_non_empty_docstring():
    module = import_daemon()

    assert isinstance(module.__doc__, str)
    assert module.__doc__.strip()


def test_daemon_docstring_mentions_key_concepts_and_submodules():
    module = import_daemon()
    doc = module.__doc__
    assert doc is not None

    lowered = doc.lower()

    assert "daemon" in lowered
    assert "discord" in lowered
    assert "long-running" in lowered
    assert "discord_cli.py" in doc

    for submodule in SUBMODULES:
        assert submodule in doc


@pytest.mark.parametrize("attr_name", ["__version__", "__all__"])
def test_daemon_package_does_not_define_forbidden_attributes(attr_name):
    module = import_daemon()

    assert not hasattr(module, attr_name)


def test_daemon_package_has_no_public_names():
    module = import_daemon()

    # Submodules that have been imported elsewhere in the test suite
    # appear in the package namespace automatically (Python behavior).
    # Exclude known submodule names — the contract is that __init__.py
    # itself does not define public names.
    public_names = sorted(
        name
        for name in vars(module)
        if not name.startswith("_") and name not in SUBMODULES
    )

    assert public_names == []
