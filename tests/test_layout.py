"""S4-L2 (R-36): Mikro-Layout-Engine (layout.resolve) +
COMPONENT-OUTSIDE-GROUP-BOX-Gate (detect_collisions) +
`component-placement-missing` (Validierung) + Rich-Fixture
rich-groups-layout (resolve → alle Mitglieder platziert).

Kanon (R-36): Hub-Anker = `hub_at` ?? Box-Mitte (explizites Hub-`at`
gewinnt); Nicht-Hub-Mitglieder in `order`-Reihenfolge (Default:
`members` minus hub), Spalten-Split (erste Hälfte links
x = box.x + 0.28·box.w, zweite Hälfte rechts + 0.72·box.w), Zeilen
gleichmäßig in [box.y + 0.25·box.h, box.y + 0.75·box.h]; Port-
Ortungs-Refinement (genutzte left-only Ports → linke Spalte,
right-only → rechte; mehrdeutig → Spalten-Split-Tiebreak über
`order`); explizites `at` gewinnt immer (Override); reine
Deterministik (gleiche Eingabe → gleiche Koordinaten, ganzzahlig).
E2E/CLI-Gates (check exit 0, Byte-Determinismus, Negativ-Live)
sind in `test_cli_inproc.py` (S4-L2-Block).
"""

from __future__ import annotations

import yaml
from conftest import fx

from plantschema import validate
from plantschema.io import load_schema_text
from plantschema.layout import resolve
from plantschema.model import Schema
from plantschema.qa import detect_collisions


def _schema(**overrides) -> Schema:
    base: dict = {
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


def _comp(cid: str, ctype: str = "pump", at=None) -> dict:
    d: dict = {"id": cid, "type": ctype}
    if at is not None:
        d["at"] = at
    return d


def _at(schema: Schema, cid: str) -> tuple[int, int]:
    comp = next(c for c in schema.components if c.id == cid)
    assert comp.at is not None
    return comp.at


def _group_box() -> dict:
    """Referenz-Box: (10,10)–(410,210) (R-35: at > 0) → linke Spalte
    x = 10 + 0.28·400 = 122, rechte x = 302; Zeilen-Band y = 60..160
    (Mitten: 60/110/160)."""
    return {"at": [10, 10], "size": [400, 200]}


# -------------------------------------------------------------------
# Determinismus


def test_determinism_two_resolves_identical():
    # Gleiche Eingabe (tiefe Kopie) → identische Koordinaten.
    s1 = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b"), _comp("c")],
        groups=[{"id": "g", "members": ["h", "a", "b", "c"], "hub": "h",
                 **_group_box()}],
    ))
    s2 = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b"), _comp("c")],
        groups=[{"id": "g", "members": ["h", "a", "b", "c"], "hub": "h",
                 **_group_box()}],
    ))
    assert [_at(s1, c) for c in ("h", "a", "b", "c")] == \
        [_at(s2, c) for c in ("h", "a", "b", "c")]


def test_determinism_yaml_roundtrip():
    # resolve → YAML-Serialesierung → laden → resolve: stabil.
    s = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b")],
        groups=[{"id": "g", "members": ["h", "a", "b"], "hub": "h",
                 **_group_box()}],
    ))
    text = yaml.safe_dump(s.model_dump(by_alias=True))
    s2 = resolve(load_schema_text(text))
    assert [_at(s, c) for c in ("h", "a", "b")] == \
        [_at(s2, c) for c in ("h", "a", "b")]


def test_all_coords_int_and_deterministic_rounding():
    # Box-Größen mit Bruchfaktor (0.28/0.72/0.25/0.75) → ganzzahlige
    # Ergebnisse (int(round(·))).
    s = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b")],
        groups=[{"id": "g", "members": ["h", "a", "b"], "hub": "h",
                 "at": [10, 10], "size": [100, 99]}],
    ))
    for c in s.components:
        assert c.at is not None
        assert c.at[0] == int(c.at[0]) and c.at[1] == int(c.at[1])


# -------------------------------------------------------------------
# Hub-Zentrierung + Spalten-Split


def test_hub_anchor_is_box_center():
    s = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b")],
        groups=[{"id": "g", "members": ["h", "a", "b"], "hub": "h",
                 **_group_box()}],
    ))
    assert _at(s, "h") == (210, 110)  # Box-Mitte ((10+410)/2, (10+210)/2)


def test_column_split_first_half_left():
    # 2 Nicht-Hub-Mitglieder: a → linke Spalte (x=122, Zeilen-Mitte),
    # b → rechte Spalte (x=298).
    s = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b")],
        groups=[{"id": "g", "members": ["h", "a", "b"], "hub": "h",
                 **_group_box()}],
    ))
    assert _at(s, "a") == (122, 110)
    assert _at(s, "b") == (298, 110)


def test_column_split_three_members_even_distribution():
    # 3 Nicht-Hub-Mitglieder: linke Spalte = ceil(3/2) = 2 Slots
    # (a: y=60, b: y=160), rechte Spalte 1 Slot (c: y=110).
    s = resolve(_schema(
        components=[_comp("h"), _comp("a"), _comp("b"), _comp("c")],
        groups=[{"id": "g", "members": ["h", "a", "b", "c"], "hub": "h",
                 **_group_box()}],
    ))
    assert _at(s, "a") == (122, 60)
    assert _at(s, "b") == (122, 160)
    assert _at(s, "c") == (298, 110)


def test_no_hub_all_members_split():
    # Gruppe ohne hub: alle Mitglieder in den Spalten-Split (2 →
    # je eines links/rechts).
    s = resolve(_schema(
        components=[_comp("a"), _comp("b")],
        groups=[{"id": "g", "members": ["a", "b"], **_group_box()}],
    ))
    assert _at(s, "a") == (122, 110)
    assert _at(s, "b") == (298, 110)


# -------------------------------------------------------------------
# Port-Ortungs-Refinement


def test_left_only_port_forces_left_column():
    # n1 (Mischpunkt, nur `in` genutzt) → linke Spalte; n2 (Mischpunkt,
    # nur `out` genutzt) → rechte Spalte. Ohne Refinement wäre n2
    # (zweites Mitglied) in der ersten Hälfte = links.
    s = resolve(_schema(
        components=[_comp("n1", "mixing"), _comp("n2", "mixing")],
        groups=[{"id": "g", "members": ["n1", "n2"], **_group_box()}],
        pipes=[
            {"id": "p1", "from": {"comp": "n1", "port": "in"},
             "to": {"comp": "n1", "port": "in"}, "kind": "vl"},
            {"id": "p2", "from": {"comp": "n2", "port": "out"},
             "to": {"comp": "n2", "port": "out"}, "kind": "vl"},
        ],
    ))
    assert _at(s, "n1")[0] == 122  # left-only → linke Spalte
    assert _at(s, "n2")[0] == 298  # right-only → rechte Spalte


def test_right_only_port_forces_right_column():
    # Umgekehrte Rollen: n1 out-only (rechts forciert), n2 in-only
    # (links forciert) — Refinement schlägt den order-Split.
    s = resolve(_schema(
        components=[_comp("n1", "mixing"), _comp("n2", "mixing")],
        groups=[{"id": "g", "members": ["n1", "n2"], **_group_box()}],
        pipes=[
            {"id": "p1", "from": {"comp": "n1", "port": "out"},
             "to": {"comp": "n1", "port": "out"}, "kind": "vl"},
            {"id": "p2", "from": {"comp": "n2", "port": "in"},
             "to": {"comp": "n2", "port": "in"}, "kind": "vl"},
        ],
    ))
    assert _at(s, "n1")[0] == 298  # out-only → rechte Spalte
    assert _at(s, "n2")[0] == 122  # in-only → linke Spalte




def test_ambiguous_ports_fall_back_to_split():
    # both ports (left+right) → keine Forcierung → reiner Spalten-Split
    # in order-Reihenfolge.
    s = resolve(_schema(
        components=[_comp("m1"), _comp("m2")],
        groups=[{"id": "g", "members": ["m1", "m2"], **_group_box()}],
        pipes=[
            {"id": "p1", "from": {"comp": "m1", "port": "in"},
             "to": {"comp": "m2", "port": "out"}, "kind": "vl"},
            {"id": "p2", "from": {"comp": "m1", "port": "out"},
             "to": {"comp": "m2", "port": "in"}, "kind": "vl"},
        ],
    ))
    assert _at(s, "m1")[0] == 122  # erst in order → linke Hälfte
    assert _at(s, "m2")[0] == 298


# -------------------------------------------------------------------
# Order-Override + `at`-Override + hub_at


def test_order_override_changes_assignment():
    # order [m2, m1] dreht die Zuordnung gegenüber der members-Default.
    s = resolve(_schema(
        components=[_comp("m1"), _comp("m2")],
        groups=[{"id": "g", "members": ["m1", "m2"], "order": ["m2", "m1"],
                 **_group_box()}],
    ))
    assert _at(s, "m2")[0] == 122
    assert _at(s, "m1")[0] == 298


def test_explicit_at_wins_over_engine():
    s = resolve(_schema(
        components=[_comp("m1", at=[77, 88]), _comp("m2")],
        groups=[{"id": "g", "members": ["m1", "m2"], **_group_box()}],
    ))
    assert _at(s, "m1") == (77, 88)  # unverändert
    assert _at(s, "m2") == (298, 110)  # m2 = zweites Mitglied → rechts


def test_hub_explicit_at_wins():
    s = resolve(_schema(
        components=[_comp("h", at=[42, 42]), _comp("a")],
        groups=[{"id": "g", "members": ["h", "a"], "hub": "h",
                 **_group_box()}],
    ))
    assert _at(s, "h") == (42, 42)
    assert _at(s, "a") == (122, 110)


def test_hub_at_anchor():
    s = resolve(_schema(
        components=[_comp("h"), _comp("a")],
        groups=[{"id": "g", "members": ["h", "a"], "hub": "h",
                 "hub_at": [300, 60], **_group_box()}],
    ))
    assert _at(s, "h") == (300, 60)


# -------------------------------------------------------------------
# Edge-Cases


def test_zero_member_group_only_hub():
    # Gruppe = nur der Hub (0 Nicht-Hub-Mitglieder) → nur Hub am Anker.
    s = resolve(_schema(
        components=[_comp("h")],
        groups=[{"id": "g", "members": ["h"], "hub": "h",
                 **_group_box()}],
    ))
    assert _at(s, "h") == (210, 110)


def test_single_member():
    # 1 Nicht-Hub-Mitglied: Einzel-Element = Box-Mitte-y, Spalten-Split
    # (ein Mitglied → linke Spalte, rechte leer).
    s = resolve(_schema(
        components=[_comp("h"), _comp("a")],
        groups=[{"id": "g", "members": ["h", "a"], "hub": "h",
                 **_group_box()}],
    ))
    assert _at(s, "a") == (122, 110)


def test_hub_at_plus_explicit_hub_at_combo():
    # hub_at-Anchor + explizites `at` des Hubs → explizit gewinnt
    # (hub_at gilt nur, wenn der Hub kein `at` hat).
    s = resolve(_schema(
        components=[_comp("h", at=[11, 22]), _comp("a")],
        groups=[{"id": "g", "members": ["h", "a"], "hub": "h",
                 "hub_at": [300, 60], **_group_box()}],
    ))
    assert _at(s, "h") == (11, 22)


def test_tight_box_gate_flags_outside_member():
    # Enge Box (R-35: at > 0): Pumpe am linke-Spalten-x =
    # 10 + 0.28·60 = 27 (pump-Bounds x0 = −20) → 3 px links außerhalb
    # der Box (10..70) → COMPONENT-OUTSIDE-GROUP-BOX.
    s = _schema(
        components=[_comp("m1")],
        groups=[{"id": "g", "members": ["m1"], "at": [10, 10],
                 "size": [60, 200]}],
    )
    resolve(s)
    cols = detect_collisions(
        [], [], components=s.components, groups=s.groups
    )
    assert [c.kind for c in cols] == ["component-outside-group-box"]
    assert cols[0].elem_a == "comp-m1"
    assert cols[0].elem_b == "group-g"


def test_group_without_at_none_is_not_flagged_as_outside():
    # at-None-Komponente ohne Gruppe: Gate springt nicht auf (0 px
    # Überstand ist unmöglich — die Prüfung wird übersprungen); der
    # Validierungs-Problem-Code ist die korrekte Antwort.
    s = _schema(components=[_comp("loose")])
    assert detect_collisions([], [], components=s.components) == []
    problems = validate.validate(s)
    assert [p.code for p in problems] == ["component-placement-missing"]
    assert problems[0].path == "components[0].at"


# -------------------------------------------------------------------
# Validierung: `component-placement-missing` + `group-order-member`


def test_ungrouped_at_none_is_problem():
    s = _schema(
        components=[_comp("ok", at=[10, 10]), _comp("loose")],
        groups=[{"id": "g", "members": ["ok"], **_group_box()}],
    )
    problems = [p for p in validate.validate(s)
                if p.code == "component-placement-missing"]
    assert len(problems) == 1
    assert problems[0].path == "components[1].at"
    assert "ohne" in problems[0].message


def test_double_membership_at_none_is_problem():
    # Mitglied zweier Gruppen + at:None → nicht-eindeutige
    # Zugehörigkeit → component-placement-missing.
    s = _schema(
        components=[_comp("dup")],
        groups=[
            {"id": "g1", "members": ["dup"], **_group_box()},
            {"id": "g2", "members": ["dup"], "at": [500, 0],
             "size": [100, 100]},
        ],
    )
    problems = [p for p in validate.validate(s)
                if p.code == "component-placement-missing"]
    assert len(problems) == 1
    assert "mehrere" in problems[0].message


def test_grouped_at_none_is_ok():
    s = _schema(
        components=[_comp("ok"), _comp("free", at=[700, 10])],
        groups=[{"id": "g", "members": ["ok"], **_group_box()}],
    )
    assert validate.validate(s) == []


def test_order_not_permutation_is_problem():
    s = _schema(
        components=[_comp("a"), _comp("b"), _comp("c")],
        groups=[{"id": "g", "members": ["a", "b"], "order": ["a", "c"],
                 **_group_box()}],
    )
    problems = [p for p in validate.validate(s)
                if p.code == "group-order-member"]
    assert len(problems) == 1
    assert problems[0].path == "groups[0].order"


# -------------------------------------------------------------------
# Rich-Fixture rich-groups-layout (E2E, s. CLI-Gates)


def test_rich_groups_layout_resolve_places_all():
    s = resolve(load_schema_text(
        fx("rich-groups-layout").read_text(encoding="utf-8")
    ))
    assert all(c.at is not None for c in s.components)
    assert validate.validate(s) == []


def test_rich_groups_layout_all_members_inside_own_box():
    # Engine-Layout ist per Konstruktion „gruppen-kompakt": jedes
    # Mitglied innerhalb der EIGENEN Box (Gate bleibt sauber).
    s = load_schema_text(fx("rich-groups-layout").read_text(encoding="utf-8"))
    resolve(s)
    assert detect_collisions([], [],
                             components=s.components,
                             groups=s.groups,
                             ) == []
