"""Lanes (S4-L5b, R-39): Leitungs-Boxen = reservierte Routing-Korridore.

Geometrie-Kanon (deterministisch, ganzzahlig):
- Lane-Box: `at` = (x, y) obere linke Ecke, `size` = (w, h).
- Achse = längere Box-Seite: `w >= h` → horizontal, sonst vertikal.
- Spur (Track) der i-ten Pipe (0-basiert, Reihenfolge = `lane.pipes`):
  horizontal `y_i = y + h/2 − (n−1)/2·S + i·S`, vertikal analog `x_i`
  (zentriert um die Mittellinie, gleichmäßig verteilt; `S` =
  `LANE_SPACING`).
- Enge Box: `(n−1)/2·S > (Quer-Ausdehnung)/2` → `S` halbiert
  (engste mögliche Verteilung, deterministisch, kein Crash) +
  Lane-Fallback-Warnung (R-33-Stil, Exit bleibt 0).
- Degenerierter Fall: beide Ports liegen auf derselben Koordinate
  entlang der Lane-Achse (horizontal: gleiches x, vertikal: gleiches
  y) → kein Lauf entlang der Lane möglich (die Lane-Route würde in
  sich zurücklaufen) → R-37/Manhattan-Fallback (`route.route_groups`).
  Kreuzt der Fallback die Box (inkl. Kanten-Berührung) → ok; sonst
  Lane-Fallback-Warnung statt LANE-PIPE-Gate-Treffer.

Lanes sind KEINE Gruppen: keine Mitglieder, keine Box-Gates der
Gruppen-Familie; Komponenten dürfen in Lane-Boxen liegen.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Lane, Point, Schema
from .symbols import is_known_type, port_offset

__all__ = [
    "LANE_SPACING",
    "LANE_TOUCH_TOL",
    "LaneSlot",
    "LaneWarning",
    "collect_lane_warnings",
    "lane_assignments",
    "lane_axis",
    "lane_exempt_ids",
    "lane_box",
    "lane_spacing",
    "lane_tracks",
    "segment_in_box",
    "route_in_box",
]

#: Abstand benachbarter Lane-Spuren (px, R-39).
LANE_SPACING: int = 10

#: Kanten-Toleranz des LANE-PIPE-Gates (px): Berührung = innerhalb.
LANE_TOUCH_TOL: float = 2.0

LaneBox = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class LaneSlot:
    """Lane-Zuordnung einer Pipe (Ergebnis von `lane_assignments`)."""

    lane_index: int
    lane_id: str
    axis: str  # "h" | "v"
    track: int  # y (horizontal) bzw. x (vertikal) der Spur
    box: LaneBox
    degenerate: bool  # True → R-37/Manhattan-Fallback


@dataclass(frozen=True, slots=True)
class LaneWarning:
    """Lane-Fallback-Warnung (R-33-Stil: kein Gate-Fehler, Exit 0)."""

    elem_id: str  # "lane-<id>"
    pipe_id: str | None  # None = Lane-weite Warnung (enge Box)
    note: str

    def line(self) -> str:
        who = f" @ pipe-{self.pipe_id}" if self.pipe_id else ""
        return f"LANE-FALLBACK  [{self.elem_id}]{who} — {self.note}"


def _valid(lane: Lane) -> bool:
    return (
        lane.at is not None and lane.size is not None
        and lane.size[0] > 0 and lane.size[1] > 0
    )


def lane_box(lane: Lane) -> LaneBox:
    """AABB `(x0, y0, x1, y1)` der Lane-Box (float)."""
    assert lane.at is not None and lane.size is not None
    x, y = lane.at
    return (float(x), float(y), float(x + lane.size[0]), float(y + lane.size[1]))


def lane_axis(lane: Lane) -> str:
    """`"h"` (w >= h) oder `"v"` (w < h) — längere Box-Seite."""
    assert lane.size is not None
    return "h" if lane.size[0] >= lane.size[1] else "v"


def lane_spacing(lane: Lane) -> tuple[float, bool]:
    """(Spurabstand, eng?) — `LANE_SPACING` bzw. halbiert, wenn die
    Pipes nicht in die Quer-Ausdehnung passen (R-39)."""
    assert lane.size is not None
    n = len(lane.pipes)
    cross = lane.size[1] if lane_axis(lane) == "h" else lane.size[0]
    if (n - 1) / 2 * LANE_SPACING > cross / 2:
        return LANE_SPACING / 2, True
    return float(LANE_SPACING), False


def _round(v: float) -> int:
    """Deterministisch ganzzahlig (Python-`round` = half-to-even)."""
    return int(round(v))


def lane_tracks(lane: Lane) -> list[int]:
    """Spur-Koordinaten je Pipe (Reihenfolge = `lane.pipes`)."""
    assert lane.at is not None and lane.size is not None
    n = len(lane.pipes)
    s, _ = lane_spacing(lane)
    if lane_axis(lane) == "h":
        center = lane.at[1] + lane.size[1] / 2
    else:
        center = lane.at[0] + lane.size[0] / 2
    return [_round(center - (n - 1) / 2 * s + i * s) for i in range(n)]


def _port_pos(schema: Schema, comp_id: str, port: str) -> Point | None:
    for c in schema.components:
        if c.id == comp_id:
            if c.at is None or not is_known_type(c.type):
                return None
            try:
                geo = port_offset(c.type, port)
            except KeyError:
                return None
            return (c.at[0] + geo.dx, c.at[1] + geo.dy)
    return None


def lane_assignments(schema: Schema) -> dict[str, LaneSlot]:
    """Pipe-ID → `LaneSlot` (defensiv: ungültige Lanes / unbekannte
    Pipes werden übersprungen; bei Doppel-Zuordnung gewinnt die erste
    Lane — Validierungs-Problem `lane-pipe-duplicate`)."""
    pipes = {p.id: p for p in schema.pipes}
    out: dict[str, LaneSlot] = {}
    for li, lane in enumerate(schema.lanes):
        if not _valid(lane):
            continue
        axis = lane_axis(lane)
        box = lane_box(lane)
        for pid, track in zip(lane.pipes, lane_tracks(lane), strict=True):
            p = pipes.get(pid)
            if p is None or pid in out:
                continue
            fp = _port_pos(schema, p.from_.comp, p.from_.port)
            tp = _port_pos(schema, p.to.comp, p.to.port)
            degenerate = False
            if fp is not None and tp is not None:
                k = 0 if axis == "h" else 1
                degenerate = fp[k] == tp[k]
            out[pid] = LaneSlot(li, lane.id, axis, track, box, degenerate)
    return out


def lane_exempt_ids(schema: Schema) -> frozenset[str]:
    """Degenerierte Lane-Pipes OHNE `via` (R-37-Fallback): vom
    LANE-PIPE-Gate ausgenommen (stattdessen ggf. Lane-Warnung)."""
    via = {p.id for p in schema.pipes if p.via}
    return frozenset(
        pid for pid, slot in lane_assignments(schema).items()
        if slot.degenerate and pid not in via
    )


def segment_in_box(
    p1: Point, p2: Point, box: LaneBox, tol: float = LANE_TOUCH_TOL,
) -> bool:
    """Orthogonal-Segment liegt (teilweise) in der Box (geschlossen,
    um `tol` px erweitert: Kanten-Berührung zählt als innerhalb)."""
    x0, y0, x1, y1 = box[0] - tol, box[1] - tol, box[2] + tol, box[3] + tol
    lo_x, hi_x = min(p1[0], p2[0]), max(p1[0], p2[0])
    lo_y, hi_y = min(p1[1], p2[1]), max(p1[1], p2[1])
    return lo_x <= x1 and hi_x >= x0 and lo_y <= y1 and hi_y >= y0


def route_in_box(points: list[Point], box: LaneBox) -> bool:
    """Mindestens EIN Segment der Route in der Box (LANE-PIPE-Prädikat)."""
    if len(points) == 1:
        return segment_in_box(points[0], points[0], box)
    return any(
        segment_in_box(points[i], points[i + 1], box)
        for i in range(len(points) - 1)
    )


def collect_lane_warnings(schema: Schema) -> list[LaneWarning]:
    """Lane-Fallback-Warnungen (R-39, R-33-Stil; Exit bleibt 0).

    Deterministisch: Lane-Reihenfolge, dann `lane.pipes`-Reihenfolge.
    - enge Box (Spurabstand halbiert) → eine Warnung je Lane;
    - degenerierte Pipe ohne `via`, deren Fallback-Route die Box NICHT
      berührt → eine Warnung je Pipe (statt LANE-PIPE-Gate).
    """
    if not schema.lanes:
        return []
    from .route import schema_routes_by_id

    routes = schema_routes_by_id(schema)
    slots = lane_assignments(schema)
    pipes = {p.id: p for p in schema.pipes}
    out: list[LaneWarning] = []
    for li, lane in enumerate(schema.lanes):
        if not _valid(lane):
            continue
        s, tight = lane_spacing(lane)
        if tight:
            out.append(LaneWarning(
                f"lane-{lane.id}", None,
                f"{len(lane.pipes)} Pipes passen nicht in die Box "
                f"(size={lane.size!r}) → Spurabstand {s:g} px statt "
                f"{LANE_SPACING} px (R-39)",
            ))
        for pid in lane.pipes:
            slot = slots.get(pid)
            p = pipes.get(pid)
            if slot is None or slot.lane_index != li or p is None:
                continue
            if p.via or not slot.degenerate:
                continue
            pts = routes.get(pid)
            if pts is not None and not route_in_box(pts, slot.box):
                out.append(LaneWarning(
                    f"lane-{lane.id}", pid,
                    "Ports ohne Lauf entlang der Lane-Achse → R-37-"
                    "Fallback-Route kreuzt die Lane-Box nicht (R-39)",
                ))
    return out
