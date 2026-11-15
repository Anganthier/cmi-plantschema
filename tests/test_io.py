"""S1-2: YAML-Laden (Fixture → Schema; ungültiges YAML → Zeile; IO-Fehler)."""

from __future__ import annotations

import pytest

from plantschema import io
from plantschema.io import SchemaLoadError
from plantschema.model import Schema, SchemaError


def test_load_minimal_fixture(minimal_schema):
    s: Schema = minimal_schema
    assert s.version == "plantschema/v1"
    assert s.canvas.width == 800
    assert s.canvas.height == 500
    assert s.canvas.background == "#0b1220"
    assert [c.id for c in s.components] == ["puffer", "h2_oel"]
    assert s.pipes[0].from_.comp == "h2_oel"
    assert s.pipes[0].from_.port == "right"
    assert s.pipes[0].via == [(350, 300)]
    assert s.readouts[0].at.is_ref
    assert s.readouts[0].value_key == "vl"
    assert s.readouts[0].side == "left"
    assert s.labels[0].anchor.value == "start"


def test_load_missing_file(tmp_path):
    p = tmp_path / "fehlt.yaml"
    with pytest.raises(SchemaLoadError, match="nicht lesbar"):
        io.load_schema(p)


def test_load_invalid_yaml_syntax():
    with pytest.raises(SchemaLoadError) as exc_info:
        io.load_schema_text("schema: [unclosed\n  bad: yaml")
    assert exc_info.value.line is not None
    assert "ungültiges YAML" in exc_info.value.message


def test_load_empty_document():
    with pytest.raises(SchemaLoadError, match="leere YAML"):
        io.load_schema_text("# nur Kommentar\n")


def test_load_top_level_list():
    with pytest.raises(SchemaLoadError, match="Mapping"):
        io.load_schema_text("- a\n- b\n")


def test_load_model_error_carries_path():
    with pytest.raises(SchemaError) as exc_info:
        io.load_schema_text(
            "schema: plantschema/v1\n"
            "canvas: { width: 800, height: 500 }\n"
            "components:\n"
            "  - id: 'bad id'\n"
            "    type: pump\n"
            "    at: [0, 0]\n"
        )
    assert exc_info.value.path == "components.0.id"
    assert exc_info.value.message.count("Whitespace") >= 1


def test_load_model_error_line_reference():
    # list-Item-Fehler: Zeile = Startzeile des YAML-List-Items (hier Zeile 7).
    text = (
        "schema: plantschema/v1\n"
        "canvas: { width: 800, height: 500 }\n"
        "components:\n"
        "  - id: p1\n"
        "    type: pump\n"
        "    at: [0, 0]\n"
        "  - id: p2\n"
        "    type: pump\n"
        "    at: [1, 2, 3]\n"
    )
    with pytest.raises(SchemaError) as exc_info:
        io.load_schema_text(text)
    assert exc_info.value.path == "components.1.at"
    assert exc_info.value.line == 7  # Startzeile des Items `p2`


def test_load_schema_error_hierarchy():
    # SchemaLoadError ist SchemaError (CLI-Unterscheidung nur per Typ).
    assert issubclass(SchemaLoadError, SchemaError)
