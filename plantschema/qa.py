"""QA-Stufe: Kollisions-Detektion (S1-Minimum, harte Gate-Logik).

S1 prüft (cmi-`svg_layout_check.py`-Kanon, Bounding-Box-Heuristik):
- TEXT×TEXT: zwei Texte (Labels/Readout-Texte) überlappen sich.
- LINE×TEXT: ein Pipe-Pfad-Segment läuft durch einen Text.

Breitenschätzung: `width ≈ font_size * 0.52 * len(text)` (system-
gemischt, cmi-Kanon). Höhe ≈ `font_size * 1.2`.

S3 ergänzt: TEXT×Box-Kante, USE×TEXT, besseres Report-Format.
Ergebnis: `list[Collision]` (Typ, Element-A, Element-B, Koordinaten).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .route import PipeGeometry

__all__ = [
    "HEIGHT_FACTOR",
    "WIDTH_FACTOR",
    "Collision",
    "TextElem",
    "estimate_width",
    "detect_collisions",
]

#: cmi-Kanon-Faktoren (system-ui, gemischte Schrift).
WIDTH_FACTOR: float = 0.52
HEIGHT_FACTOR: float = 1.2

#: Sampling-Abstand für Line×Text (px, cmi-`sample_segment`-Kanon).
_SAMPLE_STEP: float = 5.0


@dataclass(frozen=True, slots=True)
class TextElem:
    """Ein abgeprüfter Text (Label oder Readout-Label)."""

    elem_id: str  # z. B. "lbl-zone" / "readout-a6"
    text: str
    font_size: int
    x: int
    y: int
    anchor: str = "start"  # "start" | "middle" | "end"


@dataclass(frozen=True, slots=True)
class Collision:
    """Eine erkannte Kollision (Gate-Report-Zeile)."""

    kind: str  # "text-text" | "line-text"
    elem_a: str
    elem_b: str
    x: int
    y: int
    note: str

    def line(self) -> str:
        return f"{self.kind.upper()}  [{self.elem_a}] × [{self.elem_b}] " \
            f"@ ({self.x},{self.y}) — {self.note}"


def estimate_width(text: str, font_size: int) -> float:
    """cmi-Kanon-Heuristik: width ≈ font_size * 0.52 * len(text)."""
    return font_size * WIDTH_FACTOR * len(text)


def _bbox(t: TextElem) -> tuple[float, float, float, float]:
    w = estimate_width(t.text, t.font_size)
    if t.anchor == "middle":
        x0, x1 = t.x - w / 2, t.x + w / 2
    elif t.anchor == "end":
        x0, x1 = t.x - w, t.x
    else:
        x0, x1 = t.x, t.x + w
    # Baseline-basiert: Oberkante ≈ y - 0.85·fs, Unterkante ≈ y + 0.25·fs.
    y0, y1 = t.y - 0.85 * t.font_size, t.y + 0.25 * t.font_size
    return (x0, y0, x1, y1)


def _intersects(a: tuple[float, float, float, float],
                b: tuple[float, float, float, float],
                pad: float = 0.0) -> bool:
    return not (a[0] - pad >= b[2] or b[0] - pad >= a[2]
                or a[1] - pad >= b[3] or b[1] - pad >= a[3])


def _sample_segment(p1: tuple[int, int], p2: tuple[int, int]) -> list[tuple[float, float]]:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return [p1]
    n = max(1, int(dist / _SAMPLE_STEP))
    return [(p1[0] + dx * i / n, p1[1] + dy * i / n) for i in range(n + 1)]


def detect_collisions(
    texts: Sequence[TextElem],
    pipes: Sequence[PipeGeometry],
) -> list[Collision]:
    """Alle S1-Kollisionen (deterministisch: Eingabe-Reihenfolge)."""
    out: list[Collision] = []
    boxes = [(t, _bbox(t)) for t in texts if t.text]

    # 1) TEXT×TEXT (nur echte Überdeckung, nicht nur 1px-Berührung).
    for i in range(len(boxes)):
        a, ba = boxes[i]
        for j in range(i + 1, len(boxes)):
            b, bb = boxes[j]
            if _intersects(ba, bb, pad=-2.0):
                out.append(Collision(
                    "text-text",
                    a.elem_id, b.elem_id,
                    int(round(ba[0])), int(round(ba[1])),
                    f"Bounding-Boxen überlappen ({a.text!r} / {b.text!r})",
                ))

    # 2) LINE×TEXT (≥2 Sample-Punkte im Text-BBox → Leitung läuft durch).
    for t, tb in boxes:
        for p in pipes:
            hits = 0
            for k in range(len(p.points) - 1):
                for px, py in _sample_segment(p.points[k], p.points[k + 1]):
                    if tb[0] - 1 <= px <= tb[2] + 1 and tb[1] - 1 <= py <= tb[3] + 1:
                        hits += 1
            if hits >= 2:
                out.append(Collision(
                    "line-text",
                    f"pipe-{p.id}", t.elem_id,
                    int(round(tb[0])), int(round(tb[1])),
                    f"Leitung {p.id!r} (kind={p.kind}) schneidet Text {t.text!r}",
                ))
    return out
