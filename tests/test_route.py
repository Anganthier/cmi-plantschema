"""S2: route — via-Route 1:1, Fallback-Manhattan, Pfeil-Endpunkte (R-29)."""

from __future__ import annotations

from plantschema.model import Pipe
from plantschema.route import PipeGeometry, arrow_d, path_d, port_position, route_pipe


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


def test_pipe_geometry_carries_kind_and_flow_and_points():
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
    # Segmente-API (S3-Gate: LINE×TEXT braucht die Punktesequenz).
    assert g.points == [(0, 0), (10, 0)]


# ---------------------------------------------------------------------------
# Pfeil-Endpunkte (R-29, S2)
# ---------------------------------------------------------------------------


def test_arrow_horizontal_facing_right():
    # Letztes Segment horizontal nach rechts → Pfeil-Dreieck, Spitze (500,300).
    d = arrow_d([(100, 300), (500, 300)])
    assert d.startswith("M500,300 L")
    assert d.endswith(" Z")
    # Basis-Mitte 10 px davor (490,300); Flanken ±4 px senkrecht (y=304/296).
    assert "L490.0,304.0" in d and "L490.0,296.0" in d


def test_arrow_horizontal_facing_left():
    d = arrow_d([(500, 300), (100, 300)])
    assert d.startswith("M100,300 L")
    # Spitze (100,300), Basis bei (110,300) ± 4.
    assert "L110.0,304.0" in d and "L110.0,296.0" in d


def test_arrow_vertical_facing_down():
    d = arrow_d([(300, 100), (300, 400)])
    assert d.startswith("M300,400 L")
    # Senkrecht nach unten: Flanken x = 300±4, Basis y = 390.
    assert "L304.0,390.0" in d and "L296.0,390.0" in d


def test_arrow_uses_last_segment_direction():
    # Via-Route: letztes Segment (vertikal) bestimmt die Pfeil-Ausrichtung.
    pts = [(100, 100), (400, 100), (400, 300)]
    d = arrow_d(pts)
    assert d.startswith("M400,300 L")
    assert "L404.0,290.0" in d and "L396.0,290.0" in d


def test_arrow_degenerate_pipe_returns_empty():
    assert arrow_d([]) == ""
    assert arrow_d([(10, 10)]) == ""
    assert arrow_d([(10, 10), (10, 10)]) == ""


def test_arrow_deterministic():
    pts = [(0, 0), (300, 200)]
    assert arrow_d(pts) == arrow_d(list(pts))


def test_arrow_tip_exactly_at_pipe_endpoint():
    """R-29: Spitze des Pfeils = exakt Pipe-Endpunkt (M-Teil des d-Strings)."""
    end = (612, 290)
    d = arrow_d([(560, 250), end])
    assert d.startswith(f"M{end[0]},{end[1]} ")
