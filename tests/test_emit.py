"""S2: emit — Byte-Determinismus, stabile IDs, P&ID-Symbole, Readout-Struktur.

Style-Klassen, Layer-Z-Order, XML-Roundtrip, side=left-Anker.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET

from plantschema import emit
from plantschema.io import load_schema
from plantschema.model import Schema

NS = "{http://www.w3.org/2000/svg}"


def _svg(minimal_schema) -> str:
    return emit.render(minimal_schema)


def test_byte_deterministic_sha256(minimal_schema):
    a = _svg(minimal_schema)
    b = _svg(minimal_schema)
    assert a == b
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(
        b.encode()
    ).hexdigest()


def test_no_timestamp_in_output(minimal_schema):
    svg = _svg(minimal_schema)
    assert "2026" not in svg
    assert "date" not in svg.lower()


def test_xml_roundtrip_parseable(minimal_schema):
    svg = _svg(minimal_schema)
    root = ET.fromstring(svg)
    assert root.tag == f"{NS}svg"
    vb = root.get("viewBox")
    assert vb == "0 0 800 500"


def test_stable_id_contracts(minimal_schema):
    root = ET.fromstring(_svg(minimal_schema))
    ids = [el.get("id") for el in root.iter() if el.get("id")]
    for expected in (
        "comp-puffer", "comp-h2_oel", "pipe-b-vl", "readout-a6_vl",
        "lbl-zone-kk", "canvas-bg", "layer-pipes", "layer-components",
        "layer-readouts", "layer-labels", "arrow", "pid-tank-buffer",
        "pid-boiler-oil", "pid-pt",
    ):
        assert expected in ids, f"{expected} fehlt in {ids}"
    # Präfix-Vertrag: alle Element-IDs gehören zu den bekannten Klassen
    # (inkl. <defs>-Inhalt: Marker + P&ID-Symbole).
    prefix_ok = ("comp-", "pipe-", "readout-", "lbl-", "layer-", "canvas-",
                 "arrow", "pid-")
    for i in ids:
        assert i.startswith(prefix_ok), f"Unerwarteter ID-Präfix: {i}"


def test_data_attributes(minimal_schema):
    root = ET.fromstring(_svg(minimal_schema))
    comp = root.find(f".//{NS}g[@id='comp-puffer']")
    assert comp is not None
    assert comp.get("data-type") == "tank-buffer"
    assert comp.get("data-symbol") == "pid-tank-buffer"

    comp2 = root.find(f".//{NS}g[@id='comp-h2_oel']")
    assert comp2.get("data-type") == "boiler-oil"
    assert comp2.get("data-flow") is None

    pipe = root.find(f".//{NS}path[@id='pipe-b-vl']")
    assert pipe is not None
    assert pipe.get("data-kind") == "vl"
    assert pipe.get("class") == "pipe vl"
    # S2: kein marker-end (Pfeil = .pipe-arrow-Endpunkt, R-29).
    assert pipe.get("marker-end") is None
    # Port-Endpunkte exakt auf Kanten: H2-right (228,300) → via (350,300)
    # → P-Left (470,250) (S4N-2-QA: Endpunkt = comp.at + Port-Offset).
    assert pipe.get("d") == "M228,300 L350,300 L470,250"
    # Pfeil-Endpunkt: eigener .pipe-arrow-Path (Fill = Kind-Farbe),
    # Spitze exakt am Pipe-Endpunkt (470,250).
    arrow = root.find(f".//{NS}path[@class='pipe-arrow arrow-vl']")
    assert arrow is not None
    assert arrow.get("d").startswith("M470,250 ")

    ro = root.find(f".//{NS}g[@id='readout-a6_vl']")
    assert ro is not None
    assert ro.get("data-value-key") == "vl"
    assert ro.get("data-readout") == "a6 VL"

    lbl = root.find(f".//{NS}text[@id='lbl-zone-kk']")
    assert lbl is not None
    assert lbl.get("text-anchor") == "start"
    assert lbl.get("class") == "txt"
    assert (lbl.get("x"), lbl.get("y")) == ("60", "60")


def test_pid_symbols_in_defs(minimal_schema):
    """Alle 18 P&ID-Symbole im <defs> (klassen-basiert .pid/.pid-t)."""
    svg = _svg(minimal_schema)
    # Regression: <defs>-Inhalt muss als Markup emittiert werden
    # (nicht XML-escapen, d. h. kein '&lt;g id=' in der Datei).
    assert "&lt;g id=" not in svg
    assert "&lt;marker" not in svg
    for sym in (
        "pid-tank-buffer", "pid-boiler-oil", "pid-boiler-solid",
        "pid-collector-solar", "pid-heatex-plate", "pid-heatex-shell",
        "pid-mixing", "pid-pump-cent", "pid-valve-2way", "pid-valve-3way",
        "pid-valve-globe", "pid-valve-actuator", "pid-throttle",
        "pid-radiator", "pid-tap", "pid-chimney", "pid-pt",
        "pid-flow-switch",
    ):
        assert f'id="{sym}"' in svg, f"{sym} fehlt im <defs>"
    # Demo-Block wird NICHT portiert.
    assert "pid-demo" not in svg
    # Klassen-basiert: .pid-Strich, .pid-t-Text.
    assert '.pid{' in svg and '.pid-t{' in svg


def test_component_uses_pid_use(minimal_schema):
    """Komponenten = <use href='#pid-…'> (kein Platzhalter-Rect)."""
    root = ET.fromstring(_svg(minimal_schema))
    comp = root.find(f".//{NS}g[@id='comp-puffer']")
    use = comp.find(f"{NS}use")
    assert use is not None
    assert use.get("href") == "#pid-tank-buffer"
    assert (use.get("x"), use.get("y")) == ("500", "250")
    assert use.get("class") == "sym"
    assert comp.find(f"{NS}rect") is None


def test_unknown_type_placeholder(minimal_schema):
    """Unbekannter Typ → S1-Platzhalter-Rect (data-symbol='placeholder').

    (Pipes auf unbekannte Typen blockt `validate` (unknown-type) vor dem
    Render — S1-Verhalten unverändert.)
    """
    s = Schema.model_validate({
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [
            {"id": "p", "type": "tank-buffer", "at": [500, 250]},
            {"id": "x", "type": "flying-carpet", "at": [200, 200],
             "label": {"text": "X"}},
        ],
        "pipes": [],
    })
    root = ET.fromstring(emit.build_svg(s, *emit.compute_layout(s)))
    comp = root.find(f".//{NS}g[@id='comp-x']")
    assert comp.get("data-symbol") == "placeholder"
    assert comp.find(f"{NS}use") is None
    rect = comp.find(f"{NS}rect")
    assert rect is not None
    assert (rect.get("x"), rect.get("y")) == ("180", "180")
    # Label (Default-Offset 32): y = 200 − 32 = 168.
    txt = comp.find(f"{NS}text")
    assert txt.get("class") == "txt-h"
    assert txt.get("y") == "168"


def test_readout_structure(minimal_schema):
    """Readout = PT-<use> + .ro-val (Platzhalter '–', data-value-Hook)
    + .ro-lbl (cmi loop-svg.js-Kanon: Wert oben, Label unten)."""
    root = ET.fromstring(_svg(minimal_schema))
    ro = root.find(f".//{NS}g[@id='readout-a6_vl']")
    use = ro.find(f"{NS}use")
    assert use is not None
    assert use.get("href") == "#pid-pt"
    # Port left von h2_oil (172,300) − 16 = (156,300).
    assert (use.get("x"), use.get("y")) == ("156", "300")
    val = ro.find(f"{NS}text[@class='ro-val']")
    assert val is not None
    assert val.text == "–"
    assert val.get("data-value") == "true"
    assert val.get("font-size") is None  # Größe per .ro-val-Klasse (12 px)
    lbl = ro.find(f"{NS}text[@class='ro-lbl']")
    assert lbl is not None
    assert lbl.text == "a6 VL"
    # side=left → 16 px links (tx = 156 − 16 = 140), text-anchor=end.
    assert val.get("x") == "140"
    assert val.get("y") == "298"
    assert val.get("text-anchor") == "end"
    assert lbl.get("x") == "140"
    assert lbl.get("y") == "314"
    assert lbl.get("text-anchor") == "end"


def test_readout_side_default_right(minimal_schema):
    """side=right (Default) → 16 px rechts, text-anchor=start."""
    s = Schema.model_validate({
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [{"id": "h", "type": "boiler-oil", "at": [300, 300]}],
        "readouts": [
            {"id": "a6", "at": {"comp": "h", "port": "left"}, "label": "a6"},
        ],
    })
    root = ET.fromstring(emit.render(s))
    ro = root.find(f".//{NS}g[@id='readout-a6']")
    val = ro.find(f"{NS}text[@class='ro-val']")
    # Port left = (272,300) − 16 = (256,300); side=right → tx = 256+16 = 272.
    assert val.get("x") == "272"
    assert val.get("text-anchor") == "start"


def test_layer_order(minimal_schema):
    root = ET.fromstring(_svg(minimal_schema))
    children = [el.tag for el in root]
    # Hintergrund-Rect, dann die 4 Layer in fester Reihenfolge.
    layer_idx = [children.index(f"{NS}g") for _ in range(4)]
    assert layer_idx == sorted(layer_idx)
    # IDs der Layer in Dokument-Reihenfolge:
    layer_ids = [el.get("id") for el in root if el.tag == f"{NS}g"]
    assert layer_ids[:4] == [
        "layer-pipes", "layer-components", "layer-readouts", "layer-labels",
    ]


def test_pipe_flow_data_attribute():
    s = Schema.model_validate({
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [
            {"id": "h", "type": "boiler-oil", "at": [200, 300],
             "loop": "B", "flow": "loop-B"},
            {"id": "p", "type": "tank-buffer", "at": [500, 250]},
        ],
        "pipes": [{
            "id": "b",
            "from": {"comp": "h", "port": "top"},
            "to": {"comp": "p", "port": "left"},
            "kind": "vl",
            "flow": "loop-B",
        }],
    })
    root = ET.fromstring(emit.render(s))
    pipe = root.find(f".//{NS}path[@id='pipe-b']")
    assert pipe.get("data-flow") == "loop-B"
    comp = root.find(f".//{NS}g[@id='comp-h']")
    assert comp.get("data-loop") == "B"
    assert comp.get("data-flow") == "loop-B"


def test_component_label_emitted(minimal_schema):
    root = ET.fromstring(_svg(minimal_schema))
    comp = root.find(f".//{NS}g[@id='comp-puffer']")
    texts = comp.findall(f"{NS}text")
    # .txt-h (Haupt) + .txt-s (Sub), oben über dem Symbol (LABEL_OFFSET).
    assert texts[0].get("class") == "txt-h"
    assert texts[0].text == "Puffer P"
    assert len(texts) == 2 and texts[1].get("class") == "txt-s"
    assert texts[1].text == "Zonen 1-3"
    # Offset 72 (Tank): y = 250 − 72 = 178, Sub +14 = 192.
    assert (texts[0].get("x"), texts[0].get("y")) == ("500", "178")
    assert (texts[1].get("x"), texts[1].get("y")) == ("500", "192")


def test_style_block_colors_and_classes(minimal_schema):
    svg = _svg(minimal_schema)
    for color in ("#f59e0b", "#4da3ff", "#38bdf8", "#94a3b8", "#a78bfa"):
        assert color in svg
    assert "#0b1220" in svg  # canvas.background
    # S2-Style-Klassen: P&ID-Symbole, Readout, Steuer gestrichelt.
    for cls in (".pid{", ".pid-t{", ".ro-val{", ".ro-lbl{", ".txt-h{",
                ".txt-s{", ".pipe-arrow{", ".arrow-vl{", ".arrow-ctl{"):
        assert cls in svg, f"{cls} fehlt im Style-Block"
    assert "stroke-dasharray:6 4" in svg  # .ctl (cmi-Kanon)
    assert ".pipe{stroke-width:3}" in svg  # V6.3-Dicke


def test_render_deterministic_via_load_and_render_twice():
    from conftest import fx

    a = load_schema(fx("minimal"))
    b = load_schema(fx("minimal"))
    assert emit.render(a) == emit.render(b)
