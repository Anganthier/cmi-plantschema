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


def test_render_exit0_rich_fixture(tmp_path):
    """S3 E2E: Rich-Fixture rendert (Gate aktiv, 0 Kollisionen)."""
    out = tmp_path / "rich.svg"
    rc, err = call("render", "--in", str(fx("rich")), "--out", str(out))
    assert rc == EXIT_OK, err
    content = out.read_text(encoding="utf-8")
    # S2/S3-Struktur: P&ID-Symbole, Readout-Hooks, Pfeil-Endpunkte, Style.
    assert 'data-symbol="pid-tank-buffer"' in content
    assert 'data-symbol="pid-pump-cent"' in content
    assert 'href="#pid-pt"' in content
    assert "data-value-key" in content and "data-readout" in content
    assert 'class="pipe-arrow arrow-ctl"' in content
    assert ".ro-val{" in content and "stroke-dasharray:6 4" in content


def test_check_exit3_text_box_edge():
    """S3: text-box-Fixture → exit 3 + TEXT-BOX-EDGE-Zeile (R-34)."""
    rc, err = call("check", "--in", str(fx("colliding-text-box")))
    assert rc == EXIT_GATE
    assert "TEXT-BOX-EDGE" in err
    assert "lbl-lbl-tank-text" in err


def test_check_exit3_symbol_text():
    """S3: symbol-text-Fixture → exit 3 + SYMBOL-TEXT-Zeile (R-34)."""
    rc, err = call("check", "--in", str(fx("colliding-symbol-text")))
    assert rc == EXIT_GATE
    assert "SYMBOL-TEXT" in err


# ------------------------------------------------------------ S4-L1 (R-35):
# Gruppen-Fixtures (Positiv: rich-groups; Negativ: group-box-Overlap,
# doppelte Mitgliedschaft).


def test_validate_rich_groups_ok():
    rc, err = call("validate", "--in", str(fx("rich-groups")))
    assert rc == EXIT_OK, err


def test_check_rich_groups_exit0():
    rc, err = call("check", "--in", str(fx("rich-groups")))
    assert rc == EXIT_OK, err
    assert "Kollision" not in err


def test_render_rich_groups_exit0(tmp_path):
    """S4-L1 E2E (R-35): neue Fixture → validate/check/render exit 0,
    SVG mit gbox-Boxen + .gbox-lbl-Label."""
    out = tmp_path / "rich-groups.svg"
    rc, err = call("render", "--in", str(fx("rich-groups")),
                   "--out", str(out))
    assert rc == EXIT_OK, err
    content = out.read_text(encoding="utf-8")
    assert 'id="layer-groups"' in content
    assert 'id="group-g1"' in content and 'id="group-g2"' in content
    assert 'class="gbox"' in content
    assert "Gruppe A" in content  # .gbox-lbl-Text (nur g1 gelabelt)
    assert 'class="gbox-lbl"' in content


def test_check_exit3_group_box_overlap():
    """S4-L1 (R-35): überlappende Gruppen-Boxen → exit 3 +
    GROUP-BOX-Zeile."""
    rc, err = call("check", "--in", str(fx("colliding-group-box")))
    assert rc == EXIT_GATE
    assert "GROUP-BOX" in err
    assert "group-g1" in err and "group-g2" in err


def test_validate_exit2_double_membership():
    """S4-L1 (R-35): doppelte Mitgliedschaft → exit 2 +
    group-double-membership-Zeile."""
    rc, err = call("validate", "--in",
                   str(fx("invalid-double-membership")))
    assert rc == EXIT_SCHEMA
    assert "groups[1].members" in err
    assert "Mitglied zweier Gruppen" in err
    assert "'p1'" in err


def test_check_rich_warn_block_exit0():
    """S3 (R-33): Rich → Warnungs-Block (Slot-Fallbacks), Exit 0."""
    rc, err = call("check", "--in", str(fx("rich")))
    assert rc == EXIT_OK, err
    assert "Warnung(en):" in err
    assert "SLOT-FALLBACK" in err
    assert "Kollision" not in err


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
