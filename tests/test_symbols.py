"""S2: symbols — P&ID-Katalog (18 Symbole), Port-Katalog, render_component."""

from __future__ import annotations

import re

import pytest
from conftest import fx

from plantschema import symbols
from plantschema.io import load_schema
from plantschema.model import Component, Schema
from plantschema.route import port_position

SYMBOL_IDS = (
    "pid-tank-buffer",
    "pid-boiler-oil",
    "pid-boiler-solid",
    "pid-collector-solar",
    "pid-heatex-plate",
    "pid-heatex-shell",
    "pid-mixing",
    "pid-pump-cent",
    "pid-valve-2way",
    "pid-valve-3way",
    "pid-valve-globe",
    "pid-valve-actuator",
    "pid-throttle",
    "pid-radiator",
    "pid-tap",
    "pid-chimney",
    "pid-pt",
    "pid-flow-switch",
)


def test_render_defs_contains_all_18_symbols():
    defs = symbols.render_defs()
    for sym in SYMBOL_IDS:
        assert f'id="{sym}"' in defs, f"{sym} fehlt in render_defs()"
        # <g>-Struktur: offene + geschlossene Tag.
        assert f"<g id=\"{sym}\">" in defs
    assert defs.count("<g id=") == 18
    # Demo-Block (cmi-intern) wird NICHT portiert.
    assert "pid-demo" not in defs


def test_render_defs_deterministic():
    assert symbols.render_defs() == symbols.render_defs()


def test_render_component_uses_pid_symbol():
    c = Component.model_validate(
        {"id": "p1", "type": "pump", "at": [100, 200],
         "label": {"text": "O1"}, "loop": "A", "flow": "a-vl"}
    )
    out = symbols.render_component(c)
    assert '<g id="comp-p1" data-type="pump" data-loop="A" ' \
           'data-flow="a-vl" data-symbol="pid-pump-cent">' in out
    assert '<use href="#pid-pump-cent" x="100" y="200" class="sym"/>' in out
    # Label oben über dem Symbol (LABEL_OFFSET: halbe Höhe + 12).
    assert f'<text class="txt-h" x="100" y="{200 - symbols.LABEL_OFFSET["pump"]}" ' \
           'text-anchor="middle">O1</text>' in out
    assert "</g>" in out and out.count("<g ") == 1


def test_render_component_label_sub_and_escaping():
    c = Component.model_validate(
        {"id": "h2", "type": "boiler-oil", "at": [430, 235],
         "label": {"text": "H2 · Öl", "sub": "O5 ⚠ RISK"}}
    )
    out = symbols.render_component(c)
    assert f'y="{235 - symbols.LABEL_OFFSET["boiler-oil"]}"' in out
    assert ">H2 · Öl</" in out
    assert "O5 ⚠ RISK" in out


def test_render_component_placeholder_fallback():
    c = Component.model_validate(
        {"id": "x", "type": "flying-carpet", "at": [10, 10]}
    )
    out = symbols.render_component(c)
    assert 'data-symbol="placeholder"' in out
    assert "<use" not in out
    assert '<rect class="comp-ph" x="-10" y="-10" width="40" height="40" rx="4"/>' \
        in out


def test_type_symbol_mapping_1to1_and_valve_alias():
    for t in ("tank-buffer", "boiler-oil", "boiler-solid", "collector-solar",
              "heatex-plate", "heatex-shell", "mixing", "pump", "valve-2way",
              "valve-3way", "valve-globe", "valve-actuator", "throttle",
              "radiator", "tap", "chimney", "pt", "flow-switch"):
        assert symbols.symbol_id(t).startswith("pid-")
    assert symbols.symbol_id("valve") == "pid-valve-2way"
    assert symbols.symbol_id("pump") == "pid-pump-cent"
    with pytest.raises(KeyError):
        symbols.symbol_id("flying-carpet")
    assert symbols.is_known_type("valve")
    assert not symbols.is_known_type("flying-carpet")


def test_port_catalog_covers_s1_and_new_valve_variants():
    # Alle S1-Typen (Tank/Pumpe/Ventil/HE/Radiator/Kollektor/Schornstein/
    # Zapf/PT/Flow-Schalter) + S2-Neu: valve-actuator, throttle, mixing,
    # valve-globe, valve-3way, heatex-shell.
    for t in ("tank-buffer", "boiler-oil", "boiler-solid", "pump",
              "valve-2way", "valve-3way", "valve-globe", "valve-actuator",
              "heatex-plate", "heatex-shell", "mixing", "radiator",
              "collector-solar", "chimney", "tap", "pt", "flow-switch",
              "throttle"):
        assert t in symbols.COMPONENT_PORTS
    # Valve-Alias nutzt valve-2way-Geometrie.
    assert symbols.port_names("valve") == {"in", "out", "stem"}
    assert symbols.port_offset("valve", "in").dx == -20
    # Readout-Hosts ohne Pipe-Port.
    assert symbols.COMPONENT_PORTS["pt"] == ()
    assert symbols.COMPONENT_PORTS["flow-switch"] == ()


def test_port_offsets_stem_endpoints():
    """Port-Endpunkte = Stiel-Enden des cmi-Symbols (±20, s. R-30)."""
    assert symbols.port_offset("pump", "in") == \
        symbols.PortGeometry("in", -20, 0, "left")
    assert symbols.port_offset("pump", "out") == \
        symbols.PortGeometry("out", 20, 0, "right")
    assert symbols.port_offset("valve-2way", "in").dx == -20
    assert symbols.port_offset("valve-2way", "out").dx == 20
    # valve-2way: Stiel oben (0,−20) (cmi: Stielett y=−18, Stiel-Ende −15
    # → Kanon-Endpunkt −20).
    assert symbols.port_offset("valve-2way", "stem") == \
        symbols.PortGeometry("stem", 0, -20, "up")
    # valve-3way: Schenkel unten (0,+20).
    assert symbols.port_offset("valve-3way", "mix") == \
        symbols.PortGeometry("mix", 0, 20, "down")
    # cmi-Referenz (loop-svg.js): Collector-Enden ±41, Heatex-Plate ±35,
    # Shell ±30, Mixing/Tap ±14, Radiator ±30.
    assert symbols.port_offset("collector-solar", "in").dx == -41
    assert symbols.port_offset("collector-solar", "out").dx == 41
    assert symbols.port_offset("heatex-plate", "in").dx == -35
    assert symbols.port_offset("heatex-shell", "out").dx == 30
    assert symbols.port_offset("heatex-shell", "bottom").dy == 20
    assert symbols.port_offset("mixing", "in").dx == -14
    assert symbols.port_offset("tap", "in").dx == -14
    assert symbols.port_offset("radiator", "out").dx == 30


def test_tank_geometry_cmi_reference():
    """Tank: x=±30, y=±60; Zone-Linien y=±20 (cmi loop-svg.js-Kanon)."""
    assert symbols.port_offset("tank-buffer", "top") == \
        symbols.PortGeometry("top", 0, -60, "up")
    assert symbols.port_offset("tank-buffer", "bottom") == \
        symbols.PortGeometry("bottom", 0, 60, "down")
    assert symbols.port_offset("tank-buffer", "mid-top").dy == -20
    assert symbols.port_offset("tank-buffer", "mid-bottom").dy == 20
    assert symbols.port_offset("tank-buffer", "left") == \
        symbols.PortGeometry("left", -30, 0, "left")
    assert symbols.port_offset("tank-buffer", "right") == \
        symbols.PortGeometry("right", 30, 0, "right")


def test_pipe_endpoints_hit_port_positions_exactly():
    """Port-Endpunkt-Regel (S4N-2-QA): Pipe-Endpunkt = comp.at + offset.

    Fixture: alle Komponententypen mit typischen Ports — für jede
    End-Position gilt exakt `absolut = at + Port-Offset` (Katalog).
    """
    Schema.model_validate({
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [
            {"id": "p", "type": "tank-buffer", "at": [500, 250]},
            {"id": "h1", "type": "boiler-solid", "at": [130, 210]},
            {"id": "h2", "type": "boiler-oil", "at": [130, 330]},
            {"id": "h3", "type": "collector-solar", "at": [640, 80]},
            {"id": "o1", "type": "pump", "at": [250, 170]},
            {"id": "o3", "type": "valve-3way", "at": [470, 210]},
            {"id": "o9", "type": "valve-globe", "at": [560, 420]},
            {"id": "o8", "type": "valve-actuator", "at": [470, 130]},
            {"id": "o2", "type": "valve-2way", "at": [610, 290]},
            {"id": "rm1", "type": "throttle", "at": [640, 380]},
            {"id": "r1", "type": "radiator", "at": [680, 320]},
            {"id": "w", "type": "heatex-plate", "at": [560, 290]},
            {"id": "ps", "type": "heatex-shell", "at": [350, 450]},
            {"id": "mx", "type": "mixing", "at": [430, 420]},
            {"id": "e1", "type": "chimney", "at": [130, 80]},
            {"id": "zapf", "type": "tap", "at": [700, 230]},
        ],
    })
    # (typ, at, port, erwarteter absoluter Punkt) — exakt 2× gegen
    # cmi-Referenzwerte (Tank ±30/±60, Zone-Linien ±20; Stiel-Enden ±20).
    cases = [
        ("tank-buffer", (500, 250), "top", (500, 190)),
        ("tank-buffer", (500, 250), "bottom", (500, 310)),
        ("tank-buffer", (500, 250), "left", (470, 250)),
        ("tank-buffer", (500, 250), "right", (530, 250)),
        ("tank-buffer", (500, 250), "mid-top", (500, 230)),
        ("tank-buffer", (500, 250), "mid-bottom", (500, 270)),
        ("pump", (250, 170), "in", (230, 170)),
        ("pump", (250, 170), "out", (270, 170)),
        ("valve-2way", (610, 290), "in", (590, 290)),
        ("valve-2way", (610, 290), "out", (630, 290)),
        ("valve-2way", (610, 290), "stem", (610, 270)),
        ("boiler-oil", (130, 330), "right", (158, 330)),
        ("boiler-oil", (130, 330), "top", (130, 304)),
        ("collector-solar", (640, 80), "in", (599, 80)),
        ("heatex-plate", (560, 290), "out", (595, 290)),
        ("radiator", (680, 320), "in", (650, 320)),
    ]
    for typ, at, port, expected in cases:
        assert port_position(typ, at, port) == expected, (
            f"{typ}.{port} @ {at}: erwartet {expected}, "
            f"Port-Endpunkt-Regel verletzt"
        )
    # Und: Pipe-Endpunkte der S2-Fixture (rich) liegen exakt auf Ports.
    rich = load_schema(fx("rich"))
    comps = {c.id: c for c in rich.components}
    for p in rich.pipes:
        for ref in (p.from_, p.to):
            comp = comps[ref.comp]
            off = symbols.port_offset(comp.type, ref.port)
            expected = (comp.at[0] + off.dx, comp.at[1] + off.dy)
            assert port_position(comp.type, comp.at, ref.port) == expected
            # Port muss im (Override-geprägten) Set existieren (R-9):
            assert ref.port in symbols.allowed_ports(comp.type, comp.ports)


def test_symbol_ids_unique():
    defs = symbols.render_defs()
    ids = re.findall(r'<g id="(pid-[a-z0-9-]+)"', defs)
    assert len(ids) == len(set(ids)) == 18
