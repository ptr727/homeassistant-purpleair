"""Manifest requirement tests."""

import json
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).parents[3]
PACKAGE = "ptr727-aiopurpleair"


def _requirement(lines: list[str]) -> Requirement:
    """Return the aiopurpleair requirement from a list of requirement strings."""
    return next(req for req in map(Requirement, lines) if req.name == PACKAGE)


def test_test_pin_satisfies_manifest_minimum() -> None:
    """The version CI tests must be one the manifest lets HA install.

    The manifest declares a minimum so library releases reach users without an
    integration release, while Dependabot bumps only requirements-test.txt.
    """
    manifest = json.loads(
        (ROOT / "custom_components/purpleair/manifest.json").read_text()
    )
    runtime = _requirement(manifest["requirements"])
    assert not runtime.url
    assert all(spec.operator == ">=" for spec in runtime.specifier)

    test_lines = [
        line.strip()
        for line in (ROOT / "requirements-test.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "-"))
    ]
    tested = _requirement(test_lines)
    (pin,) = [spec.version for spec in tested.specifier if spec.operator == "=="]
    assert runtime.specifier.contains(pin)
