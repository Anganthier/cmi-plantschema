"""S1: qa — Kollisions-Belegung + nicht-Kollision, Breite-Heuristik."""

from __future__ import annotations

from plantschema.model import Pipe
from plantschema.qa import (
    HEIGHT_FACTOR,
    Collision,
    TextElem,
    detect_collisions,
    estimate_width,
)
from plantschema.route import PipeGeometry, route_pipe


def _pipe(d_pts: list[tuple[int, int]], kind: str = "vl", pid: str = "b") -> PipeGeometry:
    return PipeGeometry(pid, d_pts, kind, None)


def test_estimate_width_kanon():
    # cmi-Kanon: width ≈ font_size * 0.52 * len(text).
    assert estimate_width("ABCDE", 10) == 10 * 0.52 * 5
    assert estimate_width("", 14) == 0.0


def test_height_factor_kanon():
    assert HEIGHT_FACTOR == 1.2


def test_text_text_collision_detected():
    a = TextElem("lbl-a", "Kollisions-Zone", 14, 400, 200, "middle")
    b = TextElem("lbl-b", "Zweite Ebene", 14, 400, 200, "middle")
    cols = detect_collisions([a, b], [])
    assert len(cols) == 1
    c = cols[0]
    assert c.kind == "text-text"
    assert {c.elem_a, c.elem_b} == {"lbl-a", "lbl-b"}


def test_text_text_no_collision_when_apart():
    a = TextElem("lbl-a", "Kollisions-Zone", 14, 400, 200, "middle")
    b = TextElem("lbl-b", "Weit weg", 14, 400, 400, "middle")
    assert detect_collisions([a, b], []) == []


def test_line_text_collision_detected():
    # Horizontale Leitung y=250 läuft durch den Text bei y=250.
    text = TextElem("lbl-a", "Kollisions-Zone", 14, 400, 250, "middle")
    pipe = _pipe([(100, 250), (700, 250)])
    cols = detect_collisions([text], [pipe])
    assert len(cols) == 1
    assert cols[0].kind == "line-text"
    assert cols[0].elem_a == "pipe-b"
    assert cols[0].elem_b == "lbl-a"


def test_line_text_no_collision_when_clear():
    text = TextElem("lbl-a", "Kollisions-Zone", 14, 400, 100, "middle")
    pipe = _pipe([(100, 400), (700, 400)])
    assert detect_collisions([text], [pipe]) == []


def test_line_text_corner_hit_via_via():
    # Via-Route schneidet den Text im Eckbereich.
    p = Pipe.model_validate({
        "id": "b",
        "from": {"comp": "h", "port": "top"},
        "to": {"comp": "p", "port": "left"},
        "kind": "vl",
        "via": [[400, 100]],
    })
    text = TextElem("lbl-a", "Kollisions-Zone", 14, 400, 100, "middle")
    pts = route_pipe(p, (200, 300), (500, 300))
    cols = detect_collisions([text], [PipeGeometry("b", pts, "vl", None)])
    assert len(cols) == 1
    assert cols[0].kind == "line-text"


def test_empty_text_never_collides():
    a = TextElem("lbl-a", "", 14, 400, 200, "middle")
    b = TextElem("lbl-b", "x", 14, 400, 200, "middle")
    assert detect_collisions([a, b], []) == []


def test_anchor_middle_expands_box_symmetric():
    # middle-Text: BBox symmetrisch → Kollision trotz unterschiedlicher x.
    a = TextElem("lbl-a", "Kollisions-Zone", 14, 380, 200, "middle")
    b = TextElem("lbl-b", "Kollisions-Zone", 14, 420, 200, "middle")
    cols = detect_collisions([a, b], [])
    assert len(cols) == 1


def test_collision_line_format():
    c = Collision("text-text", "lbl-a", "lbl-b", 400, 200, "Überlappung")
    line = c.line()
    assert line.startswith("TEXT-TEXT")
    assert "lbl-a" in line and "lbl-b" in line
    assert "(400,200)" in line
