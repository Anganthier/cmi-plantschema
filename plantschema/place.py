"""Place-Stufe: Readout-/Label-Positionen.

S1-Regeln (Minimum):
- Readout an Port-Referenz: Port-Position + Offset nach außen in
  Port-Achsenrichtung (default 16 px; Achse aus dem Port-Katalog).
- Readout an {x,y}: Passthrough (exakt die angegebenen Koordinaten).
- Label: exakt `at` (S1 ohne Auto-Slot-Regeln — die kommen in S3;
  `docs/model-reference.md` dokumentiert das explizit).

Größen-Konstanten (Kanonic, S3-DoD übernommen): Wert ≥ 12 px, Label ≥ 11 px.
"""

from __future__ import annotations

from .model import Label, Point, Readout
from .symbols import PortGeometry

__all__ = [
    "PLACE_OUTER",
    "VALUE_FONT_MIN",
    "LABEL_FONT_MIN",
    "readout_position",
]

#: Standard-Abstand eines Readout-Labels außerhalb des Ports (px).
PLACE_OUTER: int = 16

#: Mindest-Fontgrößen (S3-Kanon: Wert ≥ 12 px, Label ≥ 11 px).
VALUE_FONT_MIN: int = 12
LABEL_FONT_MIN: int = 11

#: Emissions-Fontgrößen S1 (≥ den Mindestwerten).
VALUE_FONT: int = 13
LABEL_FONT: int = 11


def _axis_direction(axis: str | None, offset: tuple[int, int]) -> tuple[int, int]:
    """Port-Achse → (dx,dy) Richtung für die Outside-Platzierung.

    `None`/leer = Richtung des Port-Offsets; (0,0)-Offset default: oben.
    """
    if axis in (None, ""):
        dx, dy = offset
        if (dx, dy) == (0, 0):
            return (0, -1)
        return (1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)
    return {
        "up": (0, -1),
        "down": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
    }[axis]


def readout_position(
    readout: Readout,
    comp_at: Point,
    comp_type: str,
) -> Point:
    """Absolut-Position eines Readouts (S1-Regel).

    - x/y-Referenz: exakt (Passthrough).
    - Port-Referenz: Port-Position + PLACE_OUTER in Achsenrichtung.
    """
    if readout.at.is_ref:
        port: PortGeometry = _port_of(comp_type, readout.at.port)  # type: ignore[arg-type]
        port_pos = (comp_at[0] + port.dx, comp_at[1] + port.dy)
        dx, dy = _axis_direction(port.axis, (port.dx, port.dy))
        return (port_pos[0] + PLACE_OUTER * dx, port_pos[1] + PLACE_OUTER * dy)
    assert readout.at.x is not None and readout.at.y is not None
    return (readout.at.x, readout.at.y)


def label_position(label: Label) -> Point:
    """Label-Position: exakt `at` (S1, keine Auto-Slots)."""
    return label.at


def _port_of(comp_type: str, port: str) -> PortGeometry:
    from .symbols import port_offset

    return port_offset(comp_type, port)
