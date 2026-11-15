"""CLI: `python -m plantschema <load|validate|render|check>`.

Exit-Codes (Kanon):
  0 = ok
  2 = Schema-/Validierungsfehler (Probleme nach Stderr, je Problem eine
      Zeile: `[line N] path: message`, bei unbekannter Zeile `[?]`)
  3 = Gate-Fehler (Kollisionen, je Kollision eine Zeile)
  4 = IO-Fehler (Datei fehlt/lesbar/ungültiges YAML)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .emit import RO_LBL_FONT, RO_VAL_FONT, TXT_FONT, compute_layout, render
from .io import SchemaLoadError, load_schema
from .model import SchemaError
from .qa import TextElem, detect_collisions
from .validate import problem_lines, validate

__all__ = ["build_parser", "main"]

EXIT_OK = 0
EXIT_SCHEMA = 2
EXIT_GATE = 3
EXIT_IO = 4


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plantschema",
        description="Semantische Anlagen-Schemas → deterministisches P&ID-SVG.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    for name, help_ in (
        ("load", "Parse+Validate (kein Artefakt)"),
        ("validate", "Parse+Validate, Probleme mit Exit 2"),
        ("render", "Pipeline → SVG-Write (Gate aktiv, außer --no-gate)"),
        ("check", "Pipeline in-memory + nur Gate-Report (kein Write)"),
    ):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--in", dest="infile", required=True,
                        help="Pfad zur YAML-Datei")
        if name == "render":
            sp.add_argument("--out", dest="outfile", required=True,
                            help="Pfad der SVG-Ausgabe")
        if name in ("render", "check"):
            sp.add_argument("--no-gate", action="store_true",
                            help="Kollisions-Gate aus (Debug)")
    return p


def _print_schema_errors(exc: SchemaError) -> None:
    sys.stderr.write(exc.format() + "\n")


def _pipeline(schema):
    """route + place + qa-Input (deterministisch, Schema-Reihenfolge).

    S2: Readout-Texte = Wert (`.ro-val`, 12 px) + Label (`.ro-lbl`, 11 px),
    Position/Anker wie emittiert (16 px neben Symbol, `side` → anchor).
    """
    pipes, readout_pos = compute_layout(schema)
    texts: list[TextElem] = []
    for lbl in schema.labels:
        x, y = lbl.at
        texts.append(TextElem(f"lbl-{lbl.id}", lbl.text, TXT_FONT, x, y,
                              lbl.anchor.value))
    for r in schema.readouts:
        x, y = readout_pos[r.id]
        anchor = "start" if r.side == "right" else "end"
        tx = x + (16 if r.side == "right" else -16)
        texts.append(TextElem(f"readout-{r.id}.val", "–", RO_VAL_FONT, tx, y - 2,
                              anchor))
        texts.append(TextElem(f"readout-{r.id}.lbl", r.label, RO_LBL_FONT, tx,
                              y + 14, anchor))
    return pipes, texts


def _run_gate(schema, no_gate: bool) -> int:
    """Gate-Prüfung; Exit 0 (sauber) oder 3 (Kollisionen, Report)."""
    if no_gate:
        return EXIT_OK
    pipes, texts = _pipeline(schema)
    collisions = detect_collisions(texts, pipes)
    if collisions:
        sys.stderr.write(f"{len(collisions)} Kollision(en):\n")
        for c in collisions:
            sys.stderr.write("  " + c.line() + "\n")
        return EXIT_GATE
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        schema = load_schema(args.infile)
    except SchemaLoadError as exc:
        _print_schema_errors(exc)
        return EXIT_IO
    except SchemaError as exc:
        _print_schema_errors(exc)
        return EXIT_SCHEMA

    if args.command in ("load", "validate"):
        problems = validate(schema)
        if problems:
            sys.stderr.write(f"{len(problems)} Problem(e):\n")
            for line in problem_lines(problems):
                sys.stderr.write("  " + line + "\n")
            return EXIT_SCHEMA
        return EXIT_OK

    # render / check: Validierung erst, dann Pipeline + Gate.
    problems = validate(schema)
    if problems:
        sys.stderr.write(f"{len(problems)} Problem(e):\n")
        for line in problem_lines(problems):
            sys.stderr.write("  " + line + "\n")
        return EXIT_SCHEMA

    if args.command == "check":
        return _run_gate(schema, args.no_gate)

    # render: SVG bauen + schreiben.
    svg = render(schema)
    out = Path(args.outfile)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"[?]: SVG-Write fehlgeschlagen: {out} ({exc})\n")
        return EXIT_IO
    return _run_gate(schema, args.no_gate)


if __name__ == "__main__":
    raise SystemExit(main())
