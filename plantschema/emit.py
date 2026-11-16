"""Emissions-Stufe: SVG-Dokument-Bau (byte-deterministisch).

Regeln (Kanon, `docs/model-reference.md` § Determinismus):
- Festes Attribut-Reihenfolge (Insertion-Order, ElementTree ≥ Py3.8).
- KEIN Zeitstempel, keine Zufalls-IDs.
- Layer-Reihenfolge: Hintergrund → Gruppen-Boxen → Pipes → Komponenten
  → Readouts → Labels (Gruppen-Boxen unterhalb aller Zonen-Behälter,
  S4-L1, R-35 — überdecken nichts). S4-L5b (R-39): `layer-lanes`
  zwischen Gruppen-Boxen und Pipes — nur bei vorhandenen Lanes.
- Stabile ID-Verträge: `comp-*`, `pipe-*`, `readout-*`, `lbl-*`.
- S2: P&ID-Symbole via `<defs>` aus `symbols.render_defs()` (Seed cmi
  `ui/svg/pid-symbols.svg`); Komponenten = `symbols.render_component`
  (`<use href="#pid-…">` + Labels `.txt-h`/`.txt-s`).
- S2: Readouts = PT-Symbol `<use href="#pid-pt">` + Wert-Text `.ro-val`
  (Platzhalter „–") + Label-Text `.ro-lbl` (cmi `loop-svg.js::readout`:
  Wert oben, Label unten, 16 px neben Symbol; `side` = text-anchor).
- S2: Pfeil-Endpunkte (R-29) als `.pipe-arrow`-Paths (Fill = Kind-Farbe),
  kein `marker-end` (Farbe aus context-stroke nicht portabel).

Farb-Kanon: vl #f59e0b, rl #4da3ff, ww #38bdf8, gas #94a3b8, ctl #a78bfa;
Hintergrund = canvas.background (default #0b1220).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .groups import is_composite, owner_index, pipe_foreign_indices
from .lanes import lane_assignments, lane_axis
from .model import Group, Lane, Schema
from .place import readout_position, resolve_label
from .route import PipeGeometry, arrow_d, port_position, route_lane
from .symbols import port_stubs, render_component, render_defs

__all__ = [
    "COMPOSITE_RX",
    "GB_LBL_FONT",
    "LABEL_FONT",
    "LANE_LBL_FONT",
    "RO_LBL_FONT",
    "RO_VAL_FONT",
    "TXT_FONT",
    "build_svg",
    "compute_layout",
    "component_stubs",
    "group_framed",
    "lane_framed",
    "render",
]

#: Gruppen-Box-Label-Font (S4-L1, R-35): kleine, gedämpfte Schrift.
GB_LBL_FONT: int = 12

#: SVG-Namespace (in den Root-Tag injiziert; ElementTree kennt keinen Default-NS).
_SVG_NS = "http://www.w3.org/2000/svg"

#: Font-Größen der emittierten Klassen (QA-Input, mind. 12/11 px Kanon).
TXT_FONT: int = 14          # .txt (freie Labels)
LABEL_FONT: int = 14        # .txt-h (Komponenten-Label, wie S1 .txt)
RO_VAL_FONT: int = 12       # .ro-val (Readout-Wert, mind. 12 px Kanon)
RO_LBL_FONT: int = 11       # .ro-lbl (Readout-Label, mind. 11 px Kanon)

_CSS = (
    ".vl{stroke:#f59e0b;fill:none}\n"
    ".rl{stroke:#4da3ff;fill:none}\n"
    ".ww{stroke:#38bdf8;fill:none}\n"
    ".gas{stroke:#94a3b8;fill:none}\n"
    ".ctl{stroke:#a78bfa;fill:none;stroke-dasharray:6 4;stroke-width:1.5}\n"
    ".pipe{stroke-width:3}\n"
    ".pipe-arrow{stroke:none}\n"
    ".arrow-vl{fill:#f59e0b}\n"
    ".arrow-rl{fill:#4da3ff}\n"
    ".arrow-ww{fill:#38bdf8}\n"
    ".arrow-gas{fill:#94a3b8}\n"
    ".arrow-ctl{fill:#a78bfa}\n"
    ".pid{fill:none;stroke:#e6edf7;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}\n"
    f".pid-t{{fill:#8fa0bd;font-size:11px;font-family:system-ui,sans-serif;font-weight:600;text-anchor:middle}}\n"
    f".txt{{fill:#e2e8f0;font-size:{TXT_FONT}px;font-family:system-ui,sans-serif}}\n"
    f".txt-h{{fill:#e2e8f0;font-size:{LABEL_FONT}px;font-family:system-ui,sans-serif;font-weight:600}}\n"
    f".txt-s{{fill:#8fa0bd;font-size:12px;font-family:system-ui,sans-serif}}\n"
    f".ro-val{{fill:#fff;font-size:{RO_VAL_FONT}px;font-family:system-ui,sans-serif}}\n"
    f".ro-lbl{{fill:#8fa0bd;font-size:{RO_LBL_FONT}px;font-family:system-ui,sans-serif}}\n"
    ".comp{stroke:#94a3b8;fill:none;stroke-width:1.8}\n"
    ".comp-ph{stroke:#94a3b8;fill:none;stroke-width:1.8}\n"
    ".port{fill:#e2e8f0;stroke:none}\n"
    ".gbox{fill:none;stroke:rgba(140,160,200,0.25);stroke-width:1.2;stroke-dasharray:6 4}\n"
    ".gbox-lbl{fill:#8fa0bd;font-size:12px;font-family:system-ui,sans-serif;opacity:0.85}\n"
)

#: composite-Box-Style (S4-L5a, R-38): kräftigerer, länger gestrichelter
#: Rand + gerundete Ecken. Nur emittiert, wenn das Schema composites
#: enthält (Byte-Stabilität aller Schemas ohne composites).
_CSS_COMPOSITE = (
    ".gbox-composite{stroke:rgba(140,160,200,0.45);stroke-width:2;"
    "stroke-dasharray:10 5}\n"
)

#: Eckenradius der composite-Box (SVG `rx`/`ry`, R-38).
COMPOSITE_RX: int = 10

#: Lane-Label-Font (S4-L5b, R-39): klein, subtil.
LANE_LBL_FONT: int = 10

#: Lane-Box-Style (S4-L5b, R-39): gestrichelt wie `.gbox`, aber eigene
#: Klasse + abgesetzte Farbe. Nur emittiert, wenn das Schema Lanes hat
#: (Byte-Stabilität aller Schemas ohne Lanes).
_CSS_LANE = (
    ".lane{fill:none;stroke:rgba(200,180,140,0.30);stroke-width:1;"
    "stroke-dasharray:3 3}\n"
    f".lane-lbl{{fill:#a8977a;font-size:{LANE_LBL_FONT}px;"
    "font-family:system-ui,sans-serif;opacity:0.8}\n"
)


#: Stutzen-Style (S4-L5c): gleiche Strichstärke wie `.pipe`, Farbe über
#: die Kind-Klasse. Nur emittiert, wenn mind. ein Stutzen existiert
#: (Byte-Stabilität aller Schemas ohne Stutzen).
_CSS_STUB = ".stub{stroke-width:3;stroke-linecap:butt}\n"


def group_framed(g: Group) -> bool:
    """Rahmen+Label der Gruppe zeichnen? (S4-L5c, R-38: `frame` explizit
    gewinnt; Default atomic an, composite aus.)"""
    return g.frame if g.frame is not None else not is_composite(g)


def lane_framed(lane: Lane) -> bool:
    """Rahmen+Label der Lane zeichnen? (S4-L5c, R-39: Default an.)"""
    return lane.frame if lane.frame is not None else True


def component_stubs(
    schema: Schema,
) -> list[tuple[str, str, str, str]]:
    """Stutzen (S4-L5c): `(comp_id, port, kind, d)` je verbundenem
    Innen-Port (`symbols.port_stubs`), Komponenten- × Port-Reihenfolge.

    Verbunden = mind. eine sichtbare Pipe (Kind nicht in `hidden_kinds`)
    endet an (comp, port); Kind = erste solche Pipe (Schema-Reihenfolge).
    """
    hidden = schema.hidden_kind_values
    kind_at: dict[tuple[str, str], str] = {}
    for p in schema.pipes:
        if p.kind.value in hidden:
            continue
        for ref in (p.from_, p.to):
            kind_at.setdefault((ref.comp, ref.port), p.kind.value)
    out: list[tuple[str, str, str, str]] = []
    for c in schema.components:
        if c.at is None:
            continue
        cx, cy = c.at
        for port, (ex, ey), (px, py) in port_stubs(c.type):
            kind = kind_at.get((c.id, port))
            if kind is None:
                continue
            out.append((
                c.id, port, kind,
                f"M{cx + ex},{cy + ey} L{cx + px},{cy + py}",
            ))
    return out


def _group_owner(schema: Schema) -> dict[str, int]:
    """Component-ID → Gruppen-Index (S4-L3, R-37; deterministisch:
    Schema-Reihenfolge; Doppel-Mitgliedschaft wäre ein Validate-Problem
    und überschreibt hier schlicht — Pipeline setzt `validate` voraus)."""
    return owner_index(schema.groups)


def compute_layout(schema: Schema) -> tuple[list[PipeGeometry], dict[str, tuple[int, int]]]:
    """Pipeline-Hilfsstufe: Routes + Readout-Positionen berechnen.

    S4-L3 (R-37): Routes laufen gruppen-bewusst via `route_groups`:
    `via`-Pipes bleiben Autor-Route 1:1; ohne `via` wird bei
    inter-gruppigen Pipes (from- und to-Ende in verschiedenen Gruppen)
    der orthogonale Fallback gegen alle **fremden** Gruppen-Box-AABBs
    geprüft (Kreuzung = Box-Interior; eigene Boxen zählen nicht) und
    bei erstem Fremdkreuzen deterministisch über den Kanal um die
    nächste Box-Kante umgeleitet. Intra-Gruppe / keine Gruppen →
    unverändert (S2-Fallback). S4-L5a (R-38): „fremd" mit transitiver
    Semantik (`groups.pipe_foreign_indices`).
    """
    comps = {c.id: c for c in schema.components}
    boxes = {
        i: (float(g.at[0]), float(g.at[1]),
            float(g.at[0] + g.size[0]), float(g.at[1] + g.size[1]))
        for i, g in enumerate(schema.groups)
    }
    owner = _group_owner(schema)
    slots = lane_assignments(schema) if schema.lanes else {}
    pipes: list[PipeGeometry] = []
    for p in schema.pipes:
        cf, ct = comps[p.from_.comp], comps[p.to.comp]
        fp = port_position(cf.type, cf.at, p.from_.port)
        tp = port_position(ct.type, ct.at, p.to.port)
        foreign = [
            boxes[i] for i in pipe_foreign_indices(
                p.from_.comp, p.to.comp, schema.groups, owner,
            )
        ]
        pipes.append(PipeGeometry(
            p.id,
            route_lane(p, fp, tp, slots.get(p.id), foreign_boxes=foreign),
            p.kind.value,
            p.flow,
        ))
    readout_pos: dict[str, tuple[int, int]] = {}
    for r in schema.readouts:
        if r.at.is_ref:
            comp = comps[r.at.comp]  # type: ignore[arg-type]
            readout_pos[r.id] = readout_position(r, comp.at, comp.type)
        else:
            readout_pos[r.id] = (r.at.x or 0, r.at.y or 0)
    return pipes, readout_pos


# ------------------------------------------------------------------- document


def build_svg(
    schema: Schema,
    pipes: list[PipeGeometry],
    readout_pos: dict[str, tuple[int, int]],
) -> str:
    """SVG-Dokument-String (byte-deterministisch)."""
    w, h = schema.canvas.width, schema.canvas.height
    root = ET.Element("svg", {"viewBox": f"0 0 {w} {h}"})

    # <defs>: Platzhalter, nach der Serialisierung mit Roh-Text ersetzt
    # (ElementTree würde `defs.text` XML-escapen — die P&ID-Symbole müssen
    # als Markup durchkommen; S1-Präzedenz: Namespace-Injektion).
    ET.SubElement(root, "defs")

    style = ET.SubElement(root, "style")
    has_composite = any(
        is_composite(g) and group_framed(g) for g in schema.groups
    )
    stubs = component_stubs(schema)
    style.text = (
        _CSS + (_CSS_COMPOSITE if has_composite else "")
        + (_CSS_LANE if schema.lanes else "")
        + (_CSS_STUB if stubs else "")
    )

    ET.SubElement(root, "rect", {
        "id": "canvas-bg", "x": "0", "y": "0",
        "width": str(w), "height": str(h),
        "fill": schema.canvas.background,
    })

    layers: dict[str, ET.Element] = {}
    layer_names: tuple[str, ...] = (
        "layer-groups", "layer-pipes", "layer-components",
        "layer-readouts", "layer-labels",
    )
    if schema.lanes:
        # S4-L5b (R-39): Lane-Layer nach Gruppen-Boxen, vor Pipes.
        layer_names = ("layer-groups", "layer-lanes", *layer_names[1:])
    for name in layer_names:
        layers[name] = ET.SubElement(root, "g", {"id": name})

    # Gruppen-Boxen (Schema-Reihenfolge, S4-L1, R-35): gestrichelte
    # Makro-Box (`.gbox`, kein Fill) + optionales Label (`.gbox-lbl`,
    # oben links in der Box, Offset 8 px). Unterhalb der Zonen-Behälter.
    # S4-L5a (R-38): composite-Boxen zuerst (unter den atomaren Kindern),
    # `.gbox .gbox-composite` + `rx`/`ry`, `data-kind`/`data-includes`.
    lg = layers["layer-groups"]
    ordered = [g for g in schema.groups if is_composite(g)] + [
        g for g in schema.groups if not is_composite(g)
    ]
    for g in ordered:
        x, y = g.at
        box = ET.SubElement(lg, "g", {"id": f"group-{g.id}"})
        if g.hub:
            box.set("data-hub", g.hub)
        rect = {
            "class": "gbox", "x": str(x), "y": str(y),
            "width": str(g.size[0]), "height": str(g.size[1]),
        }
        if is_composite(g):
            box.set("data-kind", "composite")
            box.set("data-includes", " ".join(g.includes))
            rect["class"] = "gbox gbox-composite"
            rect["rx"] = rect["ry"] = str(COMPOSITE_RX)
        if not group_framed(g):
            continue  # S4-L5c: kein Rahmen → auch kein Label
        ET.SubElement(box, "rect", rect)
        if g.label:
            ET.SubElement(box, "text", {
                "class": "gbox-lbl", "x": str(x + 8), "y": str(y + 14),
            }).text = g.label

    # Lane-Boxen (Schema-Reihenfolge, S4-L5b, R-39): gestrichelte Box
    # (`.lane`) + optionales Label (`.lane-lbl`, oben links, 6/12 px).
    if schema.lanes:
        ln = layers["layer-lanes"]
        for lane in schema.lanes:
            assert lane.at is not None and lane.size is not None
            x, y = lane.at
            box = ET.SubElement(ln, "g", {
                "id": f"lane-{lane.id}",
                "data-axis": "horizontal" if lane_axis(lane) == "h"
                else "vertical",
                "data-pipes": " ".join(lane.pipes),
            })
            if not lane_framed(lane):
                continue  # S4-L5c: kein Rahmen → auch kein Label
            ET.SubElement(box, "rect", {
                "class": "lane", "x": str(x), "y": str(y),
                "width": str(lane.size[0]), "height": str(lane.size[1]),
            })
            if lane.label:
                ET.SubElement(box, "text", {
                    "class": "lane-lbl", "x": str(x + 6), "y": str(y + 12),
                }).text = lane.label

    # Pipes (Schema-Reihenfolge) + Pfeil-Endpunkte (R-29).
    # S4-L5c: Pipes mit Kind in `hidden_kinds` (inkl. Pfeil) entfallen.
    lp = layers["layer-pipes"]
    hidden = schema.hidden_kind_values
    for p in pipes:
        if p.kind in hidden:
            continue
        attrs = {"id": f"pipe-{p.id}", "class": f"pipe {p.kind}", "d": p.d}
        attrs["data-kind"] = p.kind
        if p.flow:
            attrs["data-flow"] = p.flow
        ET.SubElement(lp, "path", attrs)
        ad = arrow_d(p.points)
        if ad:
            ET.SubElement(lp, "path", {
                "class": f"pipe-arrow arrow-{p.kind}", "d": ad,
            })

    # Komponenten (Schema-Reihenfolge, P&ID-Symbole via <use>).
    # S4-L5c: Stutzen (`.stub`) direkt nach der comp-* Gruppe (über dem
    # Symbol), Port-Reihenfolge des Symbols.
    lc = layers["layer-components"]
    stubs_by_comp: dict[str, list[tuple[str, str, str]]] = {}
    for comp_id, port, kind, d in stubs:
        stubs_by_comp.setdefault(comp_id, []).append((port, kind, d))
    for c in schema.components:
        chunk = render_component(c)
        el = ET.fromstring(chunk)
        lc.append(el)
        for port, kind, d in stubs_by_comp.get(c.id, ()):
            ET.SubElement(lc, "path", {
                "class": f"stub {kind}", "d": d,
                "data-comp": c.id, "data-port": port,
            })

    # Readouts (Schema-Reihenfolge): PT-Symbol + Wert + Label (cmi-Kanon).
    lr = layers["layer-readouts"]
    for r in schema.readouts:
        x, y = readout_pos[r.id]
        g = ET.SubElement(lr, "g", {"id": f"readout-{r.id}"})
        if r.value_key:
            g.set("data-value-key", r.value_key)
        g.set("data-readout", r.label)
        if r.loop:
            g.set("data-loop", r.loop)
        ET.SubElement(g, "use", {
            "href": "#pid-pt", "x": str(x), "y": str(y), "class": "sym",
        })
        side = r.side
        tx = x + (16 if side == "right" else -16)
        anchor = "start" if side == "right" else "end"
        tval = ET.SubElement(g, "text", {
            "class": "ro-val", "x": str(tx), "y": str(y - 2),
            "text-anchor": anchor, "data-value": "true",
        })
        tval.text = "–"
        tlbl = ET.SubElement(g, "text", {
            "class": "ro-lbl", "x": str(tx), "y": str(y + 14),
            "text-anchor": anchor,
        })
        tlbl.text = r.label

    # Labels (Schema-Reihenfolge): `at` = exakt (Override); Auto-Slots
    # (S3, R-32) mit Slot-Anker (up/down=middle, left/right=end/start).
    ll = layers["layer-labels"]
    for lbl in schema.labels:
        pos, anchor = resolve_label(lbl, schema)
        if pos is None:
            continue  # Unbekannter Host (Validierungs-Problem liegt vor)
        ET.SubElement(ll, "text", {
            "id": f"lbl-{lbl.id}", "class": "txt",
            "x": str(pos[0]), "y": str(pos[1]),
            "text-anchor": anchor,
        }).text = lbl.text

    body = ET.tostring(root, encoding="unicode")
    body = body.replace("<svg ", f'<svg xmlns="{_SVG_NS}" ', 1)
    body = body.replace(
        "<defs />",
        f"<defs>\n{render_defs({c.type for c in schema.components})}\n</defs>",
        1,
    )
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def render(schema: Schema) -> str:
    """Kürzel: Layout berechnen + Dokument bauen."""
    pipes, readout_pos = compute_layout(schema)
    return build_svg(schema, pipes, readout_pos)
