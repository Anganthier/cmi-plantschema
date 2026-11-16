"""S4-L5b (R-39/R-40): Lanes (Leitungs-Reservierung) + Junction-Symbol
(Modell, Validate-Codes, Lane-Geometrie, Lane-Routen, Warnungen,
LANE-BOX-/LANE-PIPE-Gates, Lane-Emission, junction-Katalog, CLI-Exits)."""

from __future__ import annotations

import io as _io
import re
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout

import pytest
from conftest import fx
from pydantic import ValidationError

from plantschema import __main__ as m
from plantschema import lanes, symbols
from plantschema.__main__ import EXIT_GATE, EXIT_OK, EXIT_SCHEMA
from plantschema.emit import compute_layout, render
from plantschema.io import load_schema
from plantschema.lanes import (
    LANE_SPACING,
    LaneWarning,
    collect_lane_warnings,
    lane_assignments,
    lane_axis,
    lane_box,
    lane_exempt_ids,
    lane_spacing,
    lane_tracks,
    route_in_box,
    segment_in_box,
)
from plantschema.model import Lane, Pipe, PortRef, Schema
from plantschema.qa import detect_collisions
from plantschema.route import PipeGeometry, route_groups, route_lane, schema_routes
from plantschema.validate import validate

_SVG = "{http://www.w3.org/2000/svg}"


def call(*argv: str) -> tuple[int, str]:
    out, err = _io.StringIO(), _io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = m.main(list(argv))
    return rc, err.getvalue()


def _lane(lid: str = "l1", at=(60, 180), size=(480, 40), pipes=("p_a",), **kw) -> Lane:
    data = {"id": lid, "pipes": list(pipes), **kw}
    if at is not None:
        data["at"] = list(at)
    if size is not None:
        data["size"] = list(size)
    return Lane.model_validate(data)


_COMPS = [
    {"id": "p1", "type": "pump", "at": [100, 100]},
    {"id": "h1", "type": "radiator", "at": [450, 300]},
    {"id": "p2", "type": "pump", "at": [100, 300]},
    {"id": "h2", "type": "radiator", "at": [450, 100]},
]
_PIPES = [
    {"id": "p_a", "from": {"comp": "p1", "port": "out"},
     "to": {"comp": "h1", "port": "in"}, "kind": "vl"},
    {"id": "p_b", "from": {"comp": "p2", "port": "out"},
     "to": {"comp": "h2", "port": "in"}, "kind": "rl"},
]


def _schema(lanes_: list[dict], components=None, pipes=None, groups=None) -> Schema:
    return Schema.model_validate({
        "schema": "plantschema/v1",
        "canvas": {"width": 600, "height": 400},
        "components": _COMPS if components is None else components,
        "pipes": _PIPES if pipes is None else pipes,
        "groups": groups or [],
        "lanes": lanes_,
    })


def _ld(lid="l1", at=(60, 180), size=(480, 40), pipes=("p_a",), **kw) -> dict:
    d = {"id": lid, "pipes": list(pipes), **kw}
    if at is not None:
        d["at"] = list(at)
    if size is not None:
        d["size"] = list(size)
    return d


def _codes(schema: Schema) -> list[str]:
    return [p.code for p in validate(schema)]


def _collisions(s: Schema):
    pipes, _ = compute_layout(s)
    return detect_collisions(
        [], pipes, components=s.components, groups=s.groups,
        lanes=s.lanes, lane_exempt=lane_exempt_ids(s),
    )


# ------------------------------------------------------------------ Modell


def test_lane_model_fields_and_defaults():
    lane = _lane(label="Trasse")
    assert lane.at == (60, 180) and lane.size == (480, 40)
    assert lane.pipes == ["p_a"] and lane.label == "Trasse"
    assert _lane(label=None).label is None


def test_lane_pipes_required_non_empty():
    with pytest.raises(ValidationError):
        Lane.model_validate({"id": "l", "at": [1, 1], "size": [1, 1], "pipes": []})
    with pytest.raises(ValidationError):
        Lane.model_validate({"id": "l", "at": [1, 1], "size": [1, 1]})


def test_lane_is_not_a_group():
    with pytest.raises(ValidationError):
        Lane.model_validate({"id": "l", "at": [1, 1], "size": [1, 1],
                             "pipes": ["p"], "members": ["x"]})


def test_lane_id_and_pipe_id_validation():
    with pytest.raises(ValidationError, match="Whitespace"):
        _lane("l 1")
    with pytest.raises(ValidationError, match="Whitespace"):
        _lane(pipes=["p a"])


def test_schema_lanes_default_empty():
    s = _schema([])
    assert s.lanes == []


# --------------------------------------------------------------- Validate


def test_valid_lane_schema_has_no_problems():
    assert _codes(_schema([_ld()])) == []


def test_lane_id_duplicate():
    s = _schema([_ld("l1", pipes=["p_a"]), _ld("l1", at=(60, 300), pipes=["p_b"])])
    assert _codes(s) == ["lane-id-duplicate"]


def test_lane_id_vs_component_id_is_dup_id():
    s = _schema([_ld("p1")])
    assert _codes(s) == ["dup-id"]


@pytest.mark.parametrize("at,size,n", [
    (None, (10, 10), 1),
    ((10, 10), None, 1),
    ((0, 10), (10, 10), 1),
    ((10, 10), (0, 10), 1),
    ((10, 10), (10, 0), 1),
    (None, None, 2),
])
def test_lane_geometry(at, size, n):
    s = _schema([_ld(at=at, size=size)])
    assert _codes(s) == ["lane-geometry"] * n


def test_lane_pipe_ref():
    s = _schema([_ld(pipes=["p_a", "p_ghost"])])
    probs = validate(s)
    assert [p.code for p in probs] == ["lane-pipe-ref"]
    assert "p_ghost" in probs[0].message


def test_lane_pipe_duplicate_two_lanes():
    s = _schema([_ld("l1"), _ld("l2", at=(60, 300))])
    probs = validate(s)
    assert [p.code for p in probs] == ["lane-pipe-duplicate"]
    assert probs[0].path == "lanes[1].pipes"


def test_lane_pipe_duplicate_within_one_lane():
    s = _schema([_ld(pipes=["p_a", "p_a"])])
    assert "lane-pipe-duplicate" in _codes(s)


# --------------------------------------------------------------- Geometrie


def test_lane_axis_box():
    assert lane_axis(_lane(size=(100, 100))) == "h"
    assert lane_axis(_lane(size=(100, 40))) == "h"
    assert lane_axis(_lane(size=(40, 100))) == "v"
    assert lane_box(_lane()) == (60.0, 180.0, 540.0, 220.0)


def test_lane_tracks_horizontal_centered():
    lane = _lane(at=(60, 380), size=(880, 60), pipes=["a", "b", "c"])
    assert lane_spacing(lane) == (float(LANE_SPACING), False)
    assert lane_tracks(lane) == [400, 410, 420]


def test_lane_tracks_vertical_centered():
    lane = _lane(at=(420, 60), size=(160, 280), pipes=["a", "b"])
    assert lane_tracks(lane) == [495, 505]


def test_lane_tracks_single_pipe_on_centerline():
    assert lane_tracks(_lane(at=(0, 100), size=(200, 21), pipes=["a"])) == [110]


def test_lane_tight_spacing_halved():
    lane = _lane(at=(660, 310), size=(400, 12), pipes=["a", "b", "c"])
    assert lane_spacing(lane) == (LANE_SPACING / 2, True)
    assert lane_tracks(lane) == [311, 316, 321]


def test_lane_exactly_fitting_is_not_tight():
    # (n−1)/2·10 = 10 == h/2 → passt (nicht > h/2).
    lane = _lane(size=(400, 20), pipes=["a", "b", "c"])
    assert lane_spacing(lane)[1] is False


def test_lane_assignments_slots_and_degenerate():
    s = _schema([_ld(pipes=["p_a", "p_b"])])
    slots = lane_assignments(s)
    assert set(slots) == {"p_a", "p_b"}
    assert slots["p_a"].axis == "h" and slots["p_a"].track == 195
    assert slots["p_b"].track == 205
    assert not slots["p_a"].degenerate


def test_lane_assignments_degenerate_same_axis_coordinate():
    comps = [
        {"id": "p1", "type": "pump", "at": [100, 100]},
        {"id": "h1", "type": "radiator", "at": [150, 300]},  # in = (120, 300)
    ]
    s = _schema([_ld()], components=comps, pipes=[_PIPES[0]])
    assert lane_assignments(s)["p_a"].degenerate  # from.x 120 == to.x 120


def test_lane_assignments_defensive():
    s = _schema([
        _ld("bad", size=None, pipes=["p_a"]),
        _ld("l1", pipes=["p_ghost", "p_a"]),
        _ld("l2", at=(60, 300), pipes=["p_a", "p_b"]),
    ])
    slots = lane_assignments(s)
    assert slots["p_a"].lane_id == "l1"  # erste gültige Lane gewinnt
    assert slots["p_b"].lane_id == "l2"


def test_lane_assignments_unknown_endpoints_not_degenerate():
    comps = [{"id": "p1", "type": "pump", "at": [100, 100]},
             {"id": "x1", "type": "nope", "at": [120, 300]}]
    pipes = [
        {"id": "p_a", "from": {"comp": "p1", "port": "out"},
         "to": {"comp": "x1", "port": "in"}, "kind": "vl"},
        {"id": "p_b", "from": {"comp": "p1", "port": "zzz"},
         "to": {"comp": "ghost", "port": "in"}, "kind": "vl"},
    ]
    s = _schema([_ld(pipes=["p_a", "p_b"])], components=comps, pipes=pipes)
    slots = lane_assignments(s)
    assert not slots["p_a"].degenerate and not slots["p_b"].degenerate


def test_segment_in_box_touch_tolerance():
    box = (100.0, 100.0, 200.0, 200.0)
    assert segment_in_box((50, 150), (250, 150), box)  # durch
    assert segment_in_box((50, 98), (250, 98), box)  # 2 px Kante = innen
    assert not segment_in_box((50, 97), (250, 97), box)  # 3 px = außen
    assert segment_in_box((202, 50), (202, 250), box)
    assert not segment_in_box((203, 50), (203, 250), box)
    assert not segment_in_box((50, 150), (97, 150), box)


def test_route_in_box_single_point_and_empty():
    box = (100.0, 100.0, 200.0, 200.0)
    assert route_in_box([(150, 150)], box)
    assert not route_in_box([(10, 10)], box)
    assert not route_in_box([], box)


# ---------------------------------------------------------------- Routing


def _pipe(via=None) -> Pipe:
    return Pipe(id="p", **{"from": PortRef(comp="a", port="out")},
                to=PortRef(comp="b", port="in"), kind="vl", via=via)


def _slot(axis="h", track=200, degenerate=False):
    return lanes.LaneSlot(0, "l", axis, track, (0.0, 0.0, 1.0, 1.0), degenerate)


def test_route_lane_horizontal():
    pts = route_lane(_pipe(), (100, 50), (400, 300), _slot("h", 200))
    assert pts == [(100, 50), (100, 200), (400, 200), (400, 300)]


def test_route_lane_vertical():
    pts = route_lane(_pipe(), (100, 50), (400, 300), _slot("v", 250))
    assert pts == [(100, 50), (250, 50), (250, 300), (400, 300)]


def test_route_lane_dedups_when_port_on_track():
    pts = route_lane(_pipe(), (100, 200), (400, 300), _slot("h", 200))
    assert pts == [(100, 200), (400, 200), (400, 300)]


def test_route_lane_via_override_wins():
    via = [(100, 20), (400, 20)]
    pts = route_lane(_pipe(via=via), (100, 50), (400, 300), _slot("h", 200))
    assert pts == [(100, 50), (100, 20), (400, 20), (400, 300)]


def test_route_lane_degenerate_and_no_slot_fall_back_to_r37():
    box = [(150.0, 0.0, 250.0, 400.0)]
    fp, tp = (100, 100), (300, 100)
    ref = route_groups(_pipe(), fp, tp, foreign_boxes=box)
    assert route_lane(_pipe(), fp, tp, _slot("v", 200, True), box) == ref
    assert route_lane(_pipe(), fp, tp, None, box) == ref
    assert ref != [fp, tp]  # R-37-Detour greift weiterhin


def test_schema_routes_use_lane_routes():
    s = _schema([_ld(pipes=["p_a"])])
    routes = schema_routes(s)
    assert routes[0] == [(120, 100), (120, 200), (420, 200), (420, 300)]
    # nicht-Lane-Pipe: Manhattan-Fallback unverändert.
    assert routes[1] == [(120, 300), (420, 300), (420, 100)]
    pipes, _ = compute_layout(s)
    assert [p.points for p in pipes] == routes


def test_schema_routes_by_id_skips_unknown_end():
    from plantschema.route import schema_routes_by_id

    pipes = [*_PIPES, {"id": "p_x", "from": {"comp": "ghost", "port": "out"},
                       "to": {"comp": "h1", "port": "in"}, "kind": "vl"}]
    s = _schema([], pipes=pipes)
    assert set(schema_routes_by_id(s)) == {"p_a", "p_b"}


# ---------------------------------------------------------------- Warnungen


def test_no_lanes_no_warnings():
    assert collect_lane_warnings(_schema([])) == []


def test_tight_lane_warning():
    s = _schema([_ld(size=(480, 8), pipes=["p_a", "p_b"])])
    (w,) = collect_lane_warnings(s)
    assert w.elem_id == "lane-l1" and w.pipe_id is None
    assert w.line().startswith("LANE-FALLBACK  [lane-l1] — 2 Pipes")


def _degenerate_schema(lane_at, via=None) -> Schema:
    comps = [
        {"id": "p1", "type": "pump", "at": [100, 100]},   # out = (120, 100)
        {"id": "h1", "type": "radiator", "at": [450, 100]},  # in = (420, 100)
    ]
    pipe = {"id": "p_a", "from": {"comp": "p1", "port": "out"},
            "to": {"comp": "h1", "port": "in"}, "kind": "vl"}
    if via is not None:
        pipe["via"] = via
    # vertikale Lane: gleiche y-Koordinate beider Ports → degeneriert.
    return _schema([_ld(at=lane_at, size=(40, 200))], components=comps, pipes=[pipe])


def test_degenerate_fallback_crossing_box_no_warning_no_gate():
    s = _degenerate_schema((250, 20))
    assert lane_exempt_ids(s) == frozenset({"p_a"})
    assert collect_lane_warnings(s) == []
    assert _collisions(s) == []


def test_degenerate_fallback_missing_box_warns_instead_of_gate():
    s = _degenerate_schema((250, 200))
    (w,) = collect_lane_warnings(s)
    assert w.pipe_id == "p_a"
    assert "@ pipe-p_a" in w.line()
    assert _collisions(s) == []  # exempt → kein LANE-PIPE


def test_degenerate_with_via_is_gated_not_warned():
    s = _degenerate_schema((250, 200), via=[[120, 50], [420, 50]])
    assert lane_exempt_ids(s) == frozenset()
    assert collect_lane_warnings(s) == []
    assert [c.kind for c in _collisions(s)] == ["lane-pipe"]


def test_invalid_lane_skipped_by_warnings_and_gates():
    s = _schema([_ld(size=None), _ld("l2", at=(60, 300), pipes=["p_b"])])
    assert collect_lane_warnings(s) == []
    pipes, _ = compute_layout(s)
    assert detect_collisions([], pipes, lanes=s.lanes) == []


def test_lane_warning_line_format():
    w = LaneWarning("lane-x", None, "n")
    assert w.line() == "LANE-FALLBACK  [lane-x] — n"


# ------------------------------------------------------------------- Gates


def test_lane_box_gate_over_threshold():
    s = _schema([_ld("l1", pipes=["p_a"]),
                 _ld("l2", at=(80, 190), size=(460, 40), pipes=["p_b"])])
    cs = [c for c in _collisions(s) if c.kind == "lane-box"]
    assert len(cs) == 1
    assert cs[0].elem_a == "lane-l1" and cs[0].elem_b == "lane-l2"


def test_lane_box_gate_under_threshold_ok():
    s = _schema([_ld("l1", pipes=["p_a"]),
                 _ld("l2", at=(60, 205), size=(480, 40), pipes=["p_b"])])
    assert [c for c in _collisions(s) if c.kind == "lane-box"] == []


def test_lane_pipe_gate_missing_box():
    pipes = [{**_PIPES[0], "via": [[120, 60], [420, 60], [420, 100]]}]
    comps = [_COMPS[0], {"id": "h1", "type": "radiator", "at": [450, 100]}]
    s = _schema([_ld(at=(60, 250))], components=comps, pipes=pipes)
    (c,) = _collisions(s)
    assert c.kind == "lane-pipe" and c.elem_a == "pipe-p_a"
    assert "läuft nicht durch Lane" in c.note


def test_lane_pipe_gate_edge_touch_counts_as_inside():
    pipes = [{**_PIPES[0], "via": [[120, 178], [420, 178]]}]
    s = _schema([_ld()], pipes=pipes)  # Box-Oberkante y = 180, 2 px
    assert [c for c in _collisions(s) if c.kind == "lane-pipe"] == []


def test_lane_pipe_gate_ignores_unknown_and_empty():
    geo = PipeGeometry("p_a", [], "vl", None)
    s = _schema([_ld(pipes=["p_a", "p_zzz"])])
    assert detect_collisions([], [geo], lanes=s.lanes) == []


def test_components_inside_lane_box_allowed_and_no_group_gates():
    comps = [*_COMPS, {"id": "j1", "type": "junction", "at": [300, 200]}]
    groups = [{"id": "g1", "members": ["p1"], "at": [40, 40], "size": [140, 120]}]
    s = _schema([_ld()], components=comps, groups=groups)
    kinds = {c.kind for c in _collisions(s)}
    assert "component-in-foreign-group-box" not in kinds
    assert "component-outside-group-box" not in kinds
    assert kinds <= {"lane-box", "lane-pipe"} and not kinds


# ---------------------------------------------------------------- Emission


def _svg_root(s: Schema) -> ET.Element:
    return ET.fromstring(render(s))


def test_lane_layer_order_and_attrs():
    s = _schema([_ld(label="Trasse", pipes=["p_a"]),
                 _ld("lv", at=(250, 20), size=(40, 300), pipes=["p_b"])])
    root = _svg_root(s)
    ids = [g.get("id") for g in root.findall(f"{_SVG}g")]
    assert ids == ["layer-groups", "layer-lanes", "layer-pipes",
                   "layer-components", "layer-readouts", "layer-labels"]
    layer = root.find(f"{_SVG}g[@id='layer-lanes']")
    l1 = layer.find(f"{_SVG}g[@id='lane-l1']")
    assert l1.get("data-axis") == "horizontal" and l1.get("data-pipes") == "p_a"
    rect = l1.find(f"{_SVG}rect")
    assert rect.get("class") == "lane"
    assert (rect.get("x"), rect.get("y"), rect.get("width"), rect.get("height")) == (
        "60", "180", "480", "40")
    lbl = l1.find(f"{_SVG}text")
    assert lbl.get("class") == "lane-lbl" and lbl.text == "Trasse"
    assert (lbl.get("x"), lbl.get("y")) == ("66", "192")
    lv = layer.find(f"{_SVG}g[@id='lane-lv']")
    assert lv.get("data-axis") == "vertical"
    assert lv.find(f"{_SVG}text") is None


def test_lane_css_only_with_lanes():
    with_lanes = render(_schema([_ld()]))
    without = render(_schema([]))
    assert ".lane{" in with_lanes and ".lane-lbl{" in with_lanes
    assert "rgba(200,180,140,0.30)" in with_lanes
    assert ".lane{" not in without and "layer-lanes" not in without


def test_lane_render_deterministic():
    s = _schema([_ld(pipes=["p_a", "p_b"])])
    assert render(s) == render(s)


# ---------------------------------------------------------------- junction


def test_junction_in_catalog():
    assert "junction" in symbols.known_types()
    assert symbols.port_names("junction") == frozenset(
        {"left", "right", "top", "bottom"})
    assert symbols.symbol_id("junction") == "pid-junction"
    assert symbols.symbol_bounds("junction") == (-6, -6, 6, 6)
    assert symbols.LABEL_OFFSET["junction"] == 18
    assert "junction" in symbols.PIPE_PORT_TYPES


@pytest.mark.parametrize("port,offset", [
    ("left", (-6, 0)), ("right", (6, 0)), ("top", (0, -6)), ("bottom", (0, 6)),
])
def test_junction_port_offsets(port, offset):
    geo = symbols.port_offset("junction", port)
    assert (geo.dx, geo.dy) == offset


def test_render_defs_junction_only_when_used():
    base = symbols.render_defs()
    assert "pid-junction" not in base
    assert base.count("<g id=") == 18
    used = symbols.render_defs({"junction"})
    assert used.count("<g id=") == 19
    assert used.startswith(base)
    assert '<g id="pid-junction">' in used
    assert re.search(r'<circle class="pid" r="3" style="stroke-width:6"/>', used)


def test_junction_render_component_and_svg():
    comps = [*_COMPS, {"id": "j1", "type": "junction", "at": [300, 200],
                       "label": {"text": "V1"}}]
    s = _schema([], components=comps)
    svg = render(s)
    root = ET.fromstring(svg)
    g = root.find(f".//{_SVG}g[@id='comp-j1']")
    assert g.get("data-symbol") == "pid-junction"
    use = g.find(f"{_SVG}use")
    assert use.get("href") == "#pid-junction"
    assert root.find(f".//{_SVG}g[@id='pid-junction']") is not None
    assert "pid-junction" not in render(_schema([]))


def test_junction_pipes_validate():
    comps = [*_COMPS, {"id": "j1", "type": "junction", "at": [300, 200]}]
    pipes = [
        {"id": "a", "from": {"comp": "p1", "port": "out"},
         "to": {"comp": "j1", "port": "left"}, "kind": "vl"},
        {"id": "b", "from": {"comp": "j1", "port": "bottom"},
         "to": {"comp": "h1", "port": "in"}, "kind": "vl"},
        {"id": "c", "from": {"comp": "j1", "port": "nope"},
         "to": {"comp": "h1", "port": "in"}, "kind": "vl"},
    ]
    s = _schema([], components=comps, pipes=pipes)
    assert _codes(s) == ["ref-port"]


# --------------------------------------------------------------------- CLI


@pytest.mark.parametrize("name,code", [
    ("invalid-lane-pipe-ref", "lane-pipe-ref"),
    ("invalid-lane-pipe-duplicate", "lane-pipe-duplicate"),
])
def test_cli_invalid_lane_exit2(name, code):
    rc, err = call("validate", "--in", str(fx(name)))
    assert rc == EXIT_SCHEMA
    assert "lanes[" in err
    s = load_schema(fx(name))
    assert [p.code for p in validate(s)] == [code]


@pytest.mark.parametrize("name,line", [
    ("colliding-lane-box", "LANE-BOX  [lane-lane_a] × [lane-lane_b]"),
    ("colliding-lane-pipe-no-cross", "LANE-PIPE  [pipe-p_a] × [lane-lane_a]"),
])
def test_cli_colliding_lane_exit3(name, line):
    rc, err = call("validate", "--in", str(fx(name)))
    assert rc == EXIT_OK, err
    rc, err = call("check", "--in", str(fx(name)))
    assert rc == EXIT_GATE
    assert line in err
    assert "1 Kollision(en):" in err


def test_cli_check_prints_lane_warning_exit0():
    rc, err = call("check", "--in", str(fx("ladder-lane-03")))
    assert rc == EXIT_OK
    assert err.startswith("1 Warnung(en):\n  LANE-FALLBACK  [lane-lane_r]")


def test_cli_render_l11_junction_xml(tmp_path):
    out = tmp_path / "l11.svg"
    rc, err = call("render", "--in", str(fx("ladder-lane-02")), "--out", str(out))
    assert rc == EXIT_OK, err
    root = ET.parse(out).getroot()
    assert root.find(f".//{_SVG}g[@id='comp-j1']").get("data-type") == "junction"
    assert root.find(f".//{_SVG}g[@id='lane-lane_h']") is not None
