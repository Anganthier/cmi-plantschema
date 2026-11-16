"""Shared Test-Fixtures: Fixture-Pfade + Schema-Lade-Helfer."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantschema.io import load_schema

FIXTURES = Path(__file__).parent / "fixtures"

#: S4-L4: Layout-Test-Ladegerade (synthetische Stufen L00 … L06 +
#: getrennte Negativ-Stufen unter `ladder/negative/`).
LADDER = FIXTURES / "ladder"


def ladder_levels() -> list[Path]:
    """Alle positiven Ladder-Stufen (`ladder/L*.yaml`), sortiert L00 → Lnn."""
    return sorted(LADDER.glob("L*.yaml"))


def ladder_negatives() -> list[Path]:
    """Alle Ladder-Negativ-Stufen (`ladder/negative/*.yaml`), sortiert."""
    return sorted((LADDER / "negative").glob("*.yaml"))


def fx(name: str) -> Path:
    """Fixture-Pfad: minimal / invalid / colliding / rich / rich-groups."""
    return {
        "minimal": FIXTURES / "minimal" / "installation.yaml",
        "invalid": FIXTURES / "invalid" / "bad-refs.yaml",
        "invalid-double-membership": FIXTURES / "invalid" / "double-membership.yaml",
        "invalid-placement-missing": FIXTURES / "invalid" / "placement-missing.yaml",
        "colliding": FIXTURES / "colliding" / "collide.yaml",
        "colliding-text-box": FIXTURES / "colliding" / "text-box.yaml",
        "colliding-symbol-text": FIXTURES / "colliding" / "symbol-text.yaml",
        "colliding-group-box": FIXTURES / "colliding" / "group-box.yaml",
        "colliding-component-outside-group-box":
            FIXTURES / "colliding" / "component-outside-group-box.yaml",
        "rich": FIXTURES / "rich" / "installation.yaml",
        "rich-groups": FIXTURES / "rich-groups.yaml",
        "rich-groups-layout": FIXTURES / "rich-groups-layout.yaml",
        "rich-groups-routing": FIXTURES / "rich-groups-routing.yaml",
        "colliding-component-foreign-group-box":
            FIXTURES / "colliding" / "component-foreign-group-box.yaml",
        "colliding-group-box-label":
            FIXTURES / "colliding" / "group-box-label.yaml",
        "ladder-negative-group-box-overlap":
            LADDER / "negative" / "group-box-overlap.yaml",
    }[name]


@pytest.fixture()
def minimal_schema():
    return load_schema(fx("minimal"))
