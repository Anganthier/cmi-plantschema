"""S4-L4: Layout-Test-Ladegerade — synthetische Stufen L00 (trivial) …
L06 (Stress-Multi) + Negativ-Stufe(n). S4-L5a (R-38): Nested-Groups-
Stufen L07-hier-01 … L09-hier-03 (eigene, aufbauende Serie). S4-L5b
(R-39/R-40): Lanes + Junction-Stufen L10-lane-01 … L12-lane-03.
S4-L5c: hidden_kinds-Stufe L13-hidden-01.

Je positiver Stufe (parametrisiert über `conftest.ladder_levels()`):
1. `validate` exit 0
2. `check` exit 0 — 0 Kollisionen UND 0 Warnungen (leerer stderr)
3. `render` exit 0 + XML-wohlgeformt (`ET.parse`)
4. Byte-Determinismus: 2× `render` (getrennte Prozesse, verschiedene
   `PYTHONHASHSEED`) → sha256-identisch

Zusätzlich: Stufen-Spezifikation (Gruppen/Komponenten/Pipes, aufbauend),
R-37-Kanal-Detours unter Last, Negativ-Stufe (GROUP-BOX → exit 3) und
Regression des S4-L4-Engine-Fixes (Slot-Evaluation = emittierte Route).
"""

from __future__ import annotations

import hashlib
import io as _io
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from conftest import fx, ladder_levels, ladder_negatives

from plantschema import __main__ as m
from plantschema import place
from plantschema.__main__ import EXIT_GATE, EXIT_OK
from plantschema.emit import compute_layout
from plantschema.io import load_schema
from plantschema.layout import resolve
from plantschema.model import Pipe, PortRef
from plantschema.route import schema_routes

ROOT = Path(__file__).parent.parent
CMD = [sys.executable, "-m", "plantschema"]

LEVELS = ladder_levels()
NEGATIVES = ladder_negatives()

#: Stufen-Spezifikation (S4-L4): (Gruppen, Komponenten, Pipes).
LEVEL_SPEC: dict[str, tuple[int, int, int]] = {
    "L00": (1, 2, 1),
    "L01": (1, 4, 4),
    "L02": (3, 6, 6),
    "L03": (5, 10, 13),
    "L04": (5, 13, 17),
    "L05": (6, 18, 22),
    "L06": (7, 24, 31),
    # S4-L5a (R-38): Nested-Groups-Serie (Gruppen inkl. composites).
    "L07-hier-01": (5, 5, 3),
    "L08-hier-02": (5, 5, 4),
    "L09-hier-03": (9, 10, 10),
    # S4-L5b (R-39/R-40): Lanes + Junctions.
    "L10-lane-01": (2, 4, 5),
    "L11-lane-02": (3, 9, 9),
    "L12-lane-03": (6, 13, 13),
    # S4-L5c: hidden_kinds ([ctl]) + Lane mit frame: false.
    "L13-hidden-01": (2, 5, 4),
}

#: Aufbauende Serien (Monotonie gilt je Serie): S4-L4-Basis + S4-L5a-hier.
SERIES: tuple[tuple[str, ...], ...] = (
    ("L00", "L01", "L02", "L03", "L04", "L05", "L06"),
    ("L07-hier-01", "L08-hier-02", "L09-hier-03"),
    ("L10-lane-01", "L11-lane-02", "L12-lane-03"),
    ("L13-hidden-01",),
)

#: (Lanes, Pipes in Lanes, junctions) je Lane-Stufe (R-39/R-40).
LANE_SPEC: dict[str, tuple[int, int, int]] = {
    "L10-lane-01": (2, 5, 0),
    "L11-lane-02": (2, 8, 1),
    "L12-lane-03": (3, 11, 2),
    "L13-hidden-01": (2, 2, 0),
}

#: Explizit erwartete Warnungen (Spez S4-L5b §7: nur L12, enge Lane).
#: Alle anderen Stufen: leerer stderr.
EXPECTED_STDERR: dict[str, str] = {
    "L12-lane-03": (
        "1 Warnung(en):\n"
        "  LANE-FALLBACK  [lane-lane_r] — 3 Pipes passen nicht in die Box "
        "(size=(400, 12)) → Spurabstand 5 px statt 10 px (R-39)\n"
    ),
}

#: (composites, atomare Gruppen) je Nested-Groups-Stufe (R-38).
HIER_SPEC: dict[str, tuple[int, int]] = {
    "L07-hier-01": (2, 3),
    "L08-hier-02": (2, 3),
    "L09-hier-03": (3, 6),
}


def call(*argv: str) -> tuple[int, str]:
    out, err = _io.StringIO(), _io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = m.main(list(argv))
    return rc, err.getvalue()


def run_cli(*args: str, cwd: Path, hashseed: str = "0") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONHASHSEED"] = hashseed
    return subprocess.run(
        [*CMD, *args], cwd=cwd, capture_output=True, text=True, env=env,
    )


def _resolved(path: Path):
    return resolve(load_schema(path))


def _ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


def _level(stem: str) -> Path:
    return next(p for p in LEVELS if p.stem == stem)


# ---------------------------------------------------------------- Ladder-Set


def test_ladder_set_complete():
    """Genau L00 … L09-hier-03 (aufsteigend) + mindestens eine Negativ-Stufe."""
    assert _ids(LEVELS) == sorted(LEVEL_SPEC)
    assert [p.name for p in NEGATIVES] == ["group-box-overlap.yaml"]


@pytest.mark.parametrize("path", LEVELS, ids=_ids(LEVELS))
def test_level_spec_counts(path: Path):
    s = _resolved(path)
    assert (len(s.groups), len(s.components), len(s.pipes)) == LEVEL_SPEC[path.stem]


@pytest.mark.parametrize("series", SERIES, ids=[s[0] for s in SERIES])
def test_levels_build_up_monotonically(series: tuple[str, ...]):
    """Aufbauend je Serie: Gruppen/Komponenten/Pipes wachsen (nicht
    fallend), letzte Stufe > erste (L06 > L00, L09 > L07)."""
    assert set(series) <= set(_ids(LEVELS))
    counts = [LEVEL_SPEC[stem] for stem in series]
    for prev, nxt in zip(counts, counts[1:], strict=False):
        assert all(b >= a for a, b in zip(prev, nxt, strict=True))
    if len(series) > 1:  # S4-L5c: L13 = eigene 1-Stufen-Serie
        assert all(b > a for a, b in zip(counts[0], counts[-1], strict=True))


def test_series_cover_all_levels():
    assert sorted(stem for s in SERIES for stem in s) == sorted(LEVEL_SPEC)


@pytest.mark.parametrize("stem", sorted(HIER_SPEC))
def test_hier_levels_composite_counts(stem: str):
    s = _resolved(_level(stem))
    kinds = [g.kind for g in s.groups]
    assert (kinds.count("composite"), kinds.count("atomic")) == HIER_SPEC[stem]


def test_l00_trivial_hub_only():
    s = _resolved(LEVELS[0])
    (g,) = s.groups
    assert g.members == [g.hub]
    hub = next(c for c in s.components if c.id == g.hub)
    assert hub.type == "tank-buffer"
    # Hub-Zentrierung (R-36): Box-Mitte.
    assert hub.at == (g.at[0] + g.size[0] // 2, g.at[1] + g.size[1] // 2)


def test_l06_stress_density():
    s = _resolved(_level("L06"))
    assert {p.kind.value for p in s.pipes} == {"vl", "rl", "ww", "ctl", "gas"}
    assert 8 <= len(s.readouts) <= 12
    assert 15 <= len(s.labels) <= 25
    assert len(s.pipes) >= 30


# ------------------------------------------------- validate / check / render


@pytest.mark.parametrize("path", LEVELS, ids=_ids(LEVELS))
def test_level_validate_exit0(path: Path):
    rc, err = call("validate", "--in", str(path))
    assert rc == EXIT_OK, err
    assert err == ""


@pytest.mark.parametrize("path", LEVELS, ids=_ids(LEVELS))
def test_level_check_exit0_no_collisions_no_warnings(path: Path):
    rc, err = call("check", "--in", str(path))
    assert rc == EXIT_OK, err
    assert "Kollision" not in err
    if path.stem in EXPECTED_STDERR:
        assert err == EXPECTED_STDERR[path.stem]
        return
    assert "Warnung" not in err
    assert err == ""


@pytest.mark.parametrize("path", LEVELS, ids=_ids(LEVELS))
def test_level_render_xml_and_byte_determinism(path: Path, tmp_path: Path):
    digests = []
    for i, seed in enumerate(("0", "12345")):
        out = tmp_path / f"{path.stem}-{i}.svg"
        r = run_cli("render", "--in", str(path), "--out", str(out),
                    cwd=tmp_path, hashseed=seed)
        assert r.returncode == EXIT_OK, r.stderr
        assert r.stderr == EXPECTED_STDERR.get(path.stem, "")
        root = ET.parse(out).getroot()
        assert root.tag.endswith("svg")
        digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
    assert digests[0] == digests[1]


# -------------------------------------------------------- R-37 unter Last


def _route(path: Path, pipe_id: str) -> list[tuple[int, int]]:
    s = _resolved(path)
    pipes, _ = compute_layout(s)
    return next(p.points for p in pipes if p.id == pipe_id)


def test_l02_channel_detour_over_foreign_box():
    """p_vl (g_source → g_storage) kreuzt g_heat → obere Kante (y = 59)."""
    assert _route(LEVELS[2], "p_vl") == [(218, 180), (218, 59), (870, 59), (870, 210)]


def test_l06_channel_detour_under_load():
    """p_solar_rl (g_solar → g_misch) kreuzt g_ww → Kanal y = 519."""
    assert _route(_level("L06"), "p_solar_rl") == [
        (1493, 605), (1493, 519), (438, 519), (438, 300),
    ]


# ------------------------------------------- R-38 (Nested Groups) unter Last


def test_l07_inter_atomic_same_composite_no_detour():
    assert _route(_level("L07-hier-01"), "p_a_buf") == [(158, 230), (460, 230)]


def test_l08_pipes_into_shared_child_no_detour():
    lvl = _level("L08-hier-02")
    assert _route(lvl, "p_l_s") == [(218, 240), (520, 240)]
    assert _route(lvl, "p_s_r") == [(580, 240), (880, 240)]


def test_l08_foreign_children_detour_under_shared_child():
    """p_l_r (g_l → g_r, kein gemeinsamer composite): g_s ist fremd →
    Kanal 1 px unter g_s (y = 381)."""
    assert _route(_level("L08-hier-02"), "p_l_r") == [
        (210, 340), (210, 381), (880, 381), (880, 340),
    ]


def test_l09_detours_atomic_and_composite_foreign_box():
    lvl = _level("L09-hier-03")
    # g_buf → g_mix: g_wood fremd → Kanal unter g_wood (y = 401).
    assert _route(lvl, "p_buf_mix") == [
        (630, 310), (630, 401), (216, 401), (216, 620),
    ]
    # g_wood → g_solar: c_house fremd → Kanal über c_house (y = 79).
    assert _route(lvl, "p_wood_solar_ctl") == [
        (320, 330), (320, 79), (1080, 79), (1080, 170),
    ]
    # gemeinsamer composite c_house → kein Detour.
    assert _route(lvl, "p_heat_ww") == [(580, 620), (675, 620)]


def test_l09_stress_density():
    s = _resolved(_level("L09-hier-03"))
    assert len(s.pipes) == 10
    assert len(s.labels) == 4
    assert all(lbl.comp is not None for lbl in s.labels)


# ------------------------------------------- R-39/R-40 (Lanes + Junction)


@pytest.mark.parametrize("stem", sorted(LANE_SPEC))
def test_lane_levels_counts(stem: str):
    s = _resolved(_level(stem))
    in_lanes = sum(len(lane.pipes) for lane in s.lanes)
    junctions = sum(1 for c in s.components if c.type == "junction")
    assert (len(s.lanes), in_lanes, junctions) == LANE_SPEC[stem]


def test_l10_all_pipes_in_lanes_on_tracks():
    lvl = _level("L10-lane-01")
    s = _resolved(lvl)
    assert {pid for lane in s.lanes for pid in lane.pipes} == {p.id for p in s.pipes}
    # vertikal: Spuren x = 495 / 505; horizontal: y = 400 / 410 / 420.
    assert _route(lvl, "p_v1") == [(290, 120), (495, 120), (495, 240), (685, 240)]
    assert _route(lvl, "p_v2")[1][0] == 505
    assert [_route(lvl, pid)[1][1] for pid in ("p_h1", "p_h2", "p_h3")] == [
        400, 410, 420,
    ]


def test_l11_outside_pipe_keeps_r37_route_and_junction():
    """p_j_out (einzige Nicht-Lane-Pipe) = unveränderter R-37-Pfad
    (Manhattan-Fallback, j1 ungruppiert); j1: 2 ein, 1 aus."""
    lvl = _level("L11-lane-02")
    s = _resolved(lvl)
    lane_pipes = {pid for lane in s.lanes for pid in lane.pipes}
    assert [p.id for p in s.pipes if p.id not in lane_pipes] == ["p_j_out"]
    assert _route(lvl, "p_j_out") == [(294, 500), (120, 500), (120, 280)]
    incoming = [p.id for p in s.pipes if p.to.comp == "j1"]
    outgoing = [p.id for p in s.pipes if p.from_.comp == "j1"]
    assert (len(incoming), len(outgoing)) == (2, 1)
    assert sum(1 for lbl in s.labels if lbl.comp is not None) == 1
    assert len(s.labels) == 2


def test_l12_cross_composite_degenerate_and_tight_lane():
    lvl = _level("L12-lane-03")
    # über die composite-Grenze (c_left → c_right) auf Spur x = 540.
    assert _route(lvl, "p_m2") == [(280, 110), (540, 110), (540, 200), (865, 200)]
    # degeneriert → Manhattan-Gerade (kreuzt lane_mid, keine Warnung).
    assert _route(lvl, "p_m4") == [(320, 520), (859, 520)]
    # enge Lane: Spurabstand halbiert (5 px).
    assert [_route(lvl, pid)[1][1] for pid in ("p_r3", "p_r1", "p_r2")] == [
        311, 316, 321,
    ]
    s = _resolved(lvl)
    kinds = [g.kind for g in s.groups]
    assert (kinds.count("composite"), kinds.count("atomic")) == (2, 4)


# ------------------------------------------------------------------- Negativ


@pytest.mark.parametrize("path", NEGATIVES, ids=_ids(NEGATIVES))
def test_negative_check_exit3_group_box(path: Path):
    rc, err = call("validate", "--in", str(path))
    assert rc == EXIT_OK, err  # gültiges Schema, nur das Gate schlägt an
    rc, err = call("check", "--in", str(path))
    assert rc == EXIT_GATE
    assert "GROUP-BOX  [group-g_source] × [group-g_heat]" in err


def test_negative_cli_e2e_exit3(tmp_path: Path):
    r = run_cli("check", "--in", str(fx("ladder-negative-group-box-overlap")),
                cwd=tmp_path)
    assert r.returncode == EXIT_GATE
    assert "Kollision(en):" in r.stderr


# --------------------------------------- Engine-Fix (S4-L4): Slot-Geometrie


@pytest.mark.parametrize("path", LEVELS, ids=_ids(LEVELS))
def test_slot_eval_uses_emitted_routes(path: Path):
    """Root-Cause-Regression: die Slot-Evaluation (R-32/R-33) prüft gegen
    exakt die emittierte, gruppen-bewusste Route (R-37), nicht gegen den
    nie gezeichneten Manhattan-Fallback. S4-L5c: ausgeblendete Pipes
    (`hidden_kinds`) werden nicht emittiert → nicht in der Slot-Geometrie."""
    s = _resolved(path)
    pipes, _ = compute_layout(s)
    comps = {c.id: c for c in s.components}
    hidden = s.hidden_kind_values
    assert place._all_pipe_segments(s, comps) == [
        p.points for p in pipes if p.kind not in hidden
    ]
    assert schema_routes(s) == [p.points for p in pipes]


def test_l02_no_phantom_slot_warning():
    """Vor dem Fix: Phantom-Fallback p_vl (y = 180) blockierte den up-Slot
    von valve1 → falsche R-33-Warnung `comp-valve1.lbl`."""
    assert place.collect_slot_warnings(_resolved(LEVELS[2])) == []


def test_schema_routes_skips_unknown_endpoint():
    s = _resolved(LEVELS[0])
    s.pipes.append(Pipe(
        id="p_ghost",
        **{"from": PortRef(comp="ghost", port="out")},
        to=PortRef(comp="heat1", port="in"),
        kind="vl",
    ))
    routes = schema_routes(s)
    assert len(routes) == 1
    assert routes[0] == [(190, 200), (410, 200)]
