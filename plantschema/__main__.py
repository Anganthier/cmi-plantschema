"""CLI: `python -m plantschema <load|validate|render|check>`.

Exit-Codes (Kanon):
  0 = ok
  2 = Schema-/Validierungsfehler (Probleme nach Stderr, je Problem eine
      Zeile: `[line N] path: message`, bei unbekannter Zeile `[?]`)
  3 = Gate-Fehler (Kollisionen, je Kollision eine Zeile; davor optional
      der Warnungs-Block „N Warnung(en):" (R-33, Exit bleibt 0))
  4 = IO-Fehler (Datei fehlt/lesbar/ungültiges YAML)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .emit import compute_layout, render
from .io import SchemaLoadError, load_schema
from .layout import resolve
from .model import SchemaError
from .place import collect_slot_warnings
from .qa import detect_collisions, texts_for_schema
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


def _run_gate(schema, no_gate: bool) -> int:
    """Gate-Prüfung (S3, R-34): Exit 0 (sauber) oder 3 (Kollisionen).

    Report (R-34-Format): optionaler Warnungs-Block „N Warnung(en):"
    (R-33-Slot-Fallbacks, Exit bleibt 0), dann je Kollision eine Zeile
    `KIND  [elemA] × [elemB] @ (x,y) — Hinweis` + Summe; bei 0
    Kollisionen: kein Kollisions-Block (Exit 0).
    """
    if no_gate:
        return EXIT_OK
    pipes, _readout_pos = compute_layout(schema)
    texts = texts_for_schema(schema)
    warnings = collect_slot_warnings(schema)
    if warnings:
        sys.stderr.write(f"{len(warnings)} Warnung(en):\n")
        for w in warnings:
            sys.stderr.write(
                f"  SLOT-FALLBACK  [{w.elem_id}] @ comp-{w.comp_id} "
                f"({w.direction}) — {w.note}\n"
            )
    collisions = detect_collisions(
        texts, pipes,
        components=schema.components,
        readouts=schema.readouts,
        labels=schema.labels,
        groups=schema.groups,
    )
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

    # S4-L2 (R-36): Mikro-Layout ZWISCHEN load und validate — danach
    # arbeiten validate/check/render alle auf dem resolved Layout.
    schema = resolve(schema)

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
