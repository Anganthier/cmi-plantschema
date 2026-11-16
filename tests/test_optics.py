"""S4-L5c: Optik & Anbindung — `frame` (Group/Lane), `hidden_kinds`
(SVG-Display-Option + Gate-/Slot-Exklusion, `hidden-pipe-in-lane`) und
Stutzen (`.stub`, Docking-Connector an Innen-Ports)."""

from __future__ import annotations

import io as _io
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout

import pytest
from conftest import LADDER, fx

from plantschema import __main__ as m
from plantschema import place
from plantschema.__main__ import EXIT_OK, EXIT_SCHEMA
from plantschema.emit import (
    component_stubs,
    compute_layout,
    group_framed,
    lane_framed,
    render,
)
from plantschema.io import load_schema
from plantschema.layout import resolve
from plantschema.model import Group, Lane, PipeKind, SchemaError
from plantschema.qa import detect_collisions, texts_for_schema
from plantschema.symbols import port_stubs
from plantschema.validate import validate

_SVG = "{http://www.w3.org/2000/svg}"


def call(*argv: str) -> tuple[int, str]:
    out, err = _io.StringIO(), _io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = m.main(list(argv))
    return rc, err.getvalue()


def _load(path):
    return resolve(load_schema(path))


def _gate(s):
    pipes, _ = compute_layout(s)
    return detect_collisions(
        texts_for_schema(s), pipes,
        components=s.components, readouts=s.readouts, labels=s.labels,
        groups=s.groups, lanes=s.lanes,
        hidden_kinds=s.hidden_kind_values,
    )


def _kinds(cs):
    return [(c.kind, c.elem_a, c.elem_b) for c in cs]


# ------------------------------------------------------------------ frame


@pytest.mark.parametrize(("kind", "frame", "expected"), [
    ("atomic", None, True),
    ("atomic", True, True),
    ("atomic", False, False),
    ("composite", None, False),
    ("composite", True, True),
    ("composite", False, False),
])
def test_group_frame_rule(kind, frame, expected):
    g = Group(id="g", kind=kind, at=(10, 10), size=(50, 50),
              members=[] if kind == "composite" else ["x"],
              includes=["a"] if kind == "composite" else [], frame=frame)
    assert group_framed(g) is expected


@pytest.mark.parametrize(("frame", "expected"), [
    (None, True), (True, True), (False, False),
])
def test_lane_frame_rule(frame, expected):
    lane = Lane(id="l", at=(10, 10), size=(100, 20), pipes=["p"], frame=frame)
    assert lane_framed(lane) is expected


def test_frame_off_omits_rect_and_label_in_svg():
    s = _load(fx("rich-groups"))
    s.groups[0].frame = False  # g1 trägt das Label „Gruppe A"
    root = ET.fromstring(render(s))
    g1 = root.find(f".//{_SVG}g[@id='group-g1']")
    assert g1 is not None and list(g1) == []
    assert "Gruppe A" not in render(s)
    g2 = root.find(f".//{_SVG}g[@id='group-g2']")
    assert g2.find(f"{_SVG}rect").get("class") == "gbox"


def test_lane_frame_false_in_l13():
    root = ET.fromstring(render(_load(fx("ladder-hidden-01"))))
    lv = root.find(f".//{_SVG}g[@id='lane-lane_v']")
    lh = root.find(f".//{_SVG}g[@id='lane-lane_h']")
    assert lv.find(f"{_SVG}rect").get("class") == "lane"
    assert lv.find(f"{_SVG}text").text == "Steig"
    assert list(lh) == [] and lh.get("data-pipes") == "p_v2"


@pytest.mark.parametrize("name", [
    "colliding-group-box-venn-illegal", "colliding-group-containment",
    "colliding-group-box", "colliding-group-box-label",
])
def test_gates_independent_of_frame(name):
    s = _load(fx(name))
    base = _kinds(_gate(s))
    assert base  # Fixture kollidiert
    for frame in (True, False):
        for g in s.groups:
            g.frame = frame
        assert _kinds(_gate(s)) == base


def test_frame_must_be_bool():
    with pytest.raises(Exception):  # noqa: B017 (pydantic ValidationError)
        Group(id="g", at=(1, 1), size=(1, 1), frame="maybe")


# ------------------------------------------------------------ hidden_kinds


def test_l13_hidden_pipes_not_in_svg_but_in_model():
    s = _load(fx("ladder-hidden-01"))
    assert s.hidden_kinds == [PipeKind.CTL]
    assert validate(s) == []
    assert {p.id for p in s.pipes} == {"p_v1", "p_v2", "p_c1", "p_c2"}
    svg = render(s)
    root = ET.fromstring(svg)
    lp = root.find(f".//{_SVG}g[@id='layer-pipes']")
    ids = [e.get("id") for e in lp if e.get("id")]
    assert ids == ["pipe-p_v1", "pipe-p_v2"]
    assert not [e for e in lp if "ctl" in (e.get("class") or "")]
    # Gegen-Render ohne hidden_kinds: ctl-Pipes + Pfeile wieder da.
    s.hidden_kinds = []
    lp2 = ET.fromstring(render(s)).find(f".//{_SVG}g[@id='layer-pipes']")
    ids2 = [e.get("id") for e in lp2 if e.get("id")]
    assert ids2 == ["pipe-p_v1", "pipe-p_v2", "pipe-p_c1", "pipe-p_c2"]
    assert [e for e in lp2 if e.get("class") == "pipe-arrow arrow-ctl"]


def test_hidden_pipes_excluded_from_gate():
    s = _load(fx("ladder-hidden-01"))
    assert _gate(s) == []
    s.hidden_kinds = []
    assert ("line-text", "pipe-p_c1", "lbl-lbl_sig") in _kinds(_gate(s))


def test_detect_collisions_hidden_kinds_param():
    s = _load(fx("ladder-hidden-01"))
    pipes, _ = compute_layout(s)
    texts = texts_for_schema(s)
    assert [c.kind for c in detect_collisions(texts, pipes)] == ["line-text"]
    assert detect_collisions(texts, pipes, hidden_kinds=frozenset({"ctl"})) == []


def test_hidden_pipes_do_not_block_slots():
    s = _load(fx("ladder-hidden-01"))
    comps = {c.id: c for c in s.components}
    assert len(place._all_pipe_segments(s, comps)) == 2
    s.hidden_kinds = []
    assert len(place._all_pipe_segments(s, comps)) == 4


def test_slot_avoids_visible_but_not_hidden_pipe(tmp_path):
    """Auto-Slot (up) einer Komponente, durch den nur eine ctl-Pipe
    läuft: sichtbar → Ausweich-Slot; hidden → up-Slot."""
    y = tmp_path / "s.yaml"
    y.write_text(
        "schema: plantschema/v1\n"
        "canvas: { width: 600, height: 300 }\n"
        "components:\n"
        "  - { id: a, type: pump, at: [300, 150] }\n"
        "  - { id: v1, type: valve-actuator, at: [100, 145] }\n"
        "  - { id: v2, type: throttle, at: [500, 145] }\n"
        "labels:\n"
        "  - { id: l1, comp: a, text: P }\n"
        "pipes:\n"
        "  - id: c\n"
        "    from: { comp: v1, port: stem }\n"
        "    to: { comp: v2, port: stem }\n"
        "    kind: ctl\n",
        encoding="utf-8",
    )
    s = resolve(load_schema(y))
    visible, _ = place.resolve_label(s.labels[0], s)
    s.hidden_kinds = [PipeKind.CTL]
    hidden, _ = place.resolve_label(s.labels[0], s)
    assert hidden != visible
    assert hidden[0] == 300 and hidden[1] < 150  # up-Slot über a


def test_validate_hidden_pipe_in_lane():
    s = _load(fx("invalid-hidden-pipe-in-lane"))
    probs = validate(s)
    assert [p.code for p in probs] == ["hidden-pipe-in-lane"]
    assert probs[0].path == "lanes[0].pipes"
    rc, err = call("validate", "--in", str(fx("invalid-hidden-pipe-in-lane")))
    assert rc == EXIT_SCHEMA
    assert "hidden-pipe-in-lane" not in err  # Kanon: path: message
    assert "ausgeblendet" in err
    s.hidden_kinds = []
    assert validate(s) == []


def test_hidden_kinds_unknown_kind_is_schema_error(tmp_path):
    y = tmp_path / "bad.yaml"
    y.write_text(
        "schema: plantschema/v1\ncanvas: { width: 10, height: 10 }\n"
        "hidden_kinds: [steam]\n",
        encoding="utf-8",
    )
    with pytest.raises(SchemaError):
        load_schema(y)


@pytest.mark.parametrize("path", sorted(LADDER.glob("L0*.yaml")),
                         ids=lambda p: p.stem)
def test_hidden_kinds_default_and_unused_kind_byte_identical(path):
    s = _load(path)
    base = render(s)
    s.hidden_kinds = []
    assert render(s) == base
    used = {p.kind for p in s.pipes}
    unused = [k for k in PipeKind if k not in used]
    if unused:
        s.hidden_kinds = unused
        assert render(s) == base


def test_l13_cli_check_render(tmp_path):
    rc, err = call("check", "--in", str(fx("ladder-hidden-01")))
    assert (rc, err) == (EXIT_OK, "")
    out = tmp_path / "l13.svg"
    rc, err = call("render", "--in", str(fx("ladder-hidden-01")),
                   "--out", str(out))
    assert (rc, err) == (EXIT_OK, "")
    assert 'id="pipe-p_c1"' not in out.read_text(encoding="utf-8")


# ----------------------------------------------------------------- Stutzen


@pytest.mark.parametrize(("typ", "expected"), [
    ("boiler-oil", [("top", (0, -44), (0, -26)), ("bottom", (0, 29), (0, 26))]),
    ("boiler-solid", [("top", (0, -48), (0, -30)), ("bottom", (0, 36), (0, 20))]),
    ("chimney", [("left", (-14, 0), (-9, 0)), ("right", (18, 0), (9, 0))]),
    ("heatex-plate", [("top", (0, -15), (0, -14)), ("bottom", (0, 18), (0, 14))]),
    ("mixing", []),  # top (0,−14) liegt über y0 = −11 (s. u.)
    ("tank-buffer", [("mid-top", (0, -60), (0, -20)),
                     ("mid-bottom", (0, 60), (0, 20))]),
    ("tap", [("draw", (0, 23), (0, 20))]),
    ("throttle", [("stem", (0, -30), (0, -20))]),
    ("valve-2way", [("stem", (0, -21), (0, -20))]),
    ("valve", [("stem", (0, -21), (0, -20))]),  # Alias
    ("valve-actuator", [("stem", (0, -35), (0, -20))]),
    ("valve-globe", [("stem", (0, -22), (0, -20))]),
    ("junction", []),
    ("flow-switch", []),
    ("pump", []),
    ("unknown-thing", []),
])
def test_port_stub_catalog(typ, expected):
    assert list(port_stubs(typ)) == expected


def test_mixing_top_port_lies_outside_bbox_top():
    """Messdaten-Sonderfall: mixing.top (0,−14) liegt OBERHALB der
    BBox-Oberkante y0 = −11 → nicht strikt innen → kein Stutzen."""
    assert port_stubs("mixing") == ()


def test_stub_present_only_for_connected_inner_ports():
    s = _load(LADDER / "L03.yaml")
    stubs = component_stubs(s)
    assert [(c, p, k) for c, p, k, _ in stubs] == [
        ("tank1", "mid-bottom", "vl"), ("wood1", "bottom", "rl"),
    ]
    tank = next(c for c in s.components if c.id == "tank1")
    root = ET.fromstring(render(s))
    lc = root.find(f".//{_SVG}g[@id='layer-components']")
    paths = lc.findall(f"{_SVG}path")
    assert [(e.get("data-comp"), e.get("data-port")) for e in paths] == [
        ("tank1", "mid-bottom"), ("wood1", "bottom"),
    ]
    p0 = paths[0]
    assert p0.get("class") == "stub vl"
    x, y = tank.at
    assert p0.get("d") == f"M{x},{y + 60} L{x},{y + 20}"
    # Stutzen direkt nach seinem comp-* (über dem Symbol).
    kids = list(lc)
    i = kids.index(p0)
    assert kids[i - 1].get("id") == "comp-tank1"
    assert ".stub{" in root.find(f"{_SVG}style").text


def test_no_stub_no_css_when_only_hidden_or_edge_ports():
    s = _load(fx("ladder-hidden-01"))
    assert component_stubs(s) == []
    svg = render(s)
    assert 'class="stub' not in svg and ".stub{" not in svg
    s.hidden_kinds = []
    assert [(c, p) for c, p, _, _ in component_stubs(s)] == [
        ("va", "stem"), ("vc", "stem"), ("tb", "stem"),
    ]
    l00 = render(_load(LADDER / "L00.yaml"))
    assert ".stub{" not in l00


def test_stub_does_not_change_pipe_geometry():
    s = _load(LADDER / "L06.yaml")
    pipes, _ = compute_layout(s)
    root = ET.fromstring(render(s))
    lp = root.find(f".//{_SVG}g[@id='layer-pipes']")
    emitted = {e.get("id"): e.get("d") for e in lp if e.get("id")}
    assert emitted == {f"pipe-{p.id}": p.d for p in pipes}
