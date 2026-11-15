"""In-process-CLI-Tests: `main(argv)` direkt (Coverage für __main__.py).

Die Subprocess-Tests (`test_cli.py`) decken den echten E2E-Path; hier
werden die `main()`-Branches in einem Prozess ausgeführt (Capture von
stdout/stderr via `capsys`).
"""

from __future__ import annotations

import io as _io
from contextlib import redirect_stderr, redirect_stdout

import pytest
from conftest import fx

from plantschema import __main__ as m
from plantschema.__main__ import EXIT_GATE, EXIT_IO, EXIT_OK, EXIT_SCHEMA


def call(*argv: str) -> tuple[int, str]:
    out, err = _io.StringIO(), _io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = m.main(list(argv))
    return rc, err.getvalue()


def test_load_ok():
    rc, err = call("load", "--in", str(fx("minimal")))
    assert rc == EXIT_OK
    assert err.strip() == ""


def test_validate_ok():
    rc, _ = call("validate", "--in", str(fx("minimal")))
    assert rc == EXIT_OK


def test_validate_exit2_problems():
    rc, err = call("validate", "--in", str(fx("invalid")))
    assert rc == EXIT_SCHEMA
    assert "doppelte ID 'b-vl'" in err
    assert "Komponente 'ghost'" in err


def test_check_exit3_collision():
    rc, err = call("check", "--in", str(fx("colliding")))
    assert rc == EXIT_GATE
    assert "TEXT-TEXT" in err
    assert "Kollision" in err


def test_check_exit0_clean():
    rc, _ = call("check", "--in", str(fx("minimal")))
    assert rc == EXIT_OK


def test_check_no_gate_suppresses(tmp_path):
    rc, _ = call("check", "--in", str(fx("colliding")), "--no-gate")
    assert rc == EXIT_OK


def test_render_exit2_invalid_no_write(tmp_path):
    out = tmp_path / "x.svg"
    rc, err = call("render", "--in", str(fx("invalid")), "--out", str(out))
    assert rc == EXIT_SCHEMA
    assert "Problems" in err or "Problem(e)" in err
    assert not out.exists()


def test_render_write_failure_exit4(tmp_path):
    # /proc ist lesbar aber kein Verzeichnis → Write-OSError.
    out = "/proc/nonexistent-xyz/x.svg"
    rc, err = call("render", "--in", str(fx("minimal")), "--out", out)
    assert rc == EXIT_IO
    assert "SVG-Write fehlgeschlagen" in err


def test_render_exit3_with_gate(tmp_path):
    out = tmp_path / "c.svg"
    rc, err = call("render", "--in", str(fx("colliding")), "--out", str(out))
    assert rc == EXIT_GATE
    assert out.exists()  # SVG wird geschrieben, dann Gate schlägt
    assert "TEXT-TEXT" in err


def test_render_no_gate_exit0(tmp_path):
    out = tmp_path / "c.svg"
    rc, _ = call("render", "--in", str(fx("colliding")), "--out", str(out),
                 "--no-gate")
    assert rc == EXIT_OK
    assert out.exists()


def test_missing_input_exit4(tmp_path):
    rc, err = call("load", "--in", str(tmp_path / "fehlt.yaml"))
    assert rc == EXIT_IO
    assert "nicht lesbar" in err


def test_invalid_yaml_exit4(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: [unclosed\n  x: 1\n", encoding="utf-8")
    rc, err = call("load", "--in", str(bad))
    assert rc == EXIT_IO
    assert "ungültiges YAML" in err
    assert "[line" in err


def test_model_error_exit2(tmp_path):
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
    rc, err = call("validate", "--in", str(bad))
    assert rc == EXIT_SCHEMA
    assert "components.0.id" in err


def test_parser_rejects_unknown_command():
    with pytest.raises(SystemExit):
        m.build_parser().parse_args(["bogus"])


def test_parser_requires_in():
    with pytest.raises(SystemExit):
        m.build_parser().parse_args(["load"])


def test_parser_render_requires_out():
    with pytest.raises(SystemExit):
        m.build_parser().parse_args(["render", "--in", "x.yaml"])


def test_version_attr():
    from plantschema import __version__

    assert __version__ == "0.1.0"
