"""Emissions-Stufe: SVG-Dokument-Bau (byte-deterministisch).

Regeln (Kanon, `docs/model-reference.md` § Determinismus):
- Festes Attribut-Reihenfolge (Insertion-Order, ElementTree ≥ Py3.8).
- KEIN Zeitstempel, keine Zufalls-IDs.
- Layer-Reihenfolge: Hintergrund → Pipes → Komponenten → Readouts → Labels.
- Stabile ID-Verträge: `comp-*`, `pipe-*`, `readout-*`, `lbl-*`.
- Platzhalter-Symbole: `data-symbol="placeholder"` auf der comp-* Gruppe
  (S2 tauscht gegen P&ID-<defs> aus cmi `ui/svg/pid-symbols.svg`).

Farb-Kanon: vl #f59e0b, rl #4da3ff, ww #38bdf8, gas #94a3b8, ctl #a78bfa;
Hintergrund = canvas.background (default #0b1220).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .model import Schema
from .place import label_position, readout_position
from .route import PipeGeometry, port_position, route_pipe
from .symbols import PLACEHOLDER_SYMBOLS, allowed_ports

__all__ = ["build_svg", "compute_layout", "render"]

#: SVG-Namespace (in den Root-Tag injiziert; ElementTree kennt keinen Default-NS).
_SVG_NS = "http://www.w3.org/2000/svg"

#: Font-Größen der emittierten Klassen (QA-Input, mind. 12/11 px Kanon).
TXT_FONT: int = 14
TXT_S_FONT: int = 11

_CSS = (
    ".vl{stroke:#f59e0b;fill:none}\n"
    ".rl{stroke:#4da3ff;fill:none}\n"
    ".ww{stroke:#38bdf8;fill:none}\n"
    ".gas{stroke:#94a3b8;fill:none}\n"
    ".ctl{stroke:#a78bfa;fill:none}\n"
    ".pipe{stroke-width:2}\n"
    f".txt{{fill:#e2e8f0;font-size:{TXT_FONT}px;font-family:system-ui,sans-serif}}\n"
    f".txt-s{{fill:#94a3b8;font-size:{TXT_S_FONT}px;font-family:system-ui,sans-serif}}\n"
    ".comp{stroke:#94a3b8;fill:none;stroke-width:1.8}\n"
    ".port{fill:#e2e8f0;stroke:none}\n"
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


# ---------------------------------------------------------------- placeholders


def _component_shape(el: ET.Element, ctype: str, cx: int, cy: int) -> None:
    """S1-Platzhalter-Geometrie (Rect/Kreis/Pfadsymbole, P&ID-ähnlich)."""
    info = PLACEHOLDER_SYMBOLS.get(ctype)
    w, h = (info.size if info else (20, 20))

    def shape(tag: str, **attrs: str) -> None:
        ET.SubElement(el, tag, **{"class": "comp", **attrs})

    if info and info.shape == "circle":
        r = w
        shape("circle", cx=str(cx), cy=str(cy), r=str(r))
    elif info and info.shape == "pipe-line":
        shape("rect", x=str(cx - 13), y=str(cy - 10), width="26", height="20")
        shape("line", x1="0", y1="0", x2=str(cx), y2=str(cy - 15))
        ET.SubElement(el, "circle", {"class": "comp", "cx": str(cx),
                                     "cy": str(cy - 18), "r": "3"})
    else:
        shape("rect", x=str(cx - w), y=str(cy - h), width=str(2 * w),
              height=str(2 * h), rx="4")
        # P&ID-erkennbare Zusatzlinien (deterministische Katalog-Reihenfolge):
        if ctype in ("tank-buffer", "boiler-oil", "boiler-solid", "radiator"):
            shape("line", x1=str(cx - w + 6), y1=str(cy), x2=str(cx + w - 6), y2=str(cy))
        if ctype in ("boiler-oil", "boiler-solid"):
            shape("line", x1=str(cx), y1=str(cy - h), x2=str(cx), y2=str(cy - h - 14))


def _port_dots(el: ET.Element, ctype: str, cx: int, cy: int,
               allowed: frozenset[str]) -> None:
    """Port-Markierungen (Katalog-Reihenfolge) — Visualisierung der Geometrie."""
    info = PLACEHOLDER_SYMBOLS.get(ctype)
    if info is None:
        return
    for p in info.ports:
        if p.name in allowed:
            ET.SubElement(el, "circle", {"class": "port",
                                         "cx": str(cx + p.dx),
                                         "cy": str(cy + p.dy), "r": "2"})


# ------------------------------------------------------------------- document


def build_svg(
    schema: Schema,
    pipes: list[PipeGeometry],
    readout_pos: dict[str, tuple[int, int]],
) -> str:
    """SVG-Dokument-String (byte-deterministisch)."""
    w, h = schema.canvas.width, schema.canvas.height
    root = ET.Element("svg", {"viewBox": f"0 0 {w} {h}"})

    defs = ET.SubElement(root, "defs")
    marker = ET.SubElement(defs, "marker", {
        "id": "arrow", "viewBox": "0 0 10 10", "refX": "9", "refY": "5",
        "markerWidth": "7", "markerHeight": "7",
        "orient": "auto", "markerUnits": "userSpaceOnUse",
    })
    ET.SubElement(marker, "path", {
        "d": "M0,0 L10,5 L0,10 Z", "fill": "#cbd5e1",
    })

    style = ET.SubElement(root, "style")
    style.text = _CSS

    ET.SubElement(root, "rect", {
        "id": "canvas-bg", "x": "0", "y": "0",
        "width": str(w), "height": str(h),
        "fill": schema.canvas.background,
    })

    layers: dict[str, ET.Element] = {}
    layer_names = ("layer-pipes", "layer-components", "layer-readouts", "layer-labels")
    for name in layer_names:
        layers[name] = ET.SubElement(root, "g", {"id": name})

    # Pipes (Schema-Reihenfolge).
    for p in pipes:
        attrs = {"id": f"pipe-{p.id}", "class": f"pipe {p.kind}", "d": p.d}
        attrs["data-kind"] = p.kind
        if p.flow:
            attrs["data-flow"] = p.flow
        attrs["marker-end"] = "url(#arrow)"
        ET.SubElement(layers["layer-pipes"], "path", attrs)

    # Komponenten (Schema-Reihenfolge, Platzhalter-Symbole).
    for c in schema.components:
        g = ET.SubElement(layers["layer-components"], "g", {
            "id": f"comp-{c.id}", "data-type": c.type,
            "data-symbol": "placeholder",
        })
        if c.loop:
            g.set("data-loop", c.loop)
        if c.flow:
            g.set("data-flow", c.flow)
        _component_shape(g, c.type, c.at[0], c.at[1])
        _port_dots(g, c.type, c.at[0], c.at[1],
                   allowed_ports(c.type, c.ports))
        if c.label:
            t = ET.SubElement(g, "text", {"class": "txt-s",
                                          "x": str(c.at[0]),
                                          "y": str(c.at[1] + 4)})
            t.text = c.label.text
            if c.label.sub:
                sub = ET.SubElement(g, "text", {"class": "txt-s",
                                                "x": str(c.at[0]),
                                                "y": str(c.at[1] + 16)})
                sub.text = c.label.sub

    # Readouts (Schema-Reihenfolge).
    for r in schema.readouts:
        x, y = readout_pos[r.id]
        g = ET.SubElement(layers["layer-readouts"], "g", {
            "id": f"readout-{r.id}",
        })
        if r.value_key:
            g.set("data-value-key", r.value_key)
        g.set("data-readout", r.label)
        if r.loop:
            g.set("data-loop", r.loop)
        t = ET.SubElement(g, "text", {"class": "txt", "x": str(x), "y": str(y),
                                      "text-anchor": "middle"})
        t.text = r.label

    # Labels (Schema-Reihenfolge).
    for lbl in schema.labels:
        pos = label_position(lbl)
        ET.SubElement(layers["layer-labels"], "text", {
            "id": f"lbl-{lbl.id}", "class": "txt",
            "x": str(pos[0]), "y": str(pos[1]),
            "text-anchor": lbl.anchor.value,
        }).text = lbl.text

    body = ET.tostring(root, encoding="unicode")
    body = body.replace("<svg ", f'<svg xmlns="{_SVG_NS}" ', 1)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def render(schema: Schema) -> str:
    """Kürzel: Layout berechnen + Dokument bauen."""
    pipes, readout_pos = compute_layout(schema)
    return build_svg(schema, pipes, readout_pos)
