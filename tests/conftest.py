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
        # S4-L5a (R-38): Nested-Groups-Negativ-Fixtures.
        "invalid-group-kind-shape": FIXTURES / "invalid" / "group-kind-shape.yaml",
        "invalid-group-include-ref": FIXTURES / "invalid" / "group-include-ref.yaml",
        "invalid-group-include-composite":
            FIXTURES / "invalid" / "group-include-composite.yaml",
        "colliding-group-containment":
            FIXTURES / "colliding" / "group-containment.yaml",
        "colliding-group-box-venn-illegal":
            FIXTURES / "colliding" / "group-box-venn-illegal.yaml",
        "ladder-hier-01": LADDER / "L07-hier-01.yaml",
        "ladder-hier-02": LADDER / "L08-hier-02.yaml",
        "ladder-hier-03": LADDER / "L09-hier-03.yaml",
        # S4-L5b (R-39/R-40): Lanes + Junction.
        "invalid-lane-pipe-ref": FIXTURES / "invalid" / "lane-pipe-ref.yaml",
        "invalid-lane-pipe-duplicate":
            FIXTURES / "invalid" / "lane-pipe-duplicate.yaml",
        "colliding-lane-box": FIXTURES / "colliding" / "lane-box.yaml",
        "colliding-lane-pipe-no-cross":
            FIXTURES / "colliding" / "lane-pipe-no-cross.yaml",
        "ladder-lane-01": LADDER / "L10-lane-01.yaml",
        "ladder-lane-02": LADDER / "L11-lane-02.yaml",
        "ladder-lane-03": LADDER / "L12-lane-03.yaml",
        # S4-L5c: hidden_kinds.
        "invalid-hidden-pipe-in-lane":
            FIXTURES / "invalid" / "hidden-pipe-in-lane.yaml",
        "ladder-hidden-01": LADDER / "L13-hidden-01.yaml",
    }[name]


@pytest.fixture()
def minimal_schema():
    return load_schema(fx("minimal"))
