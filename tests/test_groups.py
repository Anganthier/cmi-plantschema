"""S4-L5a (R-38): Nested Groups — composite + includes + transitive
Mitgliedschaft (Modell, Validate-Codes, Helfer, Gate-Ausnahmen,
GROUP-CONTAINMENT, R-37-Refinement, composite-Emission, CLI-Exits)."""

from __future__ import annotations

import io as _io
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout

import pytest
from conftest import fx
from pydantic import ValidationError

from plantschema import __main__ as m
from plantschema.__main__ import EXIT_GATE, EXIT_OK, EXIT_SCHEMA
from plantschema.emit import COMPOSITE_RX, render
from plantschema.groups import (
    ancestor_groups,
    ancestor_indices,
    child_indices,
    is_composite,
    membership,
    owner_index,
    pipe_foreign_indices,
    transitive_members,
)
from plantschema.io import load_schema
from plantschema.layout import resolve
from plantschema.model import Group, Label, Schema
from plantschema.qa import TextElem, detect_collisions
from plantschema.route import schema_routes
from plantschema.validate import validate

_SVG = "{http://www.w3.org/2000/svg}"


def call(*argv: str) -> tuple[int, str]:
    out, err = _io.StringIO(), _io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = m.main(list(argv))
    return rc, err.getvalue()


def _g(gid: str, at, size, members=(), includes=(), kind="atomic", **kw) -> Group:
    return Group.model_validate({
        "id": gid, "kind": kind, "members": list(members),
        "includes": list(includes), "at": list(at), "size": list(size), **kw,
    })


def _schema(groups: list[dict], components: list[dict] | None = None,
            pipes: list[dict] | None = None,
            labels: list[dict] | None = None) -> Schema:
    return Schema.model_validate({
        "schema": "plantschema/v1",
        "canvas": {"width": 1200, "height": 800},
        "components": components or [],
        "groups": groups,
        "pipes": pipes or [],
        "labels": labels or [],
    })


def _venn() -> list[Group]:
    """c1 = {a, s}, c2 = {s, b} (s = geteiltes Kind), x = Solist."""
    return [
        _g("c1", (40, 40), (660, 360), includes=["a", "s"], kind="composite"),
        _g("c2", (400, 50), (660, 360), includes=["s", "b"], kind="composite"),
        _g("a", (60, 100), (260, 280), members=["a1"]),
        _g("s", (420, 100), (260, 280), members=["s1", "s2"]),
        _g("b", (780, 100), (260, 280), members=["b1"]),
        _g("x", (60, 500), (260, 200), members=["x1"]),
    ]


def _codes(schema: Schema) -> list[str]:
    return [p.code for p in validate(schema)]


# ------------------------------------------------------------------ Modell


def test_group_kind_defaults_atomic_and_empty_includes():
    g = _g("g1", (0, 0), (10, 10), members=["p1"])
    assert g.kind == "atomic" and g.includes == []


def test_group_members_optional_for_composite():
    g = Group.model_validate({
        "id": "c1", "kind": "composite", "includes": ["g1"],
        "at": [0, 0], "size": [10, 10],
    })
    assert g.members == [] and g.includes == ["g1"]


def test_group_kind_unknown_rejected():
    with pytest.raises(ValidationError):
        Group.model_validate({"id": "g", "kind": "nested", "at": [0, 0],
                              "size": [1, 1]})


def test_group_includes_id_validation():
    with pytest.raises(ValidationError, match="Whitespace"):
        _g("c", (0, 0), (1, 1), includes=["g 1"], kind="composite")


# ------------------------------------------------------------------ Helfer


def test_is_composite():
    gs = _venn()
    assert [is_composite(g) for g in gs] == [True, True, False, False, False, False]


def test_child_and_ancestor_indices():
    gs = _venn()
    assert child_indices(0, gs) == [2, 3]
    assert child_indices(1, gs) == [3, 4]
    assert child_indices(2, gs) == []  # atomic
    assert ancestor_indices(3, gs) == [0, 1]
    assert ancestor_indices(2, gs) == [0]
    assert ancestor_indices(5, gs) == []


def test_child_indices_defensive_skips_unknown_self_composite_dupes():
    gs = [
        _g("c1", (0, 0), (9, 9), includes=["g", "ghost", "c1", "c2", "g"],
           kind="composite"),
        _g("c2", (0, 0), (9, 9), includes=["g"], kind="composite"),
        _g("g", (1, 1), (2, 2), members=["p"]),
    ]
    assert child_indices(0, gs) == [2]


def test_transitive_members_flat():
    gs = _venn()
    assert transitive_members(gs[0], gs) == {"a1", "s1", "s2"}
    assert transitive_members(gs[1], gs) == {"s1", "s2", "b1"}
    assert transitive_members(gs[3], gs) == {"s1", "s2"}


def test_transitive_members_by_id_copy_and_unknown():
    gs = _venn()
    copy = gs[0].model_copy()
    assert transitive_members(copy, gs) == {"a1", "s1", "s2"}
    stray = _g("zz", (0, 0), (1, 1), members=["q"])
    assert transitive_members(stray, gs) == {"q"}


def test_ancestor_groups():
    gs = _venn()
    assert ancestor_groups(gs[3], gs) == {"c1", "c2"}
    assert ancestor_groups(gs[2], gs) == {"c1"}
    assert ancestor_groups(gs[5], gs) == set()
    assert ancestor_groups(gs[4].model_copy(), gs) == {"c2"}
    assert ancestor_groups(_g("zz", (0, 0), (1, 1)), gs) == set()


def test_membership_transitive():
    gs = _venn()
    assert membership("s1", gs) == {3, 0, 1}
    assert membership("a1", gs) == {2, 0}
    assert membership("x1", gs) == {5}
    assert membership("nobody", gs) == set()
    assert membership("b1", gs, owner_index(gs)) == {4, 1}


def test_pipe_foreign_indices_refinement():
    gs = _venn()
    # a → s: gemeinsamer composite c1 → dessen Kinder nicht fremd.
    assert pipe_foreign_indices("a1", "s1", gs) == [4, 5]
    # a → b: kein gemeinsamer composite → s fremd (Kanal-Detour).
    assert pipe_foreign_indices("a1", "b1", gs) == [3, 5]
    # intra-atomic / nicht-gruppig → kein Detour.
    assert pipe_foreign_indices("s1", "s2", gs) == []
    assert pipe_foreign_indices("a1", "nobody", gs) == []
    # x (ohne Eltern) → a: c2 + s + b fremd.
    assert pipe_foreign_indices("x1", "a1", gs) == [1, 3, 4]


def test_pipe_foreign_indices_without_composites_equals_r37():
    gs = [
        _g("g1", (0, 0), (10, 10), members=["p"]),
        _g("g2", (20, 0), (10, 10), members=["q"]),
        _g("g3", (40, 0), (10, 10), members=["r"]),
    ]
    assert pipe_foreign_indices("p", "q", gs) == [2]


# ---------------------------------------------------------------- Validate


_COMP = [{"id": "p1", "type": "pump", "at": [100, 200]}]


def test_validate_composite_valid():
    s = _schema([
        {"id": "c1", "kind": "composite", "includes": ["g1"],
         "at": [40, 40], "size": [400, 400]},
        {"id": "g1", "members": ["p1"], "at": [60, 60], "size": [200, 300]},
    ], _COMP)
    assert validate(s) == []


@pytest.mark.parametrize("extra, path", [
    ({"members": ["p1"]}, "groups[0].members"),
    ({"hub": "p1"}, "groups[0].hub"),
    ({"order": ["p1"]}, "groups[0].order"),
    ({"hub_at": [50, 50]}, "groups[0].hub_at"),
])
def test_validate_kind_shape_composite_container_fields(extra, path):
    s = _schema([
        {"id": "c1", "kind": "composite", "includes": ["g1"],
         "at": [40, 40], "size": [400, 400], **extra},
        {"id": "g1", "members": ["p2"], "at": [60, 60], "size": [200, 300]},
    ], [*_COMP, {"id": "p2", "type": "pump", "at": [120, 250]}])
    probs = [p for p in validate(s) if p.code == "group-kind-shape"]
    assert [p.path for p in probs] == [path]


def test_validate_kind_shape_composite_without_includes():
    s = _schema([{"id": "c1", "kind": "composite", "at": [40, 40],
                  "size": [400, 400]}])
    assert _codes(s) == ["group-kind-shape"]
    assert validate(s)[0].path == "groups[0].includes"


def test_validate_kind_shape_atomic_with_includes():
    s = _schema([
        {"id": "g0", "members": ["p1"], "includes": ["g1"],
         "at": [40, 40], "size": [400, 400]},
        {"id": "g1", "members": [], "at": [60, 60], "size": [200, 300]},
    ], _COMP)
    assert _codes(s) == ["group-kind-shape"]


def test_validate_include_ref():
    s = _schema([{"id": "c1", "kind": "composite", "includes": ["nope"],
                  "at": [40, 40], "size": [400, 400]}])
    assert _codes(s) == ["group-include-ref"]


def test_validate_include_composite_depth_max_1():
    s = _schema([
        {"id": "c0", "kind": "composite", "includes": ["c1"],
         "at": [20, 20], "size": [600, 600]},
        {"id": "c1", "kind": "composite", "includes": ["g1"],
         "at": [40, 40], "size": [400, 400]},
        {"id": "g1", "members": ["p1"], "at": [60, 60], "size": [200, 300]},
    ], _COMP)
    assert _codes(s) == ["group-include-composite"]


def test_validate_include_cycle():
    s = _schema([
        {"id": "c0", "kind": "composite", "includes": ["c1"],
         "at": [20, 20], "size": [600, 600]},
        {"id": "c1", "kind": "composite", "includes": ["c0"],
         "at": [40, 40], "size": [400, 400]},
    ])
    codes = _codes(s)
    assert codes.count("group-include-cycle") == 2
    assert codes.count("group-include-composite") == 2


def test_validate_self_include_cycle():
    s = _schema([{"id": "c0", "kind": "composite", "includes": ["c0"],
                  "at": [20, 20], "size": [600, 600]}])
    assert "group-include-cycle" in _codes(s)


def test_validate_cycle_detection_terminates_on_shared_paths():
    # Diamant ohne Zyklus (mehrfach erreichbarer Knoten) → kein Cycle.
    s = _schema([
        {"id": "c0", "kind": "composite", "includes": ["g1", "g2"],
         "at": [20, 20], "size": [600, 600]},
        {"id": "g1", "members": ["p1"], "includes": ["g3"],
         "at": [40, 40], "size": [200, 200]},
        {"id": "g2", "members": [], "includes": ["g3"],
         "at": [300, 40], "size": [200, 200]},
        {"id": "g3", "members": [], "at": [40, 300], "size": [100, 100]},
    ], _COMP)
    assert "group-include-cycle" not in _codes(s)


@pytest.mark.parametrize("name, code", [
    ("invalid-group-kind-shape", "group-kind-shape"),
    ("invalid-group-include-ref", "group-include-ref"),
    ("invalid-group-include-composite", "group-include-composite"),
])
def test_invalid_fixtures_exit2(name: str, code: str):
    s = resolve(load_schema(fx(name)))
    assert code in _codes(s)
    for cmd in ("validate", "check"):
        rc, err = call(cmd, "--in", str(fx(name)))
        assert rc == EXIT_SCHEMA, err


# ------------------------------------------------------------------- Gates


def _gate(groups, components=(), texts=(), labels=()):
    return detect_collisions(list(texts), [], components=list(components),
                             labels=list(labels), groups=groups)


def _kinds(cols) -> list[tuple[str, str, str]]:
    return [(c.kind, c.elem_a, c.elem_b) for c in cols]


def test_gate_venn_overlap_allowed_for_shared_parent():
    gs = [
        _g("c1", (40, 40), (500, 400), includes=["a", "s"], kind="composite"),
        _g("a", (60, 60), (300, 300), members=[]),
        _g("s", (100, 80), (300, 300), members=[]),  # überlappt a (Venn)
    ]
    assert _gate(gs) == []


def test_gate_composites_overlap_only_with_shared_child():
    shared = [
        _g("c1", (40, 40), (400, 400), includes=["s"], kind="composite"),
        _g("c2", (60, 40), (400, 400), includes=["s"], kind="composite"),
        _g("s", (80, 80), (200, 200), members=[]),
    ]
    assert _gate(shared) == []
    disjoint = [
        _g("c1", (40, 40), (400, 400), includes=["a"], kind="composite"),
        _g("c2", (60, 40), (400, 400), includes=["b"], kind="composite"),
        _g("a", (50, 50), (20, 20), members=[]),
        _g("b", (400, 400), (20, 20), members=[]),
    ]
    assert ("group-box", "group-c1", "group-c2") in _kinds(_gate(disjoint))


def test_gate_venn_illegal_without_shared_parent():
    rc, err = call("check", "--in", str(fx("colliding-group-box-venn-illegal")))
    assert rc == EXIT_GATE
    assert "GROUP-BOX  [group-g1] × [group-g2]" in err


def test_gate_child_listed_before_composite_exempt():
    gs = [
        _g("a", (60, 60), (300, 300), members=[]),
        _g("c1", (40, 40), (400, 400), includes=["a"], kind="composite"),
    ]
    assert _gate(gs) == []


def test_gate_containment_ok_with_touching_edges():
    gs = [
        _g("c1", (40, 40), (400, 400), includes=["a"], kind="composite"),
        _g("a", (40, 40), (400, 400), members=[]),
    ]
    assert _gate(gs) == []


@pytest.mark.parametrize("at, size", [
    ((30, 60), (100, 100)),   # links
    ((60, 30), (100, 100)),   # oben
    ((380, 60), (100, 100)),  # rechts
    ((60, 380), (100, 100)),  # unten
])
def test_gate_containment_protrusion(at, size):
    gs = [
        _g("c1", (40, 40), (400, 400), includes=["a"], kind="composite"),
        _g("a", at, size, members=[]),
    ]
    assert _kinds(_gate(gs)) == [("group-containment", "group-c1", "group-a")]


def test_gate_containment_fixture_exit3():
    rc, err = call("validate", "--in", str(fx("colliding-group-containment")))
    assert rc == EXIT_OK, err
    rc, err = call("check", "--in", str(fx("colliding-group-containment")))
    assert rc == EXIT_GATE
    assert "GROUP-CONTAINMENT  [group-c1] × [group-g2]" in err


def test_gate_composite_vs_foreign_atomic_strict():
    gs = [
        _g("c1", (40, 40), (400, 400), includes=["a"], kind="composite"),
        _g("a", (60, 60), (100, 100), members=[]),
        _g("z", (200, 200), (200, 200), members=[]),  # nicht inkludiert
    ]
    assert ("group-box", "group-c1", "group-z") in _kinds(_gate(gs))


def _comp(cid: str, at) -> dict:
    return {"id": cid, "type": "pump", "at": list(at)}


def test_component_outside_composite_parent_box():
    s = _schema([
        {"id": "c1", "kind": "composite", "includes": ["a"],
         "at": [40, 40], "size": [200, 200]},
        {"id": "a", "members": ["p1"], "at": [60, 60], "size": [160, 160]},
    ], [_comp("p1", (100, 100))])
    assert _gate(s.groups, s.components) == []
    # Kind-Box ragt heraus, Komponente liegt in a, aber außerhalb c1.
    s.groups[1].size = (400, 160)
    s.components[0].at = (350, 100)
    kinds = _kinds(_gate(s.groups, s.components))
    assert ("component-outside-group-box", "comp-p1", "group-c1") in kinds
    assert ("component-outside-group-box", "comp-p1", "group-a") not in kinds


def test_component_in_foreign_uses_transitive_membership():
    gs = [
        _g("c1", (40, 40), (660, 360), includes=["a", "s"], kind="composite"),
        _g("c2", (400, 50), (660, 360), includes=["s", "b"], kind="composite"),
        _g("a", (60, 100), (260, 280), members=["pa"]),
        _g("s", (420, 100), (260, 280), members=["ps"]),
        _g("b", (780, 100), (260, 280), members=["pb"]),
    ]
    s = _schema([g.model_dump(by_alias=True) for g in gs],
                [_comp("pa", (190, 240)), _comp("ps", (550, 240)),
                 _comp("pb", (910, 240))])
    # ps liegt in c1 UND c2 (beides Ahnen) → kein Fremd-Treffer.
    assert _gate(s.groups, s.components) == []
    # pa in c2 (kein Ahne von a) → fremd.
    s.components[0].at = (450, 240)
    s.groups[2].size = (440, 280)
    kinds = _kinds(_gate(s.groups, s.components))
    assert ("component-in-foreign-group-box", "comp-pa", "group-c2") in kinds
    assert ("component-in-foreign-group-box", "comp-pa", "group-c1") not in kinds


def test_group_box_label_skips_composite_ancestors():
    gs = [
        _g("c1", (40, 40), (400, 400), includes=["a"], kind="composite"),
        _g("a", (60, 60), (300, 300), members=["p1"]),
    ]
    comps = [_schema([], [_comp("p1", (200, 200))]).components[0]]
    t = TextElem("lbl-l1", "Label", 14, 150, 150)
    bound = Label(id="l1", comp="p1", text="Label")
    assert _gate(gs, comps, [t], [bound]) == []
    free = Label(id="l1", at=(150, 150), text="Label")
    kinds = _kinds(_gate(gs, comps, [t], [free]))
    assert ("group-box-label", "lbl-l1", "group-c1") in kinds
    assert ("group-box-label", "lbl-l1", "group-a") in kinds


# ----------------------------------------------------------------- Routing


def test_schema_routes_detour_around_shared_child_for_foreign_pair():
    s = resolve(load_schema(fx("ladder-hier-02")))
    routes = dict(zip([p.id for p in s.pipes], schema_routes(s), strict=True))
    assert routes["p_l_r"] == [(210, 340), (210, 381), (880, 381), (880, 340)]
    assert routes["p_l_s"] == [(218, 240), (520, 240)]


# ---------------------------------------------------------------- Emission


def _svg_root(name: str):
    s = resolve(load_schema(fx(name)))
    return s, ET.fromstring(render(s))


def test_emit_composite_box_style_and_attrs():
    # S4-L5c: composite-Rahmen nur bei explizitem `frame: true`.
    s = resolve(load_schema(fx("ladder-hier-01")))
    for g in s.groups:
        if g.kind == "composite":
            g.frame = True
    root = ET.fromstring(render(s))
    layer = root.find(f".//{_SVG}g[@id='layer-groups']")
    ids = [g.get("id") for g in layer]
    # composites zuerst (unter den atomaren Kindern).
    assert ids == ["group-c_main", "group-c_side", "group-g_a",
                   "group-g_buf", "group-g_c"]
    c = layer[0]
    assert c.get("data-kind") == "composite"
    assert c.get("data-includes") == "g_a g_buf"
    rect = c.find(f"{_SVG}rect")
    assert rect.get("class") == "gbox gbox-composite"
    assert rect.get("rx") == rect.get("ry") == str(COMPOSITE_RX)
    lbl = c.find(f"{_SVG}text")
    assert lbl.get("class") == "gbox-lbl" and lbl.text == "Holz-Kreis"
    assert lbl.get("x") == "48" and lbl.get("y") == "54"
    atomic = layer[2]
    assert atomic.get("data-kind") is None
    assert atomic.find(f"{_SVG}rect").get("class") == "gbox"
    assert atomic.find(f"{_SVG}rect").get("rx") is None
    style = root.find(f"{_SVG}style").text
    assert ".gbox-composite{" in style and "stroke-width:2" in style


def test_emit_composite_default_has_no_frame_and_no_css():
    """S4-L5c: composite ohne `frame` → Wrapper bleibt, kein rect/Label,
    keine composite-CSS; atomare Kinder weiter gerahmt."""
    _, root = _svg_root("ladder-hier-01")
    layer = root.find(f".//{_SVG}g[@id='layer-groups']")
    c = layer[0]
    assert c.get("id") == "group-c_main"
    assert c.get("data-kind") == "composite"
    assert list(c) == []
    assert layer[2].find(f"{_SVG}rect").get("class") == "gbox"
    assert ".gbox-composite" not in root.find(f"{_SVG}style").text


def test_emit_without_composites_has_no_composite_css():
    _, root = _svg_root("rich-groups")
    assert ".gbox-composite" not in root.find(f"{_SVG}style").text


# --------------------------------------------------------------------- CLI


@pytest.mark.parametrize("name", ["ladder-hier-01", "ladder-hier-02",
                                  "ladder-hier-03"])
def test_hier_levels_check_exit0(name: str):
    rc, err = call("check", "--in", str(fx(name)))
    assert rc == EXIT_OK, err
    assert err == ""
