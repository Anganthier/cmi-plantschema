"""Place-Stufe: Readout-/Label-Positionen (S3: Auto-Slots, R-32/R-33).

Readout-Regeln (S1/S2, unverändert):
- Readout an Port-Referenz: Port-Position + Offset nach außen in
  Port-Achsenrichtung (default 16 px; Achse aus dem Port-Katalog).
- Readout an {x,y}: Passthrough (exakt die angegebenen Koordinaten).

Label-Regeln (S3, R-32):
- `at` gesetzt → exakte Position (Override, gewinnt immer).
- sonst `comp` (+ optional `port`) → **Auto-Slot**: Slot-Text-Position an
  der Symbol-Kante in einer der 4 Richtungen (up/down/left/right, BBox aus
  `symbols.SYMBOL_BOUNDS`); Text-Offset: up/down = 8 px über/unter
  (anchor=middle), left/right = 16 px links/rechts (anchor end/start,
  Readout-`side`-Kanon).
  **Preference up → right → down → left**; erster Slot mit ≥8 px Abstand
  zu allen Pipe-Segmenten (5-px-Sampling, cmi-Kanon) + ≥8 px zu allen
  anderen Symbol-Bounding-Boxes + ≥4 px zu allen anderen Text-BBs wird
  genommen. `port` verschiebt den Slot entlang der Slot-Kante (Port-
  Offset, begrenzt auf Kante ± 0.5·Textgröße) und erzwingt die Richtung
  des Port-Offsets (Präferenzkette startet dort).
- Alle 4 Slots kollidieren → Position = up-Slot + **Warning**
  (R-33, kein Gate-Fehler; Report-Block „N Warnung(en):", Exit 0).

Komponenten-Labels (`.txt-h`/`.txt-s`, S2 `render_component`):
- up-Slot-Position = 8 px über der Symbol-Oberkante (Baseline-Abstand
  0.85·fs, d. h. Offset = 8 + ⌈0.85·fs⌉ über dem Zentrum); Sub-Text
  14 px darunter. Alle 4 Slots kollidieren → `symbols.LABEL_OFFSET`
  (S2-Default) + Warning.

Größen-Konstanten (S3-Kanon): Wert ≥ 12 px, Label ≥ 11 px
(`VALUE_FONT_MIN`/`LABEL_FONT_MIN`; harte Gate-Prüfung in `qa.py`, R-34).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Label, Point, Readout, Schema
from .symbols import LABEL_OFFSET, component_bounds, port_offset

__all__ = [
    "PLACE_OUTER",
    "VALUE_FONT_MIN",
    "LABEL_FONT_MIN",
    "VALUE_FONT",
    "LABEL_FONT",
    "SLOT_DIR_ORDER",
    "SLOT_DIST",
    "SLOT_TEXT_DIST",
    "TEXT_DIST",
    "SlotWarning",
    "readout_position",
    "slot_positions",
    "resolve_label",
    "label_position",
    "component_label_offset",
    "collect_slot_warnings",
]

#: Standard-Abstand eines Readout-Labels außerhalb des Ports (px).
PLACE_OUTER: int = 16

#: Mindest-Fontgrößen (S3-Kanon: Wert ≥ 12 px, Label ≥ 11 px, R-34).
VALUE_FONT_MIN: int = 12
LABEL_FONT_MIN: int = 11

#: Emissions-Fontgrößen (≥ den Mindestwerten).
VALUE_FONT: int = 13
LABEL_FONT: int = 11

#: Slot-Text-Abstand: `.txt`/`.txt-h`/`.txt-s` (Emissions-Klassen 14/14/12 px).
TXT_FONT: int = 14
TXT_H_FONT: int = 14
TXT_S_FONT: int = 12

#: Slot-Abstand zu Pipes/Symbol-BBoxes (cmi S4N-2-QA-Kanon, R-32).
SLOT_DIST: float = 8.0
#: Slot-Text-Abstand: Text-BBox zu Symbol-Kante / anderen Text-BBs (8 px
#: zu Symbol-Boxen, 4 px zu Text-BBs — R-32).
SLOT_TEXT_DIST: float = 8.0
#: Mindest-Abstand des Slot-Texts zu anderen Text-BBs (R-32).
TEXT_DIST: float = 4.0

#: Slot-Präferenzreihenfolge (R-32): up → right → down → left.
SLOT_DIR_ORDER: tuple[str, ...] = ("up", "right", "down", "left")

#: 5-px-Sampling (cmi `sample_segment`-Kanon).
_SAMPLE_STEP: float = 5.0


@dataclass(frozen=True, slots=True)
class SlotWarning:
    """R-33: alle 4 Slots kollidieren → Fallback-Position + Warning
    (kein Gate-Fehler; Exit bleibt 0)."""

    elem_id: str
    comp_id: str
    direction: str
    x: int
    y: int
    note: str


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


def _direction_name(d: tuple[int, int]) -> str:
    return {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}[d]


def readout_position(
    readout: Readout,
    comp_at: Point,
    comp_type: str,
) -> Point:
    """Absolut-Position eines Readouts (S1-Regel, S3 unverändert).

    - x/y-Referenz: exakt (Passthrough).
    - Port-Referenz: Port-Position + PLACE_OUTER in Achsenrichtung.
    """
    if readout.at.is_ref:
        port = port_offset(comp_type, readout.at.port)  # type: ignore[arg-type]
        port_pos = (comp_at[0] + port.dx, comp_at[1] + port.dy)
        dx, dy = _axis_direction(port.axis, (port.dx, port.dy))
        return (port_pos[0] + PLACE_OUTER * dx, port_pos[1] + PLACE_OUTER * dy)
    assert readout.at.x is not None and readout.at.y is not None
    return (readout.at.x, readout.at.y)


def slot_positions(
    comp_type: str,
    comp_at: Point,
    text_len: int,
    font_size: int = TXT_FONT,
    direction: str = "up",
) -> tuple[int, int]:
    """Slot-Text-Position (S3, R-32) für die Richtung `direction`.

    Slot = Symbol-Kante (SYMBOL_BOUNDS, R-34) entlang der Slot-Achse;
    Text-Offset: up/down = 8 px über/unter der Kante (anchor=middle),
    left/right = 16 px links/rechts (anchor end/start, Readout-`side`-
    Kanon). `font_size`/`text_len` bestimmen die Slot-Breite (nur für
    Port-Versatz-Grenzen relevant, s. `label_position`).
    """
    x0, y0, x1, y1 = component_bounds(comp_type, comp_at)
    if direction == "up":
        return (int(round((x0 + x1) / 2)), int(round(y0)) - SLOT_TEXT_DIST)
    if direction == "down":
        return (int(round((x0 + x1) / 2)), int(round(y1)) + SLOT_TEXT_DIST)
    if direction == "left":
        return (int(round(x0)) - PLACE_OUTER, int(round((y0 + y1) / 2)))
    return (int(round(x1)) + PLACE_OUTER, int(round((y0 + y1) / 2)))


def _text_bbox(
    x: int, y: int, anchor: str, text: str, font_size: int
) -> tuple[float, float, float, float]:
    """Text-BBox (cmi `text_bbox`-Kanon: width ≈ fs·0.52·len; Baseline:
    Oberkante y − 0.85·fs, Unterkante y + 0.25·fs)."""
    w = font_size * 0.52 * len(text)
    if anchor == "middle":
        x0, x1 = x - w / 2, x + w / 2
    elif anchor == "end":
        x0, x1 = x - w, x
    else:
        x0, x1 = x, x + w
    return (x0, y - 0.85 * font_size, x1, y + 0.25 * font_size)


def _sample_segment(
    p1: Point, p2: Point, step: float = _SAMPLE_STEP
) -> list[tuple[float, float]]:
    """Punkte in ≤ `step` px Abständen entlang des Segments (cmi-Kanon)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return [p1]
    n = max(1, int(dist / step))
    return [(p1[0] + dx * i / n, p1[1] + dy * i / n) for i in range(n + 1)]


def _seg_dist_box(
    segments: list[list[Point]], box: tuple[float, float, float, float]
) -> float:
    """Mindest-Abstand (5-px-Sampling) aller Pipe-Segmente zur Box."""

    def dist_point_box(
        px: float, py: float, b: tuple[float, float, float, float]
    ) -> float:
        dx = max(b[0] - px, 0.0, px - b[2])
        dy = max(b[1] - py, 0.0, py - b[3])
        return math.hypot(dx, dy)

    best = math.inf
    for pts in segments:
        for k in range(len(pts) - 1):
            for px, py in _sample_segment(pts[k], pts[k + 1]):
                d = dist_point_box(px, py, box)
                if d < best:
                    best = d
    return best


def _bbox_dist(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Abstand zweier Bounding-Boxen (0 = überlappend/berührend)."""
    dx = max(b[0] - a[2], 0.0, a[0] - b[2])
    dy = max(b[1] - a[3], 0.0, a[1] - b[3])
    return math.hypot(dx, dy)


def _slot_fits(
    slot: tuple[int, int],
    anchor: str,
    text: str,
    font_size: int,
    skip_comp_id: str | None,
    skip_text_prefix: str | None,
    pipe_segments: list[list[Point]],
    other_comp_boxes: dict[str, tuple[float, float, float, float]],
    other_text_boxes: dict[str, tuple[float, float, float, float]],
) -> bool:
    """R-32-Abstandskriterien für einen Slot (Pipes/Symbole ≥8 px, Text ≥4 px).

    `skip_comp_id`: Host-Komponente zählt nicht (Slot liegt an ihrer
    Kante). `skip_text_prefix`: nur bei Komponenten-Label-Auflösung —
    die eigenen `.txt-h`/`.txt-s`-Texte sind *keine* Hürde (der up-Slot
    ist ihre Position); für fremde Labels sind sie eine Hürde.
    """
    box = _text_bbox(*slot, anchor, text, font_size)
    if pipe_segments and _seg_dist_box(pipe_segments, box) < SLOT_DIST:
        return False
    for k, cb in other_comp_boxes.items():
        if k == skip_comp_id:
            continue
        if _bbox_dist(box, cb) < SLOT_DIST:
            return False
    for k, tb in other_text_boxes.items():
        if skip_text_prefix is not None and k.startswith(skip_text_prefix):
            continue
        if _bbox_dist(box, tb) < TEXT_DIST:
            return False
    return True


def _dir_order(forced: str | None) -> tuple[str, ...]:
    """Präferenzreihenfolge (R-32), ggf. rotiert ab Forcierungs-Richtung."""
    if forced is None or forced not in SLOT_DIR_ORDER:
        return SLOT_DIR_ORDER
    i = SLOT_DIR_ORDER.index(forced)
    return SLOT_DIR_ORDER[i:] + SLOT_DIR_ORDER[:i]


def _slot_anchor(direction: str) -> str:
    return {
        "up": "middle",
        "down": "middle",
        "left": "end",
        "right": "start",
    }[direction]


def resolve_label(label: Label, schema: Schema) -> tuple[Point | None, str]:
    """Label-Auflösung (S3, R-32/R-33): Position + `text-anchor`.

    - `at` gesetzt → exakt (Override, gewinnt immer); anchor = `label.anchor`.
    - `comp` gesetzt → Auto-Slot; anchor = Slot-Anker (up/down = middle,
      left/right = end/start); alle 4 kollidieren → up-Position +
      middle (R-33-Fallback, Warning via `collect_slot_warnings`).
    - `comp`-Host unbekannt (Validierungs-Problem `label-comp-ref` liegt
      dann vor) → `(None, label.anchor.value)` (keine Position).
    """
    if label.at is not None:
        return label.at, label.anchor.value
    comps = {c.id: c for c in schema.components}
    comp = comps.get(label.comp or "")
    if comp is None:
        return None, label.anchor.value
    pipe_segments = _all_pipe_segments(schema, comps)
    comp_boxes = {c.id: component_bounds(c.type, c.at) for c in comps.values()}
    text_boxes = _all_text_boxes(schema, comps)

    # Port-Versatz (R-32): Slot-Kante entlang der Slot-Achse um Port-Offset
    # (begrenzt auf Kante ± 0.5·Textgröße); Forcierung = Port-Offset-Achse.
    forced: str | None = None
    shift: tuple[int, int] = (0, 0)
    if label.port is not None:
        try:
            port = port_offset(comp.type, label.port)
        except KeyError:
            port = None
        if port is not None:
            d = _axis_direction(port.axis, (port.dx, port.dy))
            forced = _direction_name(d)
            half = _text_bbox(0, 0, "middle", label.text, TXT_FONT)
            half_w = (half[2] - half[0]) / 2
            half_h = half[3] - half[1]
            if forced in ("up", "down"):
                shift = (int(round(max(-half_w, min(float(port.dx), half_w)))), 0)
            else:
                shift = (0, int(round(max(-half_h, min(float(port.dy), half_h)))))

    for direction in _dir_order(forced):
        x, y = slot_positions(
            comp.type, comp.at, len(label.text), direction=direction
        )
        x += shift[0]
        y += shift[1]
        anchor = _slot_anchor(direction)
        if _slot_fits(
            (x, y), anchor, label.text, TXT_FONT, comp.id, None,
            pipe_segments, comp_boxes, text_boxes,
        ):
            return (x, y), anchor
    # R-33: alle 4 Slots kollidieren → up-Position (Fallback) + Warning.
    x, y = slot_positions(comp.type, comp.at, len(label.text))
    return (x + shift[0], y + shift[1]), "middle"


def label_position(label: Label, schema: Schema) -> Point | None:
    """Position eines Labels (S3, R-32/R-33) — siehe `resolve_label`."""
    return resolve_label(label, schema)[0]


def component_label_offset(
    comp_type: str, comp_at: Point, n_lines: int = 1
) -> int:
    """`.txt-h`-Offset über dem Symbolzentrum (S3, R-32 up-Slot).

    1 Zeile: Baseline = Symbol-Oberkante − SLOT_TEXT_DIST (8 px):
    `offset = round((Zentrum − Oberkante) + 8)`. 2 Zeilen (mit Sub):
    Sub-Baseline 17 px unter der Haupt-Baseline, dessen Unterkante
    (0.25·12 = 3 px) liegt exakt an der Symbol-Oberkante:
    `offset = round((Zentrum − Oberkante) + 20)`. Unknown-Type →
    S1-Platzhalter-Box (±20).
    """
    _, y0, _, _ = component_bounds(comp_type, comp_at)
    half_h = comp_at[1] - int(round(y0))
    return int(round(half_h + (SLOT_TEXT_DIST if n_lines <= 1 else 20.0)))


def collect_slot_warnings(schema: Schema) -> list[SlotWarning]:
    """Alle R-33-Fallbacks (Label-Auto-Slots + Komponenten-Labels).

    Deterministisch: Schema-Reihenfolge, Labels vor Komponenten-Labels;
    Fallback-Richtung ist immer „up" (Preference-Default).
    """
    out: list[SlotWarning] = []
    comps = {c.id: c for c in schema.components}
    pipe_segments = _all_pipe_segments(schema, comps)
    comp_boxes = {c.id: component_bounds(c.type, c.at) for c in comps.values()}
    text_boxes = _all_text_boxes(schema, comps)

    for lbl in schema.labels:
        if lbl.at is not None or lbl.comp is None:
            continue
        comp = comps.get(lbl.comp)
        if comp is None:
            continue
        host = component_bounds(comp.type, comp.at)
        if _all_slots_collide(
            lbl.text, host, comp.id, None,
            pipe_segments, comp_boxes, text_boxes,
        ):
            x, y = slot_positions(comp.type, comp.at, len(lbl.text))
            out.append(SlotWarning(
                f"lbl-{lbl.id}", comp.id, "up", x, y,
                "alle 4 Slots kollidieren → up-Fallback (R-33)",
            ))
    for comp in schema.components:
        if comp.label is None:
            continue
        host = component_bounds(comp.type, comp.at)
        if _all_slots_collide(
            comp.label.text, host, comp.id, f"comp-{comp.id}.",
            pipe_segments, comp_boxes, text_boxes,
        ):
            x, y = slot_positions(comp.type, comp.at, len(comp.label.text))
            out.append(SlotWarning(
                f"comp-{comp.id}.lbl", comp.id, "up", x, y,
                "alle 4 Slots kollidieren → up-Fallback (R-33)",
            ))
    return out


def _all_slots_collide(
    text: str,
    host: tuple[float, float, float, float],
    host_id: str,
    skip_text_prefix: str | None,
    pipe_segments: list[list[Point]],
    comp_boxes: dict[str, tuple[float, float, float, float]],
    text_boxes: dict[str, tuple[float, float, float, float]],
) -> bool:
    """True, wenn alle 4 Slots die R-32-Abstände verletzen (R-33-Fallback).

    `skip_text_prefix`: eigene Komponenten-Texte (`.txt-h`/`.txt-s`)
    zählen bei der eigenen Slot-Evaluation nicht mit (der up-Slot ist
    ihre Position); fremde Labels zählen sie.
    """
    for direction in SLOT_DIR_ORDER:
        x, y = _slot_from_host(host, direction)
        if _slot_fits(
            (x, y),
            _slot_anchor(direction),
            text,
            TXT_FONT,
            host_id,
            skip_text_prefix,
            pipe_segments,
            comp_boxes,
            text_boxes,
        ):
            return False
    return True


def _slot_from_host(
    host: tuple[float, float, float, float], direction: str
) -> tuple[int, int]:
    """Slot-Position aus Host-BBox (für R-33-Evaluation, host-relative)."""
    x0, y0, x1, y1 = host
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if direction == "up":
        return (int(round(cx)), int(round(y0)) - SLOT_TEXT_DIST)
    if direction == "down":
        return (int(round(cx)), int(round(y1)) + SLOT_TEXT_DIST)
    if direction == "left":
        return (int(round(x0)) - PLACE_OUTER, int(round(cy)))
    return (int(round(x1)) + PLACE_OUTER, int(round(cy)))


def _all_pipe_segments(
    schema: Schema, comps: dict[str, object]
) -> list[list[Point]]:
    """Pipe-Punktesequenzen für die Slot-Evaluation (R-32/R-33).

    S4-L4-Fix: gruppen-bewusste Route (`route.schema_routes`, R-37 —
    via-Override + Kanal-Detour) statt des reinen Manhattan-Fallbacks,
    d. h. exakt die Geometrie, die `emit.compute_layout` emittiert und
    das Gate prüft (vorher: Phantom-Segmente des nie gezeichneten
    Fallbacks blockierten Slots → falsche R-33-Warnungen).
    """
    from .route import schema_routes

    _ = comps  # Signatur stabil (Aufrufer übergeben die Komponenten-Map)
    return schema_routes(schema)


def _all_text_boxes(
    schema: Schema, comps: dict[str, object]
) -> dict[str, tuple[float, float, float, float]]:
    """Alle festen Text-BBs (Labels mit `at`, Readout-Texte,
    Komponenten-Labels `.txt-h`/`.txt-s`) — Slot-Eval-Input.

    Auto-Slot-Labels (ohne `at`) werden NICHT vorbezählt (sie werden
    selbst evaluiert; deren Endposition ist vorher nicht bekannt).
    """
    from .emit import RO_LBL_FONT, RO_VAL_FONT

    out: dict[str, tuple[float, float, float, float]] = {}
    for lbl in schema.labels:
        if lbl.at is None:
            continue
        out[f"lbl-{lbl.id}"] = _text_bbox(
            *lbl.at, lbl.anchor.value, lbl.text, TXT_FONT
        )
    for r in schema.readouts:
        xy = _readout_xy(r, comps)
        if xy is None:
            continue
        x, y = xy
        anchor = "start" if r.side == "right" else "end"
        tx = x + (16 if r.side == "right" else -16)
        out[f"readout-{r.id}.val"] = _text_bbox(tx, y - 2, anchor, "–", RO_VAL_FONT)
        out[f"readout-{r.id}.lbl"] = _text_bbox(tx, y + 14, anchor, r.label, RO_LBL_FONT)
    for c in schema.components:
        if c.label is None:
            continue
        off = LABEL_OFFSET.get(c.type, 32)
        y = c.at[1] - off
        out[f"comp-{c.id}.lbl"] = _text_bbox(
            c.at[0], y, "middle", c.label.text, TXT_H_FONT
        )
        if c.label.sub:
            out[f"comp-{c.id}.sub"] = _text_bbox(
                c.at[0], y + 14, "middle", c.label.sub, TXT_S_FONT
            )
    return out


def _readout_xy(r: Readout, comps: dict[str, object]) -> Point | None:
    from .model import Component

    if r.at.is_ref:
        comp = comps.get(r.at.comp)  # type: ignore[arg-type]
        if comp is None:
            return None
        assert isinstance(comp, Component)
        return readout_position(r, comp.at, comp.type)
    return (r.at.x or 0, r.at.y or 0)
