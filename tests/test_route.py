"""S1: route — via-Route 1:1, Fallback-Manhattan, d-String + Pfeile."""

from __future__ import annotations

from plantschema.model import Pipe
from plantschema.route import PipeGeometry, path_d, port_position, route_pipe


def test_via_route_is_1_to_1():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
        "via": [[200, 150], [500, 150]],
    })
    pts = route_pipe(p, (200, 274), (470, 250))
    assert pts == [(200, 274), (200, 150), (500, 150), (470, 250)]


def test_via_passthrough_no_autopoint():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
        "via": [[300, 300]],
    })
    pts = route_pipe(p, (100, 400), (500, 200))
    assert pts == [(100, 400), (300, 300), (500, 200)]


def test_manhattan_fallback_single_corner():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
    })
    pts = route_pipe(p, (100, 400), (500, 200))
    assert pts == [(100, 400), (500, 400), (500, 200)]


def test_manhattan_no_corner_when_aligned():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "right"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
    })
    pts = route_pipe(p, (100, 300), (500, 300))
    assert pts == [(100, 300), (500, 300)]


def test_manhattan_same_point():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "top"},
        "kind": "vl",
    })
    pts = route_pipe(p, (100, 300), (100, 300))
    assert pts == [(100, 300)]


def test_deterministic_d_string_with_arrow():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
        "via": [[200, 150]],
    })
    pts = route_pipe(p, (200, 300), (500, 250))
    d = path_d(pts)
    assert d == "M200,300 L200,150 L500,250"


def test_path_d_single_point():
    assert path_d([(10, 20)]) == "M10,20"


def test_path_d_empty():
    assert path_d([]) == ""


def test_port_position_from_catalog():
    assert port_position("pump", (100, 100), "in") == (80, 100)
    assert port_position("tank-buffer", (500, 250), "top") == (500, 190)


def test_pipe_geometry_carries_kind_and_flow():
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "ctl",
        "flow": "loop-B",
    })
    g = PipeGeometry("b", [(0, 0), (10, 0)], p.kind.value, p.flow)
    assert g.kind == "ctl"
    assert g.flow == "loop-B"
    assert g.d == "M0,0 L10,0"
