"""S4-L4: Layout-Test-Ladegerade — synthetische Stufen L00 (trivial) …
L06 (Stress-Multi) + Negativ-Stufe(n).

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


# ---------------------------------------------------------------- Ladder-Set


def test_ladder_set_complete():
    """Genau L00 … L06 (aufsteigend) + mindestens eine Negativ-Stufe."""
    assert _ids(LEVELS) == sorted(LEVEL_SPEC)
    assert [p.name for p in NEGATIVES] == ["group-box-overlap.yaml"]


@pytest.mark.parametrize("path", LEVELS, ids=_ids(LEVELS))
def test_level_spec_counts(path: Path):
    s = _resolved(path)
    assert (len(s.groups), len(s.components), len(s.pipes)) == LEVEL_SPEC[path.stem]


def test_levels_build_up_monotonically():
    """Aufbauend: Gruppen/Komponenten/Pipes wachsen (nicht fallend), L06 > L00."""
    counts = [LEVEL_SPEC[p.stem] for p in LEVELS]
    for prev, nxt in zip(counts, counts[1:], strict=False):
        assert all(b >= a for a, b in zip(prev, nxt, strict=True))
    assert all(b > a for a, b in zip(counts[0], counts[-1], strict=True))


def test_l00_trivial_hub_only():
    s = _resolved(LEVELS[0])
    (g,) = s.groups
    assert g.members == [g.hub]
    hub = next(c for c in s.components if c.id == g.hub)
    assert hub.type == "tank-buffer"
    # Hub-Zentrierung (R-36): Box-Mitte.
    assert hub.at == (g.at[0] + g.size[0] // 2, g.at[1] + g.size[1] // 2)


def test_l06_stress_density():
    s = _resolved(LEVELS[-1])
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
        assert r.stderr == ""
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
    assert _route(LEVELS[-1], "p_solar_rl") == [
        (1493, 605), (1493, 519), (438, 519), (438, 300),
    ]


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
    nie gezeichneten Manhattan-Fallback."""
    s = _resolved(path)
    pipes, _ = compute_layout(s)
    comps = {c.id: c for c in s.components}
    assert place._all_pipe_segments(s, comps) == [p.points for p in pipes]
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
