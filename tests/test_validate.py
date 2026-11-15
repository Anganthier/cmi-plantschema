"""S1-3: Validierung (alle Problem-Codes auf den Fixtures)."""

from __future__ import annotations

from plantschema import validate
from plantschema.model import Schema
from plantschema.validate import MIN_CANVAS, Problem, problem_lines


def test_minimal_fixture_is_valid(minimal_schema):
    assert validate.validate(minimal_schema) == []


def test_bad_refs_fixture_produces_two_problems():
    from conftest import fx

    from plantschema.io import load_schema

    s = load_schema(fx("invalid"))
    problems = validate.validate(s)
    assert len(problems) == 2
    codes = {p.code for p in problems}
    assert codes == {"dup-id", "ref-component"}


def test_dup_id_reported_at_second_occurrence():
    s = _schema(
        components=[
            {"id": "p", "type": "pump", "at": [0, 0]},
            {"id": "p", "type": "pump", "at": [10, 0]},
        ]
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["dup-id"]
    assert "components[1].id" in problems[0].path


def test_pipe_ref_missing_component():
    s = _schema(
        components=[{"id": "p", "type": "pump", "at": [0, 0]}],
        pipes=[{
            "id": "b",
            "from": {"comp": "ghost", "port": "in"},
            "to": {"comp": "p", "port": "out"},
            "kind": "vl",
        }],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["ref-component"]
    assert "ghost" in problems[0].message


def test_pipe_ref_unknown_port():
    s = _schema(
        components=[{"id": "p", "type": "pump", "at": [0, 0]}],
        pipes=[{
            "id": "b",
            "from": {"comp": "p", "port": "top"},
            "to": {"comp": "p", "port": "out"},
            "kind": "vl",
        }],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["ref-port"]
    assert "pump" in problems[0].message


def test_readout_missing_component():
    s = _schema(
        components=[{"id": "p", "type": "pump", "at": [0, 0]}],
        readouts=[
            {"id": "a6", "at": {"comp": "ghost", "port": "in"}, "label": "a6"},
        ],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["ref-component"]


def test_readout_unknown_port():
    s = _schema(
        components=[{"id": "p", "type": "pump", "at": [0, 0]}],
        readouts=[
            {"id": "a6", "at": {"comp": "p", "port": "top"}, "label": "a6"},
        ],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["ref-port"]


def test_readout_xy_out_of_canvas():
    s = _schema(
        readouts=[{"id": "a6", "at": {"x": 801, "y": 10}, "label": "a6"}],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["out-of-canvas"]
    assert "außerhalb" in problems[0].message


def test_label_out_of_canvas():
    s = _schema(labels=[{"id": "z", "at": [801, 501], "text": "rand"}])
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["out-of-canvas"]
    assert "labels[id=z].at" in problems[0].path


def test_label_on_canvas_edge_ok():
    # x == width / y == height = auf dem Rand, erlaubt (nur > ist Problem).
    s = _schema(labels=[{"id": "z", "at": [800, 500], "text": "rand"}])
    problems = [p for p in validate.validate(s) if p.code == "out-of-canvas"]
    assert problems == []


def test_canvas_too_small():
    s = _schema(canvas={"width": 50, "height": 500})
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["canvas-too-small"]
    assert MIN_CANVAS == 100


def test_unknown_component_type():
    s = _schema(components=[{"id": "x", "type": "flying-carpet", "at": [0, 0]}])
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["unknown-type"]


def test_ports_override_unknown_port_rejected():
    s = _schema(components=[
        {"id": "p", "type": "pump", "at": [0, 0], "ports": ["in", "flue"]},
    ])
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["ref-port"]
    assert "flue" in problems[0].message


def test_ports_override_restricts_pipe_ports():
    s = _schema(
        components=[
            {"id": "p", "type": "pump", "at": [0, 0], "ports": ["out"]},
            {"id": "q", "type": "pump", "at": [100, 0]},
        ],
        pipes=[{
            "id": "b",
            "from": {"comp": "p", "port": "in"},
            "to": {"comp": "q", "port": "out"},
            "kind": "vl",
        }],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["ref-port"]


def test_all_problems_reported_not_just_first():
    s = _schema(
        components=[
            {"id": "p", "type": "pump", "at": [0, 0]},
            {"id": "p", "type": "pump", "at": [0, 0]},
        ],
        canvas={"width": 90, "height": 500},
        labels=[{"id": "z", "at": [800, 500], "text": "z"}],
    )
    problems = validate.validate(s)
    codes = [p.code for p in problems]
    assert len(problems) == 3
    assert "dup-id" in codes
    assert "canvas-too-small" in codes
    assert "out-of-canvas" in codes


def test_problem_dataclass_and_lines():
    p = Problem("dup-id", "doppelte ID", "components[1].id")
    assert p.line() == "components[1].id: doppelte ID"
    assert problem_lines([p]) == [p.line()]


def test_label_placement_both_or_neither():
    """S3 (R-32): weder `at` noch `comp` → `label-placement`."""
    s = _schema(labels=[{"id": "z", "text": "nur-Text"}])
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["label-placement"]
    assert "labels[id=z]" in problems[0].path


def test_label_comp_ref_missing_component():
    s = _schema(
        labels=[{"id": "z", "comp": "ghost", "text": "Z"}],
    )
    problems = validate.validate(s)
    codes = [p.code for p in problems]
    assert "label-comp-ref" in codes
    assert "labels[0].comp" in [p.path for p in problems if p.code == "label-comp-ref"][0]


def test_label_port_ref_invalid_port():
    s = _schema(
        components=[{"id": "p", "type": "pump", "at": [0, 0]}],
        labels=[{"id": "z", "comp": "p", "port": "flue", "text": "Z"}],
    )
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["label-port-ref"]
    assert "labels[0].port" in problems[0].path


def test_label_comp_with_port_valid():
    s = _schema(
        components=[{"id": "p", "type": "tank-buffer", "at": [100, 100]}],
        labels=[{"id": "z", "comp": "p", "port": "top", "text": "Z"}],
    )
    assert validate.validate(s) == []


def test_label_at_out_of_canvas_still_checked():
    s = _schema(labels=[{"id": "z", "at": [801, 10], "text": "rand"}])
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["out-of-canvas"]
    assert "labels[id=z].at" in problems[0].path


def _schema(**overrides) -> Schema:
    base = {
        "version": "plantschema/v1",
        "canvas": {"width": 800, "height": 500},
        "components": [],
        "pipes": [],
        "groups": [],
        "readouts": [],
        "labels": [],
    }
    base.update(overrides)
    return Schema.model_validate(base)


# ------------------------------------------------------------ S4-L1 (R-35):
# Group-Problem-Codes (group-id-duplicate, group-member-ref,
# group-hub-ref, group-hub-not-member, group-double-membership,
# group-geometry).


def _pump(i: int) -> dict:
    return {"id": f"p{i}", "type": "pump", "at": [100 * i + 50, 100]}


def test_group_id_duplicate():
    s = _schema(
        components=[_pump(1)],
        groups=[
            {"id": "g", "members": ["p1"], "at": [0, 0], "size": [100, 100]},
            {"id": "g", "members": ["p1"], "at": [0, 0], "size": [100, 100]},
        ],
    )
    problems = [p for p in validate.validate(s) if p.code == "group-id-duplicate"]
    assert len(problems) == 1
    assert "groups[1].id" in problems[0].path


def test_group_id_duplicate_cross_kind_stays_dup_id():
    # R-5: ID-Kollision Group×Pipe bleibt `dup-id` (nur Group×Group =
    # `group-id-duplicate`).
    s = _schema(
        pipes=[{
            "id": "g",
            "from": {"comp": "p1", "port": "in"},
            "to": {"comp": "p1", "port": "out"},
            "kind": "vl",
        }],
        components=[_pump(1)],
        groups=[{"id": "g", "members": ["p1"], "at": [0, 0], "size": [100, 100]}],
    )
    codes = [p.code for p in validate.validate(s)]
    assert "dup-id" in codes
    assert "group-id-duplicate" not in codes


def test_group_member_ref_missing_component():
    s = _schema(
        groups=[
            {"id": "g1", "members": ["p1", "ghost"], "at": [0, 0],
             "size": [100, 100]},
        ],
        components=[_pump(1)],
    )
    problems = [p for p in validate.validate(s) if p.code == "group-member-ref"]
    assert len(problems) == 1
    assert "ghost" in problems[0].message
    assert "groups[0].members" in problems[0].path


def test_group_hub_ref_missing_component():
    s = _schema(
        components=[_pump(1)],
        groups=[
            {"id": "g1", "members": ["p1"], "hub": "ghost",
             "at": [0, 0], "size": [100, 100]},
        ],
    )
    problems = [p for p in validate.validate(s) if p.code == "group-hub-ref"]
    assert len(problems) == 1
    assert "ghost" in problems[0].message
    assert "groups[0].hub" in problems[0].path


def test_group_hub_not_member():
    s = _schema(
        components=[_pump(1), _pump(2)],
        groups=[
            {"id": "g1", "members": ["p1"], "hub": "p2",
             "at": [0, 0], "size": [100, 100]},
        ],
    )
    problems = [p for p in validate.validate(s)
                if p.code == "group-hub-not-member"]
    assert len(problems) == 1
    assert "p2" in problems[0].message
    assert "groups[0].hub" in problems[0].path


def test_group_double_membership():
    s = _schema(
        components=[_pump(1), _pump(2)],
        groups=[
            {"id": "g1", "members": ["p1", "p2"], "at": [0, 0],
             "size": [100, 100]},
            {"id": "g2", "members": ["p2"], "at": [200, 0],
             "size": [100, 100]},
        ],
    )
    problems = [p for p in validate.validate(s)
                if p.code == "group-double-membership"]
    assert len(problems) == 1
    assert "p2" in problems[0].message
    assert "groups[1].members" in problems[0].path


def test_group_geometry_size_zero():
    s = _schema(
        components=[_pump(1)],
        groups=[
            {"id": "g1", "members": ["p1"], "at": [10, 10],
             "size": [0, 100]},
        ],
    )
    problems = [p for p in validate.validate(s) if p.code == "group-geometry"]
    assert len(problems) == 1
    assert "size" in problems[0].message
    assert "groups[0].size" in problems[0].path


def test_group_geometry_at_zero_corner():
    # at = (0,0) = Box in der Canvas-Ecke → nicht > 0 (R-35: Autor-Kanon
    # verlangt Innenabstand, kein Eckpunkt).
    s = _schema(
        components=[_pump(1)],
        groups=[
            {"id": "g1", "members": ["p1"], "at": [0, 0], "size": [100, 100]},
        ],
    )
    problems = [p for p in validate.validate(s) if p.code == "group-geometry"]
    assert len(problems) == 1
    assert "at" in problems[0].message
    assert "groups[0].at" in problems[0].path


def test_group_geometry_both_fields_reported():
    s = _schema(
        components=[_pump(1)],
        groups=[
            {"id": "g1", "members": ["p1"], "at": [0, 0], "size": [100, 0]},
        ],
    )
    problems = [p for p in validate.validate(s) if p.code == "group-geometry"]
    assert len(problems) == 2
    assert {p.path for p in problems} == {"groups[0].at", "groups[0].size"}


def test_group_valid_no_problems():
    s = _schema(
        components=[_pump(1), _pump(2)],
        groups=[
            {"id": "g1", "label": "A", "members": ["p1", "p2"], "hub": "p1",
             "at": [40, 40], "size": [400, 200]},
        ],
    )
    assert validate.validate(s) == []


def test_double_membership_fixture_exit_code_problems():
    # Negativ-Fixture: p1 ∈ g1 und g2 → genau group-double-membership.
    from conftest import fx

    from plantschema.io import load_schema

    s = load_schema(fx("invalid-double-membership"))
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["group-double-membership"]
