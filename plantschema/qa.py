"""QA-Stufe: Kollisions-Detektion (S3: vollständiges Check-Set, R-34).

Geprüft (cmi-`svg_layout_check.py`-Kanon, Bounding-Box-Heuristik):
- **TEXT×TEXT** (`text-text`): zwei Texte überlappen sich (S1,
  unverändert: 2-px-Nachte + echte Überdeckung).
- **LINE×TEXT** (`line-text`): ein Pipe-Segment läuft durch einen Text
  (S1, unverändert: 5-px-Sampling, ≥ 2 Treffer im Text-BBox).
- **TEXT×BOX-Kante** (`text-box-edge`): Text-BBox überschneidet die
  **Umrandung/Box** einer Komponente (BBox aus `symbols.SYMBOL_BOUNDS`,
  R-34) — nur wenn der Overlap-Anteil > 50 % der **Text-Fläche**
  (cmi `overlap_area`-Logik); darunter = „Text neben Symbol" erlaubt
  (R-34 Schwelle).
- **USE×TEXT** (`symbol-text`): P&ID-Symbol-Körper (gleiche BBox aus
  `SYMBOL_BOUNDS`) × Text — gleiche >50 %-Overlap-Anteils-Logik;
  eine Kollision pro (Symbol, Text)-Paar (dedupliziert).
- **Readout-Größen-Gate** (`readout-size`): emittierter Readout-Text:
  Wert ≥ `VALUE_FONT_MIN` (12 px), Label ≥ `LABEL_FONT_MIN` (11 px)
  (S3: harte Gate-Prüfung der Konstanten aus `place.py`).
- **GROUP-BOX** (`group-box`, S4-L1, R-35): Overlap zweier Makro-
  Gruppen-Boxen (AABB) → Kollision; gleiche `OVERLAP_THRESHOLD`-
  Methodik wie die Text-Box-Edge-Checks (> 50 % der kleineren Box-
  Fläche).
- **COMPONENT-OUTSIDE-GROUP-BOX** (`component-outside-group-box`,
  S4-L2, R-36): Mitglied-Komponente, deren Symbol-BBox (aus
  `symbols.SYMBOL_BOUNDS`) die **EIGENE** Makro-Gruppen-Box verlässt
  → Kollision; Methode wie die bestehenden Box-Checks (AABB:
  `component_bounds` × `group_box`, strikt: > 0 px Überstand).
- **COMPONENT-IN-FOREIGN-GROUP-BOX** (`component-in-foreign-group-box`,
  S4-L3, R-37): Komponente, deren Symbol-BBox eine **FREMDE**
  Gruppen-Box überlappt (> 0 px, gleiche AABB-Methodik wie
  COMPONENT-OUTSIDE-GROUP-BOX) → Kollision (Fehleinsortierung-Signal);
  die EIGENE Box zählt nicht (das ist R-36s Gate).
- **GROUP-BOX×LABEL** (`group-box-label`, S4-L3, R-37): Label (freies
  oder an ein Mitglied gebundenes) überlappt eine Gruppen-Box-Kante
  mit > 50 % der Label-Text-Fläche (`OVERLAP_THRESHOLD`, gleiche
  Schwelle wie die bestehenden Box-Checks) → Kollision; ein gebundenes
  Label ignoriert die EIGENE Gruppen-Box des Hosts, prüft aber alle
  fremden. (GROUP-BOX×LABEL war R-35-Ankündigung, in S4-L3 gelandet.)

Kanon: `WIDTH_FACTOR=0.52`, `HEIGHT_FACTOR=1.2`, Sampling 5 px
(cmi `sample_segment`); `text-anchor`-Korrektur in der BBox
(`end` → x−width, `middle` → x−width/2; cmi `text_bbox`-Logik).

API: `detect_collisions(texts, pipes, components=(), readouts=(),
labels=(), groups=())` — S1-Signatur `detect_collisions(texts, pipes)`
bleibt als Alias (bestehende S1/S2-Tests grün).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .model import Component, Group, Label, Readout, Schema
from .place import TXT_FONT, _text_bbox
from .route import PipeGeometry
from .symbols import component_bounds

__all__ = [
    "HEIGHT_FACTOR",
    "WIDTH_FACTOR",
    "OVERLAP_THRESHOLD",
    "Collision",
    "TextElem",
    "estimate_width",
    "text_bbox",
    "overlap_area",
    "group_box",
    "detect_collisions",
]

#: cmi-Kanon-Faktoren (system-ui, gemischte Schrift).
WIDTH_FACTOR: float = 0.52
HEIGHT_FACTOR: float = 1.2

#: Sampling-Abstand für Line×Text (px, cmi-`sample_segment`-Kanon).
_SAMPLE_STEP: float = 5.0

#: Overlap-Anteils-Schwelle (R-34): Text-Fläche-Anteil in der
#: Symbol-BBox, ab dem eine Kollision gezählt wird.
OVERLAP_THRESHOLD: float = 0.5

#: Platzhalter-Box (unbekannter Typ, S1-Fallback ±20).
_PLACEHOLDER: tuple[int, int, int, int] = (-20, -20, 20, 20)


@dataclass(frozen=True, slots=True)
class TextElem:
    """Ein abgeprüfter Text (Label oder Readout-Text)."""

    elem_id: str  # z. B. "lbl-zone" / "readout-a6.lbl"
    text: str
    font_size: int
    x: int
    y: int
    anchor: str = "start"  # "start" | "middle" | "end"
    #: Optionales Readout-Größen-Kriterium: "value" (≥ VALUE_FONT_MIN)
    #: oder "label" (≥ LABEL_FONT_MIN); sonst None.
    size_kind: str | None = None


@dataclass(frozen=True, slots=True)
class Collision:
    """Eine erkannte Kollision (Gate-Report-Zeile, R-34-Format)."""

    kind: str  # "text-text" | "line-text" | "text-box-edge" | "symbol-text"
    #            | "readout-size" | "group-box" (S4-L1, R-35)
    #            | "component-outside-group-box" (S4-L2, R-36)
    #            | "component-in-foreign-group-box" (S4-L3, R-37)
    #            | "group-box-label" (S4-L3, R-37)
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


def text_bbox(
    t: TextElem,
) -> tuple[float, float, float, float]:
    """Text-BBox (cmi `text_bbox`-Logik: `text-anchor`-Korrektur;
    Baseline: Oberkante y − 0.85·fs, Unterkante y + 0.25·fs)."""
    return _text_bbox(t.x, t.y, t.anchor, t.text, t.font_size)


def _overlap_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, dx) * max(0.0, dy)


def overlap_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Fläche der BBox-Intersektion (0 = keine Überdeckung, cmi-Kanon)."""
    return _overlap_area(a, b)


def _area(
    b: tuple[float, float, float, float],
) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    pad: float = 0.0,
) -> bool:
    return not (a[0] - pad >= b[2] or b[0] - pad >= a[2]
                or a[1] - pad >= b[3] or b[1] - pad >= a[3])


def _sample_segment(
    p1: tuple[int, int], p2: tuple[int, int]
) -> list[tuple[float, float]]:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return [p1]
    n = max(1, int(dist / _SAMPLE_STEP))
    return [(p1[0] + dx * i / n, p1[1] + dy * i / n) for i in range(n + 1)]


def group_box(g: Group) -> tuple[float, float, float, float]:
    """Makro-Box-BBox einer Gruppe (S4-L1, R-35): `at` = obere linke
    Ecke, `size` = Breite/Höhe (Kanon: > 0, geprüft in `validate`)."""
    x, y = g.at
    return (float(x), float(y), float(x + g.size[0]), float(y + g.size[1]))


def _check_group_boxes(
    groups: Sequence[Group], out: list[Collision]
) -> None:
    """GROUP-BOX-Gate (S4-L1, R-35): Overlap zweier Makro-Boxen (AABB).

    Gleiche `OVERLAP_THRESHOLD`-Methodik wie TEXT×BOX-Kante/USE×TEXT:
    Kollision, wenn der Overlap-Anteil der **kleineren** Box-Fläche
    > 50 % liegt; darunter = Boxen neben/über Eck erlaubt. Eine
    Kollision pro (A, B)-Paar, deterministische Schema-Reihenfolge.
    """
    boxes = [(g, group_box(g)) for g in groups]
    for i in range(len(boxes)):
        a, ba = boxes[i]
        for j in range(i + 1, len(boxes)):
            b, bb = boxes[j]
            ov = _overlap_area(ba, bb)
            ref = min(_area(ba), _area(bb))
            if ref > 0 and ov > OVERLAP_THRESHOLD * ref:
                out.append(Collision(
                    "group-box",
                    f"group-{a.id}", f"group-{b.id}",
                    int(round(ba[0])), int(round(ba[1])),
                    f"Gruppen-Boxen überlappen zu "
                    f"{100.0 * ov / ref:.0f} % (Schwelle "
                    f"{OVERLAP_THRESHOLD * 100.0:.0f} %, R-35)",
                ))


def _check_component_outside_group_box(
    components: Sequence[Component],
    groups: Sequence[Group],
    out: list[Collision],
) -> None:
    """COMPONENT-OUTSIDE-GROUP-BOX-Gate (S4-L2, R-36): Mitglied-
    Komponente außerhalb der EIGENEN Makro-Gruppen-Box (AABB; strikt
    > 0 px Überstand, Methode wie die bestehenden Box-Checks).

    (Fremde-Box-Prüfung: COMPONENT-IN-FOREIGN-GROUP-BOX, S4-L3, R-37.)
    Kollisions-Koordinate = Überstandspunkt: Symbol-BBox-Mitte
    (int-gerundet); eine Kollision pro (Komponente, Gruppe)-Paar,
    deterministische Schema-Reihenfolge (Komponenten × Gruppen).
    """
    if not groups:
        return
    owner: dict[str, int] = {}
    for i, g in enumerate(groups):
        for m in g.members:
            owner.setdefault(m, i)
    for c in components:
        gi = owner.get(c.id)
        if c.at is None:
            continue  # ungeplante Komponente (validate)
        cb = component_bounds(c.type, c.at)
        if gi is None:
            continue  # nicht-gruppig: keine EIGENE Box → kein R-36-Treffer
        box = group_box(groups[gi])
        assert c.at is not None
        over_x = max(box[0] - cb[0], 0.0, cb[2] - box[2])
        over_y = max(box[1] - cb[1], 0.0, cb[3] - box[3])
        if over_x <= 0 and over_y <= 0:
            continue
        out.append(Collision(
            "component-outside-group-box",
            f"comp-{c.id}", f"group-{groups[gi].id}",
            int(round((cb[0] + cb[2]) / 2)), int(round((cb[1] + cb[3]) / 2)),
            f"Mitglied {c.id!r} außerhalb der Gruppen-Box "
            f"groups[{gi}].at={groups[gi].at!r} size={groups[gi].size!r} "
            f"(Überstand x={over_x:.0f} px, y={over_y:.0f} px; R-36)",
        ))


def _check_component_in_foreign_group_box(
    components: Sequence[Component],
    groups: Sequence[Group],
    out: list[Collision],
) -> None:
    """COMPONENT-IN-FOREIGN-GROUP-BOX-Gate (S4-L3, R-37): Komponente
    innerhalb/überlappend mit der Box einer Gruppe, der sie NICHT
    angehört (AABB: `component_bounds` × `group_box`, > 0 px Overlap —
    gleiche strikte Methodik wie die bestehenden Box-Checks, R-36).
    Die EIGENE Box wird nicht geprüft (das ist
    COMPONENT-OUTSIDE-GROUP-BOX, R-36). Signalisiert Fehleinsortierung
    (Member in der falschen Box). Eine Kollision pro
    (Komponente, fremde-Gruppe)-Paar, deterministische Schema-
    Reihenfolge.
    """
    if not groups:
        return
    owner: dict[str, int] = {}
    for i, g in enumerate(groups):
        for m in g.members:
            owner.setdefault(m, i)
    for c in components:
        if c.at is None:
            continue  # ungeplante Komponente (validate)
        cb = component_bounds(c.type, c.at)
        own = owner.get(c.id)
        for i, g in enumerate(groups):
            if i == own:
                continue  # eigene Box: R-36s Zuständigkeit
            box = group_box(g)
            ov = _overlap_area(cb, box)
            if ov > 0.0:
                out.append(Collision(
                    "component-in-foreign-group-box",
                    f"comp-{c.id}", f"group-{g.id}",
                    int(round((cb[0] + cb[2]) / 2)),
                    int(round((cb[1] + cb[3]) / 2)),
                    f"Komponente {c.id!r} (Gruppe: "
                    f"{groups[own].id if own is not None else 'keine'}) in "
                    f"fremder Gruppen-Box {g.id!r} (Overlap "
                    f"{ov:.0f} px² > 0; R-37)",
                ))


def _check_group_box_labels(
    texts: Sequence[TextElem],
    groups: Sequence[Group],
    labels: Sequence[Label],
    out: list[Collision],
) -> None:
    """GROUP-BOX×LABEL-Gate (S4-L3, R-37): Label (`.txt`, `lbl-*`),
    das eine Gruppen-Box-Kante mit > 50 % der Label-Text-Fläche
    überlappt (`OVERLAP_THRESHOLD`, gleiche Schwelle/Methodik wie die
    bestehenden Box-Checks: Overlap-Anteil der **Text**-Fläche).

    - Freies Label (ohne Host) → alle Gruppen-Boxen.
    - Gebundenes Label (`comp` = Mitglied) → die EIGENE Gruppen-Box des
      Hosts wird ignoriert, alle fremden Boxen werden geprüft.
    - Nicht-Label-Texte (Readout-/Komponenten-Texte) werden nicht
      geprüft (Bindungs-/Komponenten-Texte ≠ „freies Label").

    Eine Kollision pro (Label, Box)-Paar, deterministische
    Schema-Reihenfolge.
    """
    if not groups:
        return
    host_group: dict[str, int] = {}
    for i, g in enumerate(groups):
        for m in g.members:
            host_group.setdefault(m, i)
    label_index: dict[str, Label] = {
        f"lbl-{lbl.id}": lbl for lbl in labels
    }
    boxes = [(g, group_box(g)) for g in groups]
    for t in texts:
        if not t.elem_id.startswith("lbl-") or not t.text:
            continue
        lbl = label_index.get(t.elem_id)
        if lbl is None or lbl.comp is None:
            skip: int | None = None  # freies Label: alle Boxen
        else:
            skip = host_group.get(lbl.comp)
        tb = text_bbox(t)
        text_area = _area(tb)
        if text_area <= 0:
            continue
        for i, (g, gb) in enumerate(boxes):
            if i == skip:
                continue  # eigene Box des Host-Mitglieds (R-37)
            ov = _overlap_area(tb, gb)
            if ov > OVERLAP_THRESHOLD * text_area:
                out.append(Collision(
                    "group-box-label",
                    t.elem_id, f"group-{g.id}",
                    int(round(tb[0])), int(round(tb[1])),
                    f"Label {t.text!r} zu "
                    f"{100.0 * ov / text_area:.0f} % in der Gruppen-Box "
                    f"{g.id!r} (Schwelle "
                    f"{OVERLAP_THRESHOLD * 100.0:.0f} %, R-37)",
                ))


def _check_readout_size(texts: Sequence[TextElem], out: list[Collision]) -> None:
    """Readout-Größen-Gate (R-34): Wert ≥ 12 px, Label ≥ 11 px."""
    from .place import LABEL_FONT_MIN, VALUE_FONT_MIN

    for t in texts:
        if t.size_kind is None:
            continue
        minimum = VALUE_FONT_MIN if t.size_kind == "value" else LABEL_FONT_MIN
        if t.font_size < minimum:
            out.append(Collision(
                "readout-size",
                t.elem_id,
                "min" if t.size_kind == "value" else "min-label",
                t.x,
                t.y,
                f"Readout-{'Wert' if t.size_kind == 'value' else 'Label'}-Text "
                f"{t.font_size} px < Mindestgröße {minimum} px (R-34)",
            ))


def detect_collisions(
    texts: Sequence[TextElem],
    pipes: Sequence[PipeGeometry],
    components: Sequence[Component] = (),
    readouts: Sequence[Readout] = (),
    labels: Sequence[Label] = (),
    groups: Sequence[Group] = (),
) -> list[Collision]:
    """Alle S3-Kollisionen (deterministisch: Eingabe-Reihenfolge).

    S1-Compatibilität: `detect_collisions(texts, pipes)` bleibt gültig
    (nur TEXT×TEXT + LINE×TEXT). S3-Parameter (R-34-API):
    - `components`: Komponente-Liste → Symbol-Bounding-Boxes aus
      `symbols.SYMBOL_BOUNDS` (TEXT×BOX-Kante + USE×TEXT-Checks).
    - `readouts`/`labels`: Readout-/Label-Modelle (R-34-API-Vertrag;
      die Text-BBs kommen aus `texts`, die hier autoritativ ist —
      `__main__._pipeline` buildet sie aus Readouts/Labels/Emissions-
      Klassen).
    - `groups` (S4-L1, R-35): Gruppe-Liste → Makro-Boxen (`at`/`size`)
      → GROUP-BOX-Overlap-Check (Kollision nur bei > 50 % Overlap).
      + (S4-L2, R-36) COMPONENT-OUTSIDE-GROUP-BOX-Check (Mitglied
      außerhalb der EIGENEN Box, strikt > 0 px; `components` +
      `groups` zusammen).
      + (S4-L3, R-37) COMPONENT-IN-FOREIGN-GROUP-BOX-Check (Komponente
      in FREMDER Box, strikt > 0 px Overlap, eigene Box ausgenommen)
      + GROUP-BOX×LABEL-Check (Label mit > 50 % Text-Fläche in
      fremder Box; gebundene Labels ignorieren die eigene Box;
      `labels` + `groups` + `texts` zusammen).
    """
    component_boxes: dict[str, tuple[float, float, float, float]] | None = (
        {c.id: component_bounds(c.type, c.at)
         for c in components if c.at is not None}
        if components
        else None
    )
    _ = readouts  # R-34-API-Vertrag (s. Docstring)
    return _detect(texts, pipes, component_boxes, groups, components, labels)


def _detect(
    texts: Sequence[TextElem],
    pipes: Sequence[PipeGeometry],
    component_boxes: dict[str, tuple[float, float, float, float]] | None,
    groups: Sequence[Group] = (),
    components: Sequence[Component] = (),
    labels: Sequence[Label] = (),
) -> list[Collision]:
    """S3-Check-Set (R-34) + S4-L1-Gruppe-Check (R-35) +
    S4-L2-Mitglied-Check (R-36) + S4-L3-Gruppen-Checks (R-37):
    TEXT×TEXT, LINE×TEXT, TEXT×BOX-Kante, USE×TEXT, Readout-Größe,
    GROUP-BOX, COMPONENT-OUTSIDE-GROUP-BOX,
    COMPONENT-IN-FOREIGN-GROUP-BOX, GROUP-BOX×LABEL."""
    out: list[Collision] = []
    boxes = [(t, text_bbox(t)) for t in texts if t.text]

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

    # 3) TEXT×BOX-Kante + 4) USE×TEXT (R-34, >50 %-Overlap-Anteil der
    #    Text-Fläche; dedupliziert: eine Kollision pro Paar).
    #    Labels (`.txt`, lbl-*) → `text-box-edge`; alle anderen Texte
    #    (Readout-/Komponenten-Texte) → `symbol-text`.
    if component_boxes:
        for t, tb in boxes:
            text_area = _area(tb)
            for comp_id, cb in component_boxes.items():
                ov = _overlap_area(tb, cb)
                if text_area > 0 and ov > OVERLAP_THRESHOLD * text_area:
                    kind = (
                        "text-box-edge"
                        if t.elem_id.startswith("lbl-")
                        else "symbol-text"
                    )
                    out.append(Collision(
                        kind,
                        t.elem_id,
                        f"comp-{comp_id}",
                        int(round(tb[0])), int(round(tb[1])),
                        f"Text {t.text!r} zu {100.0 * ov / text_area:.0f} % "
                        f"in der Symbol-BBox (Schwelle "
                        f"{OVERLAP_THRESHOLD * 100.0:.0f} %, R-34)",
                    ))

    # 5) Readout-Größen-Gate (R-34).
    _check_readout_size(texts, out)

    # 6) GROUP-BOX-Overlap (S4-L1, R-35).
    _check_group_boxes(groups, out)
    # 7) COMPONENT-OUTSIDE-GROUP-BOX (S4-L2, R-36).
    _check_component_outside_group_box(components, groups, out)
    # 8) COMPONENT-IN-FOREIGN-GROUP-BOX (S4-L3, R-37).
    _check_component_in_foreign_group_box(components, groups, out)
    # 9) GROUP-BOX×LABEL (S4-L3, R-37).
    _check_group_box_labels(texts, groups, labels, out)
    return out


def texts_for_schema(schema: Schema) -> list[TextElem]:
    """S3-Text-Input: Labels + Readout-Texte + Komponenten-Labels.

    Deterministisch (Schema-Reihenfolge); Positionen = Emissions-
    Positionen (s. `emit.build_svg` / `__main__._pipeline`):
    - Labels: `.txt` (TXT_FONT) an `label.at` bzw. Auto-Slot
      (`place.label_position`, R-32; unbekannter Host → übersprungen).
    - Readouts: `.ro-val` („–", `data-value`-Hook) + `.ro-lbl`
      (Emissions-Fontgrößen, `side` → Anker, 16 px neben Symbol).
    - Komponenten: `.txt-h` + sub `.txt-s` an der up-Slot-Position
      (`place.component_label_offset`; Sub 17 px unter der Haupt-Baseline).
    """
    from .emit import RO_LBL_FONT, RO_VAL_FONT
    from .place import (
        TXT_H_FONT,
        TXT_S_FONT,
        component_label_offset,
        readout_position,
        resolve_label,
    )

    comps = {c.id: c for c in schema.components}
    texts: list[TextElem] = []
    for lbl in schema.labels:
        pos, anchor = resolve_label(lbl, schema)
        if pos is None:
            continue
        texts.append(TextElem(
            f"lbl-{lbl.id}", lbl.text, TXT_FONT, *pos, anchor
        ))
    for r in schema.readouts:
        if r.at.is_ref:
            comp = comps.get(r.at.comp)  # type: ignore[arg-type]
            if comp is None:
                continue
            x, y = readout_position(r, comp.at, comp.type)
        else:
            x, y = (r.at.x or 0, r.at.y or 0)
        anchor = "start" if r.side == "right" else "end"
        tx = x + (16 if r.side == "right" else -16)
        texts.append(TextElem(
            f"readout-{r.id}.val", "–", RO_VAL_FONT, tx, y - 2, anchor,
            size_kind="value",
        ))
        texts.append(TextElem(
            f"readout-{r.id}.lbl", r.label, RO_LBL_FONT, tx, y + 14, anchor,
            size_kind="label",
        ))
    for c in schema.components:
        if c.label is None:
            continue
        y = c.at[1] - component_label_offset(
            c.type, c.at, 2 if c.label.sub else 1
        )
        texts.append(TextElem(
            f"comp-{c.id}.lbl", c.label.text, TXT_H_FONT, c.at[0], y, "middle"
        ))
        if c.label.sub:
            texts.append(TextElem(
                f"comp-{c.id}.sub", c.label.sub, TXT_S_FONT, c.at[0],
                y + 17, "middle",
            ))
    return texts
