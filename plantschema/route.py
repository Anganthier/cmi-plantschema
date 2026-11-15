"""Route-Stufe: Pipe-Geometrie (Punktesequenz + SVG-`path`-d-String).

Strategie (S1):
- mit `via`: Autor-Route 1:1 — from-Port → via[0] → … → via[-1] → to-Port.
- ohne `via`: orthogonaler Manhattan-Fallback — erst horizontal, dann
  vertikal, einziger Umrisspunkt. Bewusst simpel (S2 verfeinert:
  Kanal-Hinweis/Vermeidungslogik).

Punkte = `list[tuple[int,int]]` (ganzzahlig, deterministisch).
"""

from __future__ import annotations

from .model import Pipe, Point
from .symbols import port_offset

__all__ = ["PipeGeometry", "path_d", "port_position", "route_pipe"]


def port_position(
    comp_type: str,
    comp_at: Point,
    port: str,
) -> Point:
    """Absolut-Position eines Ports = comp.at + Port-Offset (Katalog)."""
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
    """Punktesequenz einer Pipe (Start-, optional via-Punkte, Endpunkt)."""
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


class PipeGeometry:
    """Route + d-String einer Pipe (Emission-Input)."""

    __slots__ = ("id", "points", "d", "kind", "flow")

    def __init__(self, id: str, points: list[Point], kind: str, flow: str | None):
        self.id = id
        self.points = points
        self.d = path_d(points)
        self.kind = kind
        self.flow = flow
