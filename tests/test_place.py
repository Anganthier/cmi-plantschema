"""place — Readout-Offset, x/y-Passthrough, S3-Slot-Regeln (R-32/R-33)."""

from __future__ import annotations

from plantschema import place
from plantschema.model import Label, Readout, Schema


def test_readout_offset_outside_port():
    r = Readout.model_validate(
        {"id": "a6", "at": {"comp": "h", "port": "left"}, "label": "a6"}
    )
    pos = place.readout_position(r, (200, 300), "boiler-oil")
    # Port left = (172,300), Achse left → 16 px nach außen.
    assert pos == (172 - place.PLACE_OUTER, 300)


def test_readout_offset_top_axis():
    r = Readout.model_validate(
        {"id": "a6", "at": {"comp": "h", "port": "top"}, "label": "a6"}
    )
    pos = place.readout_position(r, (200, 300), "boiler-oil")
    # Port top = (200,274), Achse up → 16 px nach oben.
    assert pos == (200, 274 - place.PLACE_OUTER)


def test_readout_xy_passthrough():
    r = Readout.model_validate(
        {"id": "a6", "at": {"x": 123, "y": 45}, "label": "a6"}
    )
    assert place.readout_position(r, (200, 300), "boiler-oil") == (123, 45)


def test_axis_direction_defaults():
    """R-11: Achse None → Richtung des Offsets; Offset (0,0) → nach oben."""
    assert place._axis_direction(None, (0, -7)) == (0, -1)
    assert place._axis_direction(None, (0, 0)) == (0, -1)
    assert place._axis_direction(None, (5, 0)) == (1, 0)
    assert place._axis_direction(None, (0, 9)) == (0, 1)
    assert place._axis_direction("up", (0, -20)) == (0, -1)
    assert place._axis_direction("down", (0, 20)) == (0, 1)
    assert place._axis_direction("left", (-20, 0)) == (-1, 0)
    assert place._axis_direction("right", (20, 0)) == (1, 0)


def test_readout_offset_left_axis():
    r = Readout.model_validate(
        {"id": "a6", "at": {"comp": "h", "port": "in"}, "label": "a6"}
    )
    # pump-Port in = (−20,0), Achse left → 16 px nach außen.
    pos = place.readout_position(r, (300, 300), "pump")
    assert pos == (300 - 20 - place.PLACE_OUTER, 300)


def test_label_position_exact_at():
    s = Schema.model_validate({
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
    })
    lbl = Label.model_validate({"id": "z", "at": [42, 7], "text": "P"})
    assert place.label_position(lbl, s) == (42, 7)


def test_font_size_constants_kanon():
    # S3-Kanon: Wert ≥ 12 px, Label ≥ 11 px.
    assert place.VALUE_FONT_MIN == 12
    assert place.LABEL_FONT_MIN == 11
    assert place.VALUE_FONT >= place.VALUE_FONT_MIN
    assert place.LABEL_FONT >= place.LABEL_FONT_MIN


def test_place_outer_constant():
    assert place.PLACE_OUTER == 16


def test_slot_dist_constants_kanon():
    # R-32: 8 px zu Pipes/Symbol-BBox, 4 px zu anderen Text-BBs.
    assert place.SLOT_DIST == 8.0
    assert place.SLOT_TEXT_DIST == 8.0
    assert place.TEXT_DIST == 4.0
    assert place.SLOT_DIR_ORDER == ("up", "right", "down", "left")


def _schema(**overrides) -> Schema:
    base = {
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [],
        "pipes": [],
        "readouts": [],
        "labels": [],
    }
    base.update(overrides)
    return Schema.model_validate(base)


def test_slot_position_up_uses_symbol_edge():
    # tank-buffer @ (500,300): BBox top = 300−60 = 240 → Slot = 240−8 = 232,
    # x = BBox-Mitte = 500 (R-32: Symbol-Kante + 8 px).
    assert place.slot_positions("tank-buffer", (500, 300), 4) == (500, 232)


def test_slot_position_right_offset_16px():
    # right-Kante = 530, +16 px (Readout-`side`-Kanon, R-32).
    assert place.slot_positions(
        "tank-buffer", (500, 300), 4, direction="right"
    ) == (546, 300)


def test_label_at_override_wins():
    s = _schema(
        components=[{"id": "p", "type": "tank-buffer", "at": [500, 300]}],
        labels=[{"id": "z", "at": [10, 10], "comp": "p", "text": "Z"}],
    )
    pos, anchor = place.resolve_label(s.labels[0], s)
    assert pos == (10, 10) and anchor == "start"


def test_label_auto_slot_prefers_up():
    s = _schema(
        components=[{"id": "p", "type": "tank-buffer", "at": [500, 300]}],
        labels=[{"id": "z", "comp": "p", "text": "P-Oben"}],
    )
    pos, anchor = place.resolve_label(s.labels[0], s)
    # up-Slot: x = 500 (BBox-Mitte), y = 300−60−8 = 232, anchor=middle.
    assert pos == (500, 232)
    assert anchor == "middle"


def test_label_slot_skips_occupied_up_takes_right():
    # up-Slot wird durch einen festen Label-Text blockiert (< 4 px) →
    # right-Slot.
    s = _schema(
        components=[{"id": "p", "type": "tank-buffer", "at": [500, 300]}],
        labels=[
            {"id": "blocker", "at": [500, 230],
             "text": "Sehr langes Textlabel hier", "anchor": "middle"},
            {"id": "z", "comp": "p", "text": "P-Rechts"},
        ],
    )
    pos, anchor = place.resolve_label(s.labels[1], s)
    # right-Slot: x = 530+16 = 546, y = BBox-Mitte = 300, anchor=start.
    assert pos == (546, 300)
    assert anchor == "start"


def test_label_slot_avoids_pipe():
    # Pipe (y=230) quer vor dem up-Slot (Text-BBox 220–236) → up kollidiert
    # (< 8 px) → right-Slot. Pipe-Endpunkte = reale Komponenten-Ports.
    s = _schema(
        components=[
            {"id": "p", "type": "tank-buffer", "at": [500, 300]},
            {"id": "a", "type": "tank-buffer", "at": [300, 230]},
            {"id": "b", "type": "tank-buffer", "at": [700, 230]},
        ],
        pipes=[{
            "id": "b",
            "from": {"comp": "a", "port": "right"},
            "to": {"comp": "b", "port": "left"},
            "kind": "vl",
        }],
        labels=[{"id": "z", "comp": "p", "text": "P-Slot"}],
    )
    pos, anchor = place.resolve_label(s.labels[0], s)
    # up-Text-BBox (y 220.1–235.5) < 8 px zur Pipe y=230 → right-Slot.
    assert pos == (546, 300)
    assert anchor == "start"


def test_label_slot_avoids_other_symbol_box():
    # Zweite Tank-Komponente direkt über der ersten → up kollidiert (Symbol
    # -BBox-Abstand < 8 px) → next Slot.
    s = _schema(
        components=[
            {"id": "p", "type": "tank-buffer", "at": [500, 300]},
            {"id": "q", "type": "tank-buffer", "at": [500, 180]},
        ],
        labels=[{"id": "z", "comp": "p", "text": "P-Slot"}],
    )
    pos, _ = place.resolve_label(s.labels[0], s)
    assert pos != (500, 232)  # up ist blockiert


def test_all_slots_collide_falls_back_to_up_with_warning():
    # Enges Tank-Raster: alle 4 Slots < 8 px zu Symbol-BBoxes (R-33-Fall).
    s = _schema(
        components=[
            {"id": "p", "type": "tank-buffer", "at": [500, 300]},
            {"id": "n", "type": "tank-buffer", "at": [500, 160]},
            {"id": "s", "type": "tank-buffer", "at": [500, 430]},
            {"id": "w", "type": "tank-buffer", "at": [409, 300]},
            {"id": "e", "type": "tank-buffer", "at": [591, 300]},
        ],
        labels=[{"id": "z", "comp": "p", "text": "P"}],
    )
    lbl = s.labels[0]
    pos, anchor = place.resolve_label(lbl, s)
    # R-33: up-Position + Warning.
    assert pos == (500, 232)
    assert anchor == "middle"
    warnings = place.collect_slot_warnings(s)
    z = [w for w in warnings if w.elem_id == "lbl-z"]
    assert len(z) == 1
    assert z[0].comp_id == "p"
    assert z[0].direction == "up"
    assert (z[0].x, z[0].y) == (500, 232)
    assert "R-33" in z[0].note


def test_component_label_warning_all_slots_blocked():
    # Komponenten-Label im gleichen Engraster → R-33-Warning.
    s = _schema(
        components=[
            {"id": "p", "type": "tank-buffer", "at": [500, 300],
             "label": {"text": "Puff"}},
            {"id": "n", "type": "tank-buffer", "at": [500, 160]},
            {"id": "s", "type": "tank-buffer", "at": [500, 430]},
            {"id": "w", "type": "tank-buffer", "at": [409, 300]},
            {"id": "e", "type": "tank-buffer", "at": [591, 300]},
        ],
    )
    warnings = place.collect_slot_warnings(s)
    comp_w = [w for w in warnings if w.elem_id == "comp-p.lbl"]
    assert len(comp_w) == 1
    assert comp_w[0].comp_id == "p"
    assert (comp_w[0].x, comp_w[0].y) == (500, 232)


def test_label_comp_model_fields():
    # S3-Modell: Label.comp/port optional, `at` optional (R-32).
    lbl = Label.model_validate(
        {"id": "z", "comp": "p", "port": "top", "text": "P"}
    )
    assert lbl.at is None and lbl.comp == "p" and lbl.port == "top"
    lbl2 = Label.model_validate({"id": "z", "at": [1, 2], "text": "P"})
    assert lbl2.comp is None and lbl2.port is None


def test_label_unknown_host_no_position():
    s = _schema(labels=[{"id": "z", "comp": "ghost", "text": "P"}])
    pos, anchor = place.resolve_label(s.labels[0], s)
    assert pos is None
    assert anchor == "start"  # label.anchor-Default


def test_component_label_offset_up_slot_rule():
    # R-32 up-Slot: 1 Zeile = halbe Höhe + 8 px; 2 Zeilen = halbe Höhe + 20.
    assert place.component_label_offset("tank-buffer", (500, 300), 1) == 68
    assert place.component_label_offset("tank-buffer", (500, 300), 2) == 80
    # Unknown-Type → Platzhalter-Box (±20).
    assert place.component_label_offset("flying-carpet", (10, 10), 1) == 28
