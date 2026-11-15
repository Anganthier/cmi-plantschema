"""Shared Test-Fixtures: Fixture-Pfade + Schema-Lade-Helfer."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantschema.io import load_schema

FIXTURES = Path(__file__).parent / "fixtures"


def fx(name: str) -> Path:
    """Fixture-Pfad: minimal / invalid / colliding / rich / rich-groups."""
    return {
        "minimal": FIXTURES / "minimal" / "installation.yaml",
        "invalid": FIXTURES / "invalid" / "bad-refs.yaml",
        "invalid-double-membership": FIXTURES / "invalid" / "double-membership.yaml",
        "colliding": FIXTURES / "colliding" / "collide.yaml",
        "colliding-text-box": FIXTURES / "colliding" / "text-box.yaml",
        "colliding-symbol-text": FIXTURES / "colliding" / "symbol-text.yaml",
        "colliding-group-box": FIXTURES / "colliding" / "group-box.yaml",
        "rich": FIXTURES / "rich" / "installation.yaml",
        "rich-groups": FIXTURES / "rich-groups.yaml",
    }[name]


@pytest.fixture()
def minimal_schema():
    return load_schema(fx("minimal"))
