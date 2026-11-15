"""qa — Kollisions-Detektion (S1-Checks + S3-Ausbau, R-34)."""

from __future__ import annotations

from plantschema.model import Component, Group, Pipe
from plantschema.qa import (
    HEIGHT_FACTOR,
    Collision,
    TextElem,
    detect_collisions,
    estimate_width,
    group_box,
    overlap_area,
    text_bbox,
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


# ---------------------------------------------------------------- S3 (R-34)


def test_overlap_area_kanon():
    # cmi `overlap_area`: Intersektionsfläche (0 bei Disjunktheit).
    assert overlap_area((0, 0, 10, 10), (5, 5, 15, 15)) == 25.0
    assert overlap_area((0, 0, 5, 5), (10, 10, 20, 20)) == 0.0


def test_text_bbox_anchor_end_korrektur():
    # cmi `text_bbox`-Kanon: end → x = anchor_x − width.
    t = TextElem("lbl-a", "ABCDE", 10, 100, 200, "end")
    w = estimate_width("ABCDE", 10)
    x0, y0, x1, y1 = text_bbox(t)
    assert x0 == 100 - w
    assert x1 == 100
    # Baseline: Oberkante y − 0.85·fs, Unterkante y + 0.25·fs.
    assert y0 == 200 - 0.85 * 10
    assert y1 == 200 + 0.25 * 10


def test_text_bbox_anchor_middle_korrektur():
    # cmi `text_bbox`-Kanon: middle → x = anchor_x − width/2.
    t = TextElem("lbl-a", "ABCDE", 10, 100, 200, "middle")
    w = estimate_width("ABCDE", 10)
    x0, _, x1, _ = text_bbox(t)
    assert x0 == 100 - w / 2
    assert x1 == 100 + w / 2


def _tank() -> Component:
    return Component.model_validate(
        {"id": "p", "type": "tank-buffer", "at": [500, 300]}
    )


def test_text_box_edge_hit_when_mostly_inside():
    # Label mit >50 % Text-Fläche in der Tank-BBox → text-box-edge.
    t = TextElem("lbl-tank", "Tank-Text", 14, 500, 300, "middle")
    cols = detect_collisions([t], [], components=[_tank()])
    assert len(cols) == 1
    c = cols[0]
    assert c.kind == "text-box-edge"
    assert c.elem_a == "lbl-tank" and c.elem_b == "comp-p"
    assert "50 %" in c.note or "R-34" in c.note


def test_text_box_edge_allowed_below_threshold():
    # Text knapp an der Kante (< 50 % Overlap-Anteil) → keine Kollision
    # („Text neben Symbol" erlaubt, R-34-Schwelle).
    # Tank-BBox: (470,240)-(530,360). Ende-Text endet 5 px in der Kante:
    # Overlap-Anteil ≈ 5/29 ≈ 17 % < 50 %.
    t = TextElem("lbl-edge", "Kurz", 14, 475, 300, "end")
    cols = detect_collisions([t], [], components=[_tank()])
    assert [c for c in cols if c.kind == "text-box-edge"] == []


def test_symbol_text_hit_readout_on_symbol():
    # Readout-Label-Text über der Pumpe (USE×TEXT > 50 %) → symbol-text.
    # Pump-BBox: (380,287)-(420,322) bei at=(400,300). End-Text endet auf
    # der rechten Kante (x=420): Overlap ≈ 54 % der Text-Fläche.
    p = Component.model_validate(
        {"id": "p1", "type": "pump", "at": [400, 300]}
    )
    t = TextElem(
        "readout-a1.lbl", "P-Überdeckung", 11, 420, 314, "end",
        size_kind="label",
    )
    cols = detect_collisions([t], [], components=[p])
    kinds = [c.kind for c in cols]
    assert "symbol-text" in kinds
    assert "text-box-edge" not in kinds  # Readout-Text ≠ lbl-*
    c = next(c for c in cols if c.kind == "symbol-text")
    assert c.elem_a == "readout-a1.lbl" and c.elem_b == "comp-p1"


def test_symbol_box_no_false_positive_when_far():
    # Text weit vom Symbol entfernt → keine symbol-text-Kollision.
    p = _tank()
    t = TextElem("lbl-far", "Fern", 14, 100, 100, "start")
    cols = detect_collisions([t], [], components=[p])
    assert cols == []


def test_readout_size_gate_ok_default_classes():
    # Emissions-Größen (12/11 px) → kein readout-size-Problem.
    v = TextElem("readout-a1.val", "–", 12, 10, 10, "start",
                 size_kind="value")
    lbl = TextElem("readout-a1.lbl", "a1", 11, 10, 24, "start",
                   size_kind="label")
    assert detect_collisions([v, lbl], []) == []


def test_readout_size_gate_mutated_classes_fail():
    # Mutierte Emissions-Klassen (Wert 11 px, Label 10 px) → Gate schlägt
    # an (direkter QA-API-Test, R-34).
    v = TextElem("readout-a1.val", "–", 11, 10, 10, "start",
                 size_kind="value")
    lbl = TextElem("readout-a1.lbl", "a1", 10, 10, 24, "start",
                   size_kind="label")
    cols = detect_collisions([v, lbl], [])
    assert [c.kind for c in cols] == ["readout-size", "readout-size"]
    assert all("R-34" in c.note for c in cols)


def test_symbol_text_deduplicated_one_per_pair():
    # Ein (Text, Symbol)-Paar → genau eine Kollision (kein Doppelzählen
    # je Symbol-Element).
    p = _tank()
    t = TextElem("lbl-on", "Tank-Text", 14, 500, 300, "middle")
    cols = detect_collisions([t], [], components=[p])
    assert len(cols) == 1
    assert cols[0].kind == "text-box-edge"


# ------------------------------------------------------ S4-L1 (R-35):
# GROUP-BOX-Gate (Overlap zweier Makro-Boxen, > 50 % der kleineren Box).


def _group(gid: str, at: tuple[int, int], size: tuple[int, int]) -> Group:
    return Group.model_validate({
        "id": gid, "members": [], "at": list(at), "size": list(size),
    })


def test_group_box_kanon():
    g = _group("g1", (80, 60), (300, 180))
    assert group_box(g) == (80.0, 60.0, 380.0, 240.0)


def test_group_box_overlap_collides():
    # g1: 50..450, g2: 200..600 → Overlap = 250×400 px = 62,5 % der
    # kleineren Box (400×400) (> 50 %) → Kollision.
    g1 = _group("g1", (50, 50), (400, 400))
    g2 = _group("g2", (200, 50), (400, 400))
    cols = detect_collisions([], [], groups=[g1, g2])
    assert len(cols) == 1
    c = cols[0]
    assert c.kind == "group-box"
    assert {c.elem_a, c.elem_b} == {"group-g1", "group-g2"}
    assert c.x == 50 and c.y == 50
    assert "R-35" in c.note
    assert c.line().startswith("GROUP-BOX")


def test_group_box_no_overlap_clean():
    g1 = _group("g1", (0, 0), (100, 100))
    g2 = _group("g2", (200, 0), (100, 100))
    assert detect_collisions([], [], groups=[g1, g2]) == []


def test_group_box_touching_edges_clean():
    # Exakt aneinanderliegende Kanten (Overlap 0) → keine Kollision.
    g1 = _group("g1", (0, 0), (100, 100))
    g2 = _group("g2", (100, 0), (100, 100))
    assert detect_collisions([], [], groups=[g1, g2]) == []


def test_group_box_below_threshold_clean():
    # 400×400 × 100×100, Overlap 50×100 = 50 % der kleineren Box
    # (nicht > 50 %) → „Boxen über Eck erlaubt" (R-35-Schwelle).
    g1 = _group("g1", (0, 0), (400, 400))
    g2 = _group("g2", (350, 0), (100, 100))
    assert detect_collisions([], [], groups=[g1, g2]) == []


def test_group_box_threshold_exceeds_collides():
    # Überstand 390 px → Overlap 60×100 = 60 % der kleineren Box
    # (> 50 %) → Kollision (Schwellen-Grenze).
    g1 = _group("g1", (0, 0), (400, 400))
    g2 = _group("g2", (340, 0), (100, 100))
    cols = detect_collisions([], [], groups=[g1, g2])
    assert [c.kind for c in cols] == ["group-box"]


def test_group_box_one_per_pair_deterministic():
    # 3 Gruppen → C(3,2) = 3 Kollisionen, Schema-Reihenfolge
    # (jedes Paar > 50 % der kleineren Box).
    g1 = _group("g1", (50, 50), (400, 400))
    g2 = _group("g2", (150, 100), (400, 400))
    g3 = _group("g3", (100, 200), (400, 400))
    cols = detect_collisions([], [], groups=[g1, g2, g3])
    assert [c.kind for c in cols] == ["group-box", "group-box", "group-box"]
    pairs = {(c.elem_a, c.elem_b) for c in cols}
    assert pairs == {
        ("group-g1", "group-g2"), ("group-g1", "group-g3"),
        ("group-g2", "group-g3"),
    }


def test_group_box_single_group_never_collides():
    g1 = _group("g1", (0, 0), (400, 400))
    assert detect_collisions([], [], groups=[g1]) == []


def test_group_box_empty_groups_default_clean():
    assert detect_collisions([], []) == []


def test_dedup_two_components_one_collision_each():
    # Zwei Komponenten, ein Text über beide → je eine Kollision (dedup
    # pro Paar, nicht pro BBox-Element).
    p1 = _tank()
    p2 = Component.model_validate(
        {"id": "q", "type": "valve-2way", "at": [500, 300]}
    )
    t = TextElem("lbl-a", "X", 14, 500, 300, "middle")
    cols = detect_collisions([t], [], components=[p1, p2])
    pair_cols = [c for c in cols if c.elem_b in ("comp-p", "comp-q")]
    assert {c.elem_b for c in pair_cols} == {"comp-p", "comp-q"}
