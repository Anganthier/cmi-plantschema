"""S1-4: CLI — alle 4 Subkommandos, Exit-Codes 0/2/3/4, --no-gate, Format."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from conftest import fx

ROOT = Path(__file__).parent.parent
CMD = [sys.executable, "-m", "plantschema"]


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [*CMD, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_load_ok(minimal_schema, tmp_path):
    r = run_cli("load", "--in", str(fx("minimal")), cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_validate_ok(tmp_path):
    r = run_cli("validate", "--in", str(fx("minimal")), cwd=tmp_path)
    assert r.returncode == 0


def test_validate_exit2_both_problems(tmp_path):
    r = run_cli("validate", "--in", str(fx("invalid")), cwd=tmp_path)
    assert r.returncode == 2
    assert "doppelte ID 'b-vl'" in r.stderr
    assert "Komponente 'ghost'" in r.stderr
    # beide Probleme je eine Zeile (Reihenfolge: dup-id vor ref-component).
    lines = [line for line in r.stderr.splitlines() if line.strip()]
    assert "doppelte ID" in lines[1]
    assert "ghost" in lines[2]


def test_render_ok_and_svg_written(tmp_path):
    out = tmp_path / "out" / "minimal.svg"
    r = run_cli("render", "--in", str(fx("minimal")), "--out", str(out),
                cwd=tmp_path)
    assert r.returncode == 0
    assert out.exists()
    assert out.stat().st_size > 500
    content = out.read_text(encoding="utf-8")
    assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_render_deterministic_two_runs(tmp_path):
    o1 = tmp_path / "a.svg"
    o2 = tmp_path / "b.svg"
    for out in (o1, o2):
        r = run_cli("render", "--in", str(fx("minimal")), "--out", str(out),
                    cwd=tmp_path)
        assert r.returncode == 0
    h1 = hashlib.sha256(o1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(o2.read_bytes()).hexdigest()
    assert h1 == h2


def test_check_exit3_on_collision(tmp_path):
    r = run_cli("check", "--in", str(fx("colliding")), cwd=tmp_path)
    assert r.returncode == 3
    assert "Kollision" in r.stderr
    assert "TEXT-TEXT" in r.stderr
    assert "lbl-lbl-a" in r.stderr


def test_check_exit0_when_clean(tmp_path):
    r = run_cli("check", "--in", str(fx("minimal")), cwd=tmp_path)
    assert r.returncode == 0


def test_render_no_gate_exit0_despite_collision(tmp_path):
    out = tmp_path / "c.svg"
    r = run_cli("render", "--in", str(fx("colliding")), "--out", str(out),
                "--no-gate", cwd=tmp_path)
    assert r.returncode == 0
    assert out.exists()


def test_render_rich_fixture_no_gate(tmp_path):
    """S2 E2E (Subprocess): Rich-Fixture → valide SVG, exit 0 (--no-gate).

    Die Rich-Fixture ist S4-Seed und muss NICHT kollisionsfrei sein
    (Gate kommt in S3); mit `--no-gate` ist exit 0 Pflicht.
    """
    out = tmp_path / "rich" / "rich.svg"
    r = run_cli("render", "--in", str(fx("rich")), "--out", str(out),
                "--no-gate", cwd=tmp_path)
    assert r.returncode == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert 'id="comp-puffer"' in content
    assert 'id="pipe-ctl-o8-o3"' in content
    assert 'id="readout-a6_vl"' in content
    assert 'id="lbl-zone-keller"' in content
    # Alle 18 P&ID-Symbole im <defs>.
    for sym in ("pid-tank-buffer", "pid-boiler-oil", "pid-boiler-solid",
                "pid-collector-solar", "pid-heatex-plate", "pid-heatex-shell",
                "pid-mixing", "pid-pump-cent", "pid-valve-2way",
                "pid-valve-3way", "pid-valve-globe", "pid-valve-actuator",
                "pid-throttle", "pid-radiator", "pid-tap", "pid-chimney",
                "pid-pt", "pid-flow-switch"):
        assert f'id="{sym}"' in content, f"{sym} fehlt"


def test_render_rich_gate_status_reported(tmp_path):
    """Rich-Fixture mit Gate: Exit 0 (kollisionsfrei) oder 3 (Report)."""
    out = tmp_path / "rich-gate.svg"
    r = run_cli("render", "--in", str(fx("rich")), "--out", str(out),
                cwd=tmp_path)
    assert r.returncode in (0, 3), f"Rich-Gate: unerwarteter Exit {r.returncode}"
    if r.returncode == 3:
        assert "Kollision" in r.stderr


def test_render_exit2_on_invalid(tmp_path):
    out = tmp_path / "nope.svg"
    r = run_cli("render", "--in", str(fx("invalid")), "--out", str(out),
                cwd=tmp_path)
    assert r.returncode == 2
    assert not out.exists()


def test_missing_input_file_exit4(tmp_path):
    r = run_cli("load", "--in", str(tmp_path / "fehlt.yaml"), cwd=tmp_path)
    assert r.returncode == 4
    assert "nicht lesbar" in r.stderr


def test_invalid_yaml_exit4_with_line(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: [unclosed\n  x: 1\n", encoding="utf-8")
    r = run_cli("load", "--in", str(bad), cwd=tmp_path)
    assert r.returncode == 4
    assert "ungültiges YAML" in r.stderr
    assert "[line" in r.stderr


def test_model_error_exit2_stderr_format(tmp_path):
    bad = tmp_path / "model.yaml"
    bad.write_text(
        "schema: plantschema/v1\n"
        "canvas: { width: 800, height: 500 }\n"
        "components:\n"
        "  - id: 'bad id'\n"
        "    type: pump\n"
        "    at: [0, 0]\n",
        encoding="utf-8",
    )
    r = run_cli("validate", "--in", str(bad), cwd=tmp_path)
    assert r.returncode == 2
    # Kanon-Format: `path: message` (Zeile optional).
    assert "components.0.id" in r.stderr


def test_check_requires_gate_flag_only_for_check_render(tmp_path):
    # load/validate kennen --no-gate nicht (argparse-Fehler → Exit 2).
    r = run_cli("load", "--in", str(fx("minimal")), "--no-gate", cwd=tmp_path)
    assert r.returncode != 0


def test_version_flag(tmp_path):
    r = run_cli("--version", cwd=tmp_path)
    assert r.returncode == 0
    assert "0.1.0" in r.stdout
