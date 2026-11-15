"""S1-1: Pydantic-v2-Modelle (Typ-Fehler, Canvas-Bereich, Port-Form)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plantschema.model import (
    Canvas,
    Component,
    Label,
    Pipe,
    PipeKind,
    PortRef,
    Readout,
    Schema,
    SchemaError,
    TextAnchor,
    check_id,
    check_point,
)


def test_schema_valid_minimal():
    s = Schema.model_validate({
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [{"id": "p", "type": "tank-buffer", "at": [100, 100]}],
        "pipes": [],
        "readouts": [],
        "labels": [],
    })
    assert s.canvas.width == 800
    assert s.canvas.height == 500
    assert s.canvas.background == "#0b1220"
    assert s.component_ids == {"p"}


def test_schema_version_rejected():
    with pytest.raises(ValidationError, match="plantschema/v1"):
        Schema.model_validate({"version": "plantschema/v2",
                               "canvas": {"width": 200, "height": 200}})


def test_schema_unknown_key_rejected():
    with pytest.raises(ValidationError):
        Schema.model_validate({
            "version": "plantschema/v1",
            "canvas": {"width": 200, "height": 200},
            "extra": "nope",
        })


def test_canvas_background_invalid():
    with pytest.raises(ValidationError, match="hex-Farbe"):
        Canvas.model_validate({"width": 200, "height": 200,
                               "background": "blau"})


def test_canvas_positive_only():
    with pytest.raises(ValidationError):
        Canvas.model_validate({"width": 0, "height": 200})


def test_component_id_whitespace_rejected():
    with pytest.raises(ValidationError, match="Whitespace"):
        Component.model_validate({"id": "p 1", "type": "pump", "at": [0, 0]})


def test_component_at_must_be_two_numbers():
    with pytest.raises(ValidationError, match="genau 2 Zahlen"):
        Component.model_validate({"id": "p", "type": "pump", "at": [1, 2, 3]})


def test_component_at_negative_rejected():
    with pytest.raises(ValidationError, match=">= 0"):
        Component.model_validate({"id": "p", "type": "pump", "at": [-1, 0]})


def test_component_at_fractional_rejected():
    with pytest.raises(ValidationError, match="ganzzahlig"):
        Component.model_validate({"id": "p", "type": "pump", "at": [1.5, 0]})


def test_component_label_spec():
    c = Component.model_validate(
        {"id": "p", "type": "pump", "at": [0, 0],
         "label": {"text": "P1", "sub": "10120A"}}
    )
    assert c.label.text == "P1"
    assert c.label.sub == "10120A"


def test_pipe_from_alias_and_kind_enum():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
    })
    assert p.kind is PipeKind.VL
    assert p.from_.comp == "h"
    assert p.via is None


def test_pipe_kind_rejects_unknown():
    with pytest.raises(ValidationError):
        Pipe.model_validate({
            "id": "b",
            "from": {"comp": "h", "port": "top"},
            "to": {"comp": "p", "port": "left"},
            "kind": "heat",
        })


def test_pipe_via_points_validated():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
        "via": [[10, 20], [30, 40]],
    })
    assert p.via == [(10, 20), (30, 40)]


def test_pipe_via_rejects_three_values():
    with pytest.raises(ValidationError, match="genau 2 Zahlen"):
        Pipe.model_validate({
            "id": "b",
            "from": {"comp": "h", "port": "top"},
            "to": {"comp": "p", "port": "left"},
            "kind": "vl",
            "via": [[1, 2, 3]],
        })


def test_portref_comp_must_be_valid_id():
    with pytest.raises(ValidationError, match="Whitespace"):
        PortRef.model_validate({"comp": "h 2", "port": "top"})


def test_readout_ref_and_xy_exclusive():
    r = Readout.model_validate({
        "id": "a6", "at": {"comp": "h", "port": "top"}, "label": "a6",
    })
    assert r.at.is_ref
    r2 = Readout.model_validate(
        {"id": "a6", "at": {"x": 10, "y": 20}, "label": "a6"}
    )
    assert not r2.at.is_ref


def test_readout_mixed_ref_rejected():
    with pytest.raises(ValidationError, match="nicht beides"):
        Readout.model_validate({
            "id": "a6",
            "at": {"comp": "h", "port": "top", "x": 10, "y": 20},
            "label": "a6",
        })


def test_readout_xy_pair_rejected_partial():
    with pytest.raises(ValidationError, match="zusammen"):
        Readout.model_validate({"id": "a6", "at": {"x": 10}, "label": "a6"})


def test_label_anchor_enum():
    lbl = Label.model_validate({"id": "z", "at": [0, 0], "text": "P",
                                "anchor": "middle"})
    assert lbl.anchor is TextAnchor.MIDDLE


def test_label_at_or_comp_exclusive_semantics():
    """S3 (R-32): `at` ODER `comp` — Modell-Level: beide Felder optional;
    das Entweder-oder prüft `validate` (Problem `label-placement`)."""
    # comp-Form (ohne at):
    lbl = Label.model_validate({"id": "z", "comp": "p", "text": "P"})
    assert lbl.at is None and lbl.comp == "p" and lbl.port is None
    # comp+port-Form:
    lbl2 = Label.model_validate(
        {"id": "z", "comp": "p", "port": "top", "text": "P"}
    )
    assert lbl2.port == "top"
    # at-Form (S1-Verhalten):
    lbl3 = Label.model_validate({"id": "z", "at": [3, 4], "text": "P"})
    assert lbl3.comp is None and lbl3.at == (3, 4)


def test_label_comp_id_validation():
    with pytest.raises(ValidationError, match="Whitespace"):
        Label.model_validate({"id": "z", "comp": "p x", "text": "P"})


def test_label_port_lowercase_validation():
    with pytest.raises(ValidationError, match="label.port ungültig"):
        Label.model_validate({"id": "z", "comp": "p", "port": "Top",
                              "text": "P"})


def test_check_id_direct():
    assert check_id("a-b_c.1", "x") == "a-b_c.1"
    with pytest.raises(ValueError):
        check_id(" p", "x")


def test_check_point_direct():
    assert check_point([3, 4], "at") == (3, 4)
    with pytest.raises(ValueError):
        check_point([3], "at")


def test_schema_error_format_with_line():
    e = SchemaError("ungültig", path="canvas.width", line=4)
    assert e.format() == "[line 4] canvas.width: ungültig"
    assert e.line == 4


def test_schema_error_format_no_line():
    e = SchemaError("fehlend", path="pipes.id")
    assert e.format() == "[?] pipes.id: fehlend"
    assert e.line is None
