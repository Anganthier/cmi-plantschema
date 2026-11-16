"""Route-Stufe: Pipe-Geometrie (Punktesequenz + SVG-`path`-d-String).

Strategie:
- mit `via`: Autor-Route 1:1 — from-Port → via[0] → … → via[-1] → to-Port.
  **Author-Override: `via` gewinnt immer** (S4-L3, R-37: auch wenn sie
  fremde Gruppen-Boxen kreuzt — keine Detour-Einmischung).
- ohne `via`: orthogonaler Manhattan-Fallback — erst horizontal, dann
  vertikal, einziger Umrisspunkt (S2).
- **Kanal-Regel (S4-L3, R-37, gruppen-bewusst):** ohne `via` +
  inter-Gruppe (from- und to-Ende in VERSCHIEDENEN Gruppen) prüft
  `route_groups` den Fallback-Pfad gegen alle **fremden** Gruppen-Boxen
  (AABB-Interior: ein Orthogonal-Segment „kreuzt" eine Box, wenn es
  deren Inneres schneidet; Tangential entlang einer Kante ≠ Kreuzung).
  Kreuzt das **erste** Fremdkreuzungs-Segment (niedrigster
  Segmente-Index, dann Box-Reihenfolge) eine fremde Box → eindeutiger
  Detour: ein Kanal-Panel (Kanal = Lücken-Linie zwischen den
  betroffenen Boxen) wird eingefügt. Die Box wird über ihre
  **nächstgelegene Kante in Segment-Achsenrichtung** umgangen:
  horizontales Kreuzungs-Segment → horizontale Kanal-Linie 1 px
  außerhalb der nächstgelegenen horizontalen Kante (obere/untere;
  Gleichstand → obere), vertikales Segment analog (linke/rechte;
  Gleichstand → linke). Route: from-Port → senkrecht auf die
  Kanal-Linie → entlang der Linie → senkrecht ab zum to-Port (2
  Detour-Viapunkte, eine eindeutige Route). Die Route wird NICHT
  wiederholt geprüft: kreuzt der Detour selbst eine weitere Box,
  meldet das Kollisions-Gate (Exit 3) — erwartetes Signal, kein
  Backtracking (R-37). Intra-Gruppe (beide Enden in derselben
  Gruppe) bzw. ein nicht-gruppiges Ende → unverändert (kein Detour).
  Deterministisch: keine Random/Zeit/Hash-Heuristik; gleiche Eingabe
  → gleiche Punktesequenz.

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
from collections.abc import Sequence

from .model import Pipe, Point
from .symbols import port_offset

__all__ = [
    "PipeGeometry",
    "arrow_d",
    "manhattan_fallback",
    "path_d",
    "port_position",
    "route_groups",
    "route_pipe",
]

#: Kanal-Offset (R-37): Detour-Linie liegt 1 px außerhalb der Box-Kante
#: (Kanal = Linie zwischen den betroffenen Boxen, kein Kanten-Paint).
CHANNEL_OFFSET: int = 1

#: Gruppen-Box-AABB für Kanal-Checks: `(x0, y0, x1, y1)`, float.
GroupBox = tuple[float, float, float, float]


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
    S4-L3 (R-37): gruppen-bewusstes Routing läuft über `route_groups`
    (via-Override + Kanal-Detour); dieser Einstieg bleibt via-1:1 +
    Manhattan-Fallback (bestehende Tests/API unverändert).
    """
    pts: list[Point] = [from_pos]
    if pipe.via:
        pts.extend(pipe.via)
    else:
        # Manhattan-Fallback: horizontal-dann-vertikal, 1 Umrisspunkt.
        pts.extend(manhattan_fallback(from_pos, to_pos))
    pts.append(to_pos)
    return _dedup(pts)


def manhattan_fallback(from_pos: Point, to_pos: Point) -> list[Point]:
    """Orthogonaler Fallback ohne `via` (S2): erst horizontal, dann
    vertikal, genau 1 Umrisspunkt (oder leer, wenn ausgerichtet)."""
    if from_pos[0] != to_pos[0] and from_pos[1] != to_pos[1]:
        return [(to_pos[0], from_pos[1])]
    return []


def _seg_crosses_box(
    p1: Point, p2: Point, box: GroupBox,
) -> bool:
    """Orthogonal-Segment × Box-INTERIOR (R-37-Kanal-Prädikat).

    Horizontales Segment auf Höhe `y` kreuzt, wenn `y` im Box-Innen-
    band `(y0, y1)` liegt und der x-Intervall die Box x-umspannt
    (streng); vertikal analog. Tangential entlang einer Kante (y =
    Kante bzw. Segment endet auf Box-Intervall-Kante) = keine
    Kreuzung (Pipe rückt an/entlang der Box, läuft nicht durch).
    """
    if p1[1] == p2[1]:  # horizontal auf Höhe y
        lo, hi = min(p1[0], p2[0]), max(p1[0], p2[0])
        return box[1] < p1[1] < box[3] and lo < box[2] and hi > box[0]
    # vertikal auf Linie x
    lo, hi = min(p1[1], p2[1]), max(p1[1], p2[1])
    return box[0] < p1[0] < box[2] and lo < box[3] and hi > box[1]


def _first_foreign_crossing(
    points: list[Point],
    foreign: Sequence[GroupBox],
) -> tuple[int, int] | None:
    """Erstes Fremde-Box-Kreuzungs-Segment des (orthogonalen) Pfads.

    Returns `(seg-index, box-index)` des niedrigsten Segments, das eine
    fremde Box kreuzt (deterministisch: Segment-Reihenfolge, dann
    Box-Reihenfolge); `None` = keine Fremdkreuzung.
    """
    for i in range(len(points) - 1):
        for j, box in enumerate(foreign):
            if _seg_crosses_box(points[i], points[i + 1], box):
                return i, j
    return None


def _channel_detour(
    seg: tuple[Point, Point],
    box: GroupBox,
    from_pos: Point,
    to_pos: Point,
) -> list[Point]:
    """Eindeutiger Kanal-Detour um `box` (R-37, s. Modul-Docstring).

    Nächstgelegene Kante der Box in Segment-Achsenrichtung:
    horizontales Segment → nächste horizontale Kante (Exakt-Tiebreak:
    obere Kante), vertikales Segment → nächste vertikale Kante
    (Exakt-Tiebreak: linke Kante). Detour-Linie = Kante ±
    `CHANNEL_OFFSET` px (außen, d. h. weg vom Box-Interior).
    """
    a, b = seg
    if a[1] == b[1]:  # horizontales Segment: Kanal über/unter der Box
        y = a[1]
        dist_top, dist_bottom = abs(y - box[1]), abs(y - box[3])
        # Exakt-Tiebreak → obere Kante (nächste Kante, ≤-Vergleich).
        lane = int(box[1] - CHANNEL_OFFSET) if dist_top <= dist_bottom \
            else int(box[3] + CHANNEL_OFFSET)
        return [
            from_pos,
            (from_pos[0], lane),
            (to_pos[0], lane),
            to_pos,
        ]
    x = a[0]  # vertikales Segment: Kanal links/rechts der Box
    dist_left, dist_right = abs(x - box[0]), abs(x - box[2])
    # Exakt-Tiebreak → linke Kante (nächste Kante, ≤-Vergleich).
    lane = int(box[0] - CHANNEL_OFFSET) if dist_left <= dist_right \
        else int(box[2] + CHANNEL_OFFSET)
    return [
        from_pos,
        (lane, from_pos[1]),
        (lane, to_pos[1]),
        to_pos,
    ]


def route_groups(
    pipe: Pipe,
    from_pos: Point,
    to_pos: Point,
    foreign_boxes: Sequence[GroupBox] = (),
    use_channel: bool = True,
) -> list[Point]:
    """Punktesequenz mit S4-L3-Gruppen-Bewusstsein (R-37).

    - `via` gesetzt → Autor-Route 1:1 (Override gewinnt immer, auch
      bei Fremdkreuzung: kein Detour, der Router greift nicht ein).
    - ohne `via`, intra-Gruppe oder `use_channel=False` → wie
      `route_pipe` (Manhattan-Fallback).
    - ohne `via`, inter-Gruppe (`foreign_boxes` nicht leer): kreuzt
      der Fallback eine fremde Box-Interior-AABB (Tangential zählt
      nicht) → eindeutiger Kanal-Detour am ersten Fremdkreuzungs-
      Segment (s. `_channel_detour`); sonst Fallback. Deterministisch,
      keine Iteration/Backtracking.

    `foreign_boxes` = AABBs der Gruppen, der WEDER from- noch to-Ende
    angehören (aufrufseitig bereinigt, s. `emit.compute_layout`).
    """
    if pipe.via:
        pts: list[Point] = [from_pos, *pipe.via, to_pos]
    else:
        pts = [from_pos, *manhattan_fallback(from_pos, to_pos), to_pos]
    if pipe.via or not use_channel or not foreign_boxes:
        return _dedup(pts)
    hit = _first_foreign_crossing(pts, foreign_boxes)
    if hit is None:
        return _dedup(pts)
    seg_i, box_i = hit
    return _dedup(_channel_detour(
        (pts[seg_i], pts[seg_i + 1]),
        foreign_boxes[box_i],
        from_pos,
        to_pos,
    ))


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
