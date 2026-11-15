"""Emissions-Stufe: SVG-Dokument-Bau (byte-deterministisch).

Regeln (Kanon, `docs/model-reference.md` § Determinismus):
- Festes Attribut-Reihenfolge (Insertion-Order, ElementTree ≥ Py3.8).
- KEIN Zeitstempel, keine Zufalls-IDs.
- Layer-Reihenfolge: Hintergrund → Gruppen-Boxen → Pipes → Komponenten
  → Readouts → Labels (Gruppen-Boxen unterhalb aller Zonen-Behälter,
  S4-L1, R-35 — überdecken nichts).
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

from .model import Schema
from .place import readout_position, resolve_label
from .route import PipeGeometry, arrow_d, port_position, route_pipe
from .symbols import render_component, render_defs

__all__ = [
    "GB_LBL_FONT",
    "LABEL_FONT",
    "RO_LBL_FONT",
    "RO_VAL_FONT",
    "TXT_FONT",
    "build_svg",
    "compute_layout",
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


def compute_layout(schema: Schema) -> tuple[list[PipeGeometry], dict[str, tuple[int, int]]]:
    """Pipeline-Hilfsstufe: Routes + Readout-Positionen berechnen."""
    comps = {c.id: c for c in schema.components}
    pipes: list[PipeGeometry] = []
    for p in schema.pipes:
        cf, ct = comps[p.from_.comp], comps[p.to.comp]
        fp = port_position(cf.type, cf.at, p.from_.port)
        tp = port_position(ct.type, ct.at, p.to.port)
        pipes.append(PipeGeometry(
            p.id, route_pipe(p, fp, tp), p.kind.value, p.flow
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
    style.text = _CSS

    ET.SubElement(root, "rect", {
        "id": "canvas-bg", "x": "0", "y": "0",
        "width": str(w), "height": str(h),
        "fill": schema.canvas.background,
    })

    layers: dict[str, ET.Element] = {}
    layer_names = (
        "layer-groups", "layer-pipes", "layer-components",
        "layer-readouts", "layer-labels",
    )
    for name in layer_names:
        layers[name] = ET.SubElement(root, "g", {"id": name})

    # Gruppen-Boxen (Schema-Reihenfolge, S4-L1, R-35): gestrichelte
    # Makro-Box (`.gbox`, kein Fill) + optionales Label (`.gbox-lbl`,
    # oben links in der Box, Offset 8 px). Unterhalb der Zonen-Behälter.
    lg = layers["layer-groups"]
    for g in schema.groups:
        x, y = g.at
        box = ET.SubElement(lg, "g", {"id": f"group-{g.id}"})
        if g.hub:
            box.set("data-hub", g.hub)
        ET.SubElement(box, "rect", {
            "class": "gbox", "x": str(x), "y": str(y),
            "width": str(g.size[0]), "height": str(g.size[1]),
        })
        if g.label:
            ET.SubElement(box, "text", {
                "class": "gbox-lbl", "x": str(x + 8), "y": str(y + 14),
            }).text = g.label

    # Pipes (Schema-Reihenfolge) + Pfeil-Endpunkte (R-29).
    lp = layers["layer-pipes"]
    for p in pipes:
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
    lc = layers["layer-components"]
    for c in schema.components:
        chunk = render_component(c)
        el = ET.fromstring(chunk)
        lc.append(el)

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
        "<defs />", f"<defs>\n{render_defs()}\n</defs>", 1
    )
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def render(schema: Schema) -> str:
    """Kürzel: Layout berechnen + Dokument bauen."""
    pipes, readout_pos = compute_layout(schema)
    return build_svg(schema, pipes, readout_pos)
