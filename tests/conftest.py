"""Shared Test-Fixtures: Fixture-Pfade + Schema-Lade-Helfer."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantschema.io import load_schema

FIXTURES = Path(__file__).parent / "fixtures"


def fx(name: str) -> Path:
    """Fixture-Pfad: minimal / invalid / colliding."""
    return {
        "minimal": FIXTURES / "minimal" / "installation.yaml",
        "invalid": FIXTURES / "invalid" / "bad-refs.yaml",
        "colliding": FIXTURES / "colliding" / "collide.yaml",
    }[name]


@pytest.fixture()
def minimal_schema():
    return load_schema(fx("minimal"))
