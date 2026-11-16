"""S2: route — via-Route 1:1, Fallback-Manhattan, Pfeil-Endpunkte (R-29)."""

from __future__ import annotations

from plantschema.model import Pipe
from plantschema.route import (
    PipeGeometry,
    arrow_d,
    manhattan_fallback,
    path_d,
    port_position,
    route_groups,
    route_pipe,
)


def _pipe(**kw) -> Pipe:
    base = {
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
    }
    base.update(kw)
    return Pipe.model_validate(base)


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


# ---------------------------------------------------------------------------
# S4-L3 (R-37): gruppen-bewusstes Routing (Kanal-Konvention)
# ---------------------------------------------------------------------------


def test_manhattan_fallback_helper():
    assert manhattan_fallback((100, 400), (500, 200)) == [(500, 400)]
    assert manhattan_fallback((100, 300), (500, 300)) == []
    assert manhattan_fallback((100, 300), (100, 300)) == []


def test_route_groups_no_groups_equals_route_pipe():
    p = _pipe()
    assert route_groups(p, (100, 400), (500, 200)) == \
        route_pipe(p, (100, 400), (500, 200))
    pv = _pipe(via=[[300, 300]])
    assert route_groups(pv, (100, 400), (500, 200)) == \
        route_pipe(pv, (100, 400), (500, 200))


def test_route_groups_via_override_beats_detour():
    """R-37: `via` (Author-Override) gewinnt immer über den Detour —
    auch wenn die via-Route die fremde Box kreuzen würde."""
    p = _pipe(via=[[300, 200]])  # horizontales Segment y=200 kreuzt Box
    boxes = [(150.0, 100.0, 450.0, 300.0)]  # g_x: 150..450 × 100..300
    pts = route_groups(p, (100, 400), (500, 400), foreign_boxes=boxes)
    assert pts == [(100, 400), (300, 200), (500, 400)]


def test_route_groups_intra_group_no_detour():
    """R-37: intra-gruppig (kein `foreign_boxes`) → unverändert."""
    p = _pipe()
    assert route_groups(
        p, (300, 150), (600, 250),
        foreign_boxes=[], use_channel=True,
    ) == [(300, 150), (600, 150), (600, 250)]


def test_route_groups_no_crossing_no_detour():
    p = _pipe()
    # Fallback (100,400)→(500,400)→(500,200): kein Segment kreuzt die
    # Box (500..700 × 100..300) (Vertikale x=500 = Box-Linkskante →
    # tangential, nicht Interior).
    boxes = [(500.0, 100.0, 700.0, 300.0)]
    pts = route_groups(p, (100, 400), (500, 200), foreign_boxes=boxes)
    assert pts == [(100, 400), (500, 400), (500, 200)]


def test_route_groups_channel_detour_horizontal_segment():
    """R-37: horizontales Fallback-Segment y=450 kreuzt Box
    (980..1340 × 480..720) → Detour über nächste Kante (obere, y=480),
    Kanal-Linie y=479 (CHANNEL_OFFSET 1 px außen)."""
    p = _pipe()
    boxes = [(980.0, 480.0, 1340.0, 720.0)]
    # Fallback: (813,450)→(1140,450)→(1140,600): Segment 0 (y=450)
    # oberhalb der Box, Segment 1 (x=1140, y 450..600) kreuzt →
    # vertikales Segment → nächste vertikale Kante: linke (980),
    # |1140−980| ≤ |1140−1340| → Kanal x=979.
    pts = route_groups(p, (813, 450), (1140, 600), foreign_boxes=boxes)
    assert pts == [(813, 450), (979, 450), (979, 600), (1140, 600)]
    d = path_d(pts)
    assert d == "M813,450 L979,450 L979,600 L1140,600"


def test_route_groups_channel_detour_bottom_edge():
    """R-37: horizontales Segment IN der Box nahe der untern Kante →
    Detour über die nächste Kante (untere, y=300), Kanal y=301."""
    p = _pipe()
    boxes = [(150.0, 100.0, 450.0, 300.0)]
    # Fallback: (100,290)→(500,290)→(500,400): Segment 0 (y=290) kreuzt
    # (|290−100|=190 > |290−300|=10 → untere Kante).
    pts = route_groups(p, (100, 290), (500, 400), foreign_boxes=boxes)
    assert pts == [(100, 290), (100, 301), (500, 301), (500, 400)]


def test_route_groups_channel_detour_vertical_segment():
    """R-37: vertikales Fallback-Segment x=785 kreuzt Box
    (540..900 × 300..600) → Detour über nächste Kante (rechte, x=900),
    Kanal-Linie x=901."""
    p = _pipe()
    boxes = [(540.0, 300.0, 900.0, 600.0)]
    # Fallback: (219,200)→(785,200)→(785,700): Segment 1 (x=785,
    # y 200..700) kreuzt (|785−900|=115 < |785−540|=245 → rechte Kante).
    pts = route_groups(p, (219, 200), (785, 700), foreign_boxes=boxes)
    assert pts == [(219, 200), (901, 200), (901, 700), (785, 700)]
    # Kein Segment des Detours kreuzt die Box-Interior mehr (Target
    # liegt außerhalb der Box).
    assert all(
        not _seg_hits(pts[k], pts[k + 1], boxes[0])
        for k in range(len(pts) - 1)
    )


def _seg_hits(p1, p2, box) -> bool:
    from plantschema.route import _seg_crosses_box

    return _seg_crosses_box(p1, p2, box)


def test_route_groups_channel_detour_left_edge_vertical():
    """R-37: vertikales Fallback-Segment kreuzt Box → Detour über die
    LINKE Kante (nächste Kante), Kanal-Linie x=279."""
    p = _pipe()
    boxes = [(280.0, 250.0, 400.0, 350.0)]
    # Fallback: (100,400)→(300,400)→(300,200): Segment 0 (y=400)
    # oberhalb... unterhalb der Box (kein Kreuz), Segment 1 (x=300,
    # y 200..400) kreuzt (x-Interior 280..400 ∋ 300, y-Interior
    # 250..350 ∩ 200..400). Nächste vertikale Kante: linke (280),
    # |300−280|=20 < |300−400|=100 → Kanal x=279.
    pts = route_groups(p, (100, 400), (300, 200), foreign_boxes=boxes)
    assert pts == [(100, 400), (279, 400), (279, 200), (300, 200)]


def test_route_groups_channel_detour_tiebreak_top_edge():
    """R-37: exakt gegenüberliegende Kanten (Segment in Box-Mitte) →
    deterministischer Tiebreak: obere bzw. linke Kante."""
    p = _pipe()
    boxes = [(150.0, 100.0, 450.0, 300.0)]  # Mittellinie y=200
    pts = route_groups(p, (100, 200), (500, 200), foreign_boxes=boxes)
    assert pts == [(100, 200), (100, 99), (500, 99), (500, 200)]


def test_route_groups_first_segment_wins():
    """R-37: erstes Fremdkreuzungs-Segment (niedrigster Index) bestimmt
    die Detour-Box — nicht die Box-Reihenfolge im Tuple (kein
    Backtracking/Iteration)."""
    p = _pipe()
    # Fallback: (100,250)→(800,250)→(800,500): Segment 0 (horizontal
    # y=250) kreuzt Box A; Segment 1 (vertikal x=800) kreuzt Box B.
    # Box B steht im Tuple VOR Box A, aber Segment-Index 0 < 1 →
    # Box A gewinnt.
    box_a = (150.0, 100.0, 350.0, 300.0)   # y-Int. 100..300 ⊃ 250, x 150..350 ⊂ 100..800
    box_b = (600.0, 300.0, 900.0, 500.0)   # x 600..900 ∋ 800, y 300..500 ∩ 250..500
    pts = route_groups(p, (100, 250), (800, 500),
                       foreign_boxes=(box_b, box_a))
    # Detour um Box A: horizontales Segment y=250, nächste horizontale
    # Kante = untere (y=300, |250−300|=50 < |250−100|=150) → Kanal y=301.
    assert pts == [(100, 250), (100, 301), (800, 301), (800, 500)]


def test_route_groups_deterministic_repeated_calls():
    p = _pipe()
    boxes = [(980.0, 480.0, 1340.0, 720.0)]
    first = route_groups(p, (813, 450), (1140, 600), foreign_boxes=boxes)
    for _ in range(5):
        assert route_groups(
            p, (813, 450), (1140, 600), foreign_boxes=boxes,
        ) == first


def test_route_groups_detour_may_still_collide_gate_reports():
    """R-37: Detour, der selbst eine weitere Box kreuzt, wird NICHT
    iterativ korrigiert — der Pfad wird so emittiert (Gate meldet
    den Rest, kein Backtracking): exakt 4 Punkte, Kanal-Linie bleibt
    deterministisch."""
    p = _pipe()
    box_a = (150.0, 100.0, 350.0, 300.0)  # wird von Fallback y=250 kreuzt
    box_b = (400.0, 250.0, 600.0, 350.0)  # kreuzt die Detour-Linie y=301
    pts = route_groups(p, (100, 250), (800, 250),
                       foreign_boxes=(box_b, box_a))
    # Ausgerichtet (y=250): Fallback-Segment kreuzt nur Box A (Box B:
    # y=250 = Box-Oberkante → tangential, kein Interior). Detour um
    # Box A (nächste horizontale Kante: untere y=300 → Kanal y=301)
    # wird NICHT erneut geprüft, obwohl die Kanal-Linie Box B kreuzt.
    assert pts == [(100, 250), (100, 301), (800, 301), (800, 250)]
    from plantschema.route import _seg_crosses_box

    assert _seg_crosses_box(pts[1], pts[2], box_b)  # Gate meldet den Rest
