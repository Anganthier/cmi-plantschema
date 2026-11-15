"""S1: place — Readout-Offset-Regel, x/y-Passthrough, Größen-Konstanten."""

from __future__ import annotations

from plantschema import place
from plantschema.model import Label, Readout


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


def test_readout_zero_offset_defaults_up():
    r = Readout.model_validate(
        {"id": "a6", "at": {"comp": "p", "port": "in"}, "label": "a6"}
    )
    # `tap`-Port `in` = (0,-7) → Achse null, Offset (0,-7) → up.
    pos = place.readout_position(r, (300, 300), "tap")
    assert pos == (300, 300 - 7 - place.PLACE_OUTER)


def test_label_position_exact_at():
    lbl = Label.model_validate({"id": "z", "at": [42, 7], "text": "P"})
    assert place.label_position(lbl) == (42, 7)


def test_font_size_constants_kanon():
    # S3-Kanon: Wert ≥ 12 px, Label ≥ 11 px.
    assert place.VALUE_FONT_MIN == 12
    assert place.LABEL_FONT_MIN == 11
    assert place.VALUE_FONT >= place.VALUE_FONT_MIN
    assert place.LABEL_FONT >= place.LABEL_FONT_MIN


def test_place_outer_constant():
    assert place.PLACE_OUTER == 16
