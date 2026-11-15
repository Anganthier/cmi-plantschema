"""S1: emit — Byte-Determinismus, stabile IDs, data-Attribute, XML-Roundtrip."""

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
        "layer-readouts", "layer-labels", "arrow",
    ):
        assert expected in ids, f"{expected} fehlt in {ids}"
    # Präfix-Vertrag: alle Element-IDs gehören zu den 4 Klassen.
    prefix_ok = ("comp-", "pipe-", "readout-", "lbl-", "layer-", "canvas-", "arrow")
    for i in ids:
        assert i.startswith(prefix_ok) or i == "arrow"


def test_data_attributes(minimal_schema):
    root = ET.fromstring(_svg(minimal_schema))
    comp = root.find(f".//{NS}g[@id='comp-puffer']")
    assert comp is not None
    assert comp.get("data-type") == "tank-buffer"
    assert comp.get("data-symbol") == "placeholder"

    comp2 = root.find(f".//{NS}g[@id='comp-h2_oel']")
    assert comp2.get("data-type") == "boiler-oil"
    assert comp2.get("data-flow") is None

    pipe = root.find(f".//{NS}path[@id='pipe-b-vl']")
    assert pipe is not None
    assert pipe.get("data-kind") == "vl"
    assert pipe.get("class") == "pipe vl"
    assert pipe.get("marker-end") == "url(#arrow)"
    assert pipe.get("d") == "M200,274 L200,150 L500,150 L470,250"

    ro = root.find(f".//{NS}g[@id='readout-a6_vl']")
    assert ro is not None
    assert ro.get("data-value-key") == "vl"
    assert ro.get("data-readout") == "a6 VL"

    lbl = root.find(f".//{NS}text[@id='lbl-zone-kk']")
    assert lbl is not None
    assert lbl.get("text-anchor") == "start"
    assert lbl.get("class") == "txt"
    assert (lbl.get("x"), lbl.get("y")) == ("60", "60")


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
    assert texts and texts[0].text == "Puffer P"
    assert len(texts) == 2 and texts[1].text == "Zonen 1-3"


def test_readout_position_emitted(minimal_schema):
    root = ET.fromstring(_svg(minimal_schema))
    ro = root.find(f".//{NS}g[@id='readout-a6_vl']")
    t = ro.find(f"{NS}text")
    # Port left von h2_oil (172,300) − 16 = (156,300).
    assert (t.get("x"), t.get("y")) == ("156", "300")


def test_style_block_colors(minimal_schema):
    svg = _svg(minimal_schema)
    for color in ("#f59e0b", "#4da3ff", "#38bdf8", "#94a3b8", "#a78bfa"):
        assert color in svg
    assert "#0b1220" in svg  # canvas.background


def test_render_deterministic_via_load_and_render_twice():
    from conftest import fx

    a = load_schema(fx("minimal"))
    b = load_schema(fx("minimal"))
    assert emit.render(a) == emit.render(b)
