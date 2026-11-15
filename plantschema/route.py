"""Route-Stufe: Pipe-Geometrie (Punktesequenz + SVG-`path`-d-String).

Strategie (S2):
- mit `via`: Autor-Route 1:1 — from-Port → via[0] → … → via[-1] → to-Port.
- ohne `via`: orthogonaler Manhattan-Fallback — erst horizontal, dann
  vertikal, einziger Umrisspunkt. Bewusst simpel (S3: Kanal-Hinweis/
  Vermeidungslogik, wenn das Kollisions-Gate den Fallback bewertet).
- **Pfeil-Endpunkte (R-29, S2):** kein `marker-end` (Farbe aus
  `context-stroke` nicht portabel) → stattdessen ein kleines Dreieck am
  Pipe-Ende, rotiert nach Letztem-Segment-Vektor, als `<path class="pipe-arrow">`
  mit Fill = Kind-Farbe (`.arrow-vl` …) — deterministisch, kein
  Marker-Referenz-Problem. `arrow_d` liefert den `d`-String; bei
  < 2 Punkten (degenerierte Pipe) = leere Pipe.

Punkte = `list[tuple[int,int]]` (ganzzahlig, deterministisch). Die
Punkte-Liste (`PipeGeometry.points`) ist API für das S3-Kollisions-Gate
(LINE×TEXT braucht die Segmente).
"""

from __future__ import annotations

import math

from .model import Pipe, Point
from .symbols import port_offset

__all__ = ["PipeGeometry", "arrow_d", "path_d", "port_position", "route_pipe"]


def port_position(
    comp_type: str,
    comp_at: Point,
    port: str,
) -> Point:
    """Absolut-Position eines Ports = comp.at + Port-Offset (Katalog, R-30)."""
    dx, dy = port_offset(comp_type, port).dx, port_offset(comp_type, port).dy
    return (comp_at[0] + dx, comp_at[1] + dy)


def path_d(points: list[Point]) -> str:
    """SVG-`d`-String (M/L, absolute Koordinaten, ganzzahlig).

    Konstante Leerzeichen/Format → byte-deterministisch.
    """
    if not points:
        return ""
    head = f"M{points[0][0]},{points[0][1]}"
    tail = " ".join(f"L{x},{y}" for x, y in points[1:])
    return f"{head} {tail}" if tail else head


def route_pipe(
    pipe: Pipe,
    from_pos: Point,
    to_pos: Point,
) -> list[Point]:
    """Punktesequenz einer Pipe (Start-, optional via-Punkte, Endpunkt).

    Die Liste ist stabile API für das S3-Kollisions-Gate (Segmente).
    """
    pts: list[Point] = [from_pos]
    if pipe.via:
        pts.extend(pipe.via)
    else:
        # Manhattan-Fallback: horizontal-dann-vertikal, 1 Umrisspunkt.
        if from_pos[0] != to_pos[0] and from_pos[1] != to_pos[1]:
            pts.append((to_pos[0], from_pos[1]))
    pts.append(to_pos)
    return _dedup(pts)


def _dedup(points: list[Point]) -> list[Point]:
    """Konsekutive Duplikate entfernen (doppelter Umriss-Keil wird sauber)."""
    out: list[Point] = []
    for p in points:
        if not out or p != out[-1]:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Pfeil-Endpunkte (R-29, S2)
# ---------------------------------------------------------------------------

#: Pfeil-Länge (px) entlang des letzten Segments, Spitze am Pipe-Endpunkt.
ARROW_LEN: int = 10
#: Pfeil-Breite (px), ± halb im Lot zum Vektor.
ARROW_HALF_W: int = 4.0


def arrow_d(points: list[Point]) -> str:
    """`d`-String des Pfeil-Endpunkts (kleines Dreieck am Pipe-Ende).

    Rotiert nach Letztem-Segment-Vektor; Spitze exakt am Endpunkt,
    Basis ~ `ARROW_LEN` px davor. Deterministisch (ganzzahlig gerundete
    Koordinaten, fester Format). Bei < 2 Punkten: `""` (kein Pfeil).
    """
    if len(points) < 2:
        return ""
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return ""
    ux, uy = dx / dist, dy / dist
    # Basis-Mitte = Spitze − ARROW_LEN·e; Flanken = Basis-Mitte ± half_w·⊥.
    bx, by = x2 - ARROW_LEN * ux, y2 - ARROW_LEN * uy
    px, py = -uy, ux
    f1x, f1y = bx + ARROW_HALF_W * px, by + ARROW_HALF_W * py
    f2x, f2y = bx - ARROW_HALF_W * px, by - ARROW_HALF_W * py
    return (
        f"M{x2},{y2} L{f1x:.1f},{f1y:.1f} L{f2x:.1f},{f2y:.1f} Z"
    )


class PipeGeometry:
    """Route + d-String einer Pipe (Emission-Input).

    `points` = Punktesequenz (S3-Gate-Input: LINE×TEXT-Segmente);
    `d` = SVG-`d`-String; `kind`/`flow` = Emissions-Hooks.
    """

    __slots__ = ("id", "points", "d", "kind", "flow")

    def __init__(self, id: str, points: list[Point], kind: str, flow: str | None):
        self.id = id
        self.points = points
        self.d = path_d(points)
        self.kind = kind
        self.flow = flow
