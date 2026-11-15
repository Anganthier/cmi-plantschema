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
