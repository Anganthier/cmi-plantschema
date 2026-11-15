"""Validierungs-Stufe der Pipeline: Referenz- und Plausibilitäts-Checks.

`validate(schema)` → Liste aller Probleme (leere Liste = valide).
Probleme werden von der CLI mit Exit 2 ausgegeben (je Problem eine Zeile).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from . import symbols
from .model import Component, Schema

__all__ = ["MIN_CANVAS", "Problem", "problem_lines", "validate"]

#: Minimum-Canvas-Größe (S1-Plausibilität; cmi-Gesamt-Schema: 2200×1500).
MIN_CANVAS: int = 100


@dataclass(frozen=True, slots=True)
class Problem:
    """Ein Validierungs-Problem (Code + menschenlesbare Meldung + Feldpfad)."""

    code: str
    message: str
    path: str

    def line(self) -> str:
        return f"{self.path}: {self.message}"


def _check_ids(schema: Schema, out: list[Problem]) -> None:
    """(a) IDs eindeutig über alle Arten (component/pipe/readout/label)."""
    seen: dict[str, tuple[str, int]] = {}
    for path_kind, i, ident in _all_id_refs(schema):
        if ident in seen:
            kind0, i0 = seen[ident]
            out.append(
                Problem(
                    "dup-id",
                    f"doppelte ID {ident!r} (bereits {kind0}[{i0}])",
                    f"{path_kind}[{i}].id",
                )
            )
        else:
            seen[ident] = (path_kind, i)


def _all_id_refs(schema: Schema) -> Iterable[tuple[str, int, str]]:
    for i, c in enumerate(schema.components):
        yield "components", i, c.id
    for i, p in enumerate(schema.pipes):
        yield "pipes", i, p.id
    for i, r in enumerate(schema.readouts):
        yield "readouts", i, r.id
    for i, lbl in enumerate(schema.labels):
        yield "labels", i, lbl.id


def _check_pipe_refs(
    schema: Schema, ports_by_comp: dict[str, frozenset[str]], out: list[Problem]
) -> None:
    """(b)+(c) Pipe-Enden: Komponente existiert; Port existiert im Typ-Katalog."""
    for p in schema.pipes:
        for end in ("from", "to"):
            ref = p.from_ if end == "from" else p.to
            base = f"pipes[id={p.id}].{end}"
            comp = _find_component(schema, ref.comp)
            if comp is None:
                out.append(
                    Problem(
                        "ref-component",
                        f"Komponente {ref.comp!r} existiert nicht",
                        f"{base}.comp",
                    )
                )
                continue
            if ref.port not in ports_by_comp[comp.id]:
                allowed = sorted(ports_by_comp[comp.id])
                out.append(
                    Problem(
                        "ref-port",
                        f"Port {ref.port!r} nicht zulässig für "
                        f"{comp.type!r} (erlaubt: {', '.join(allowed)})",
                        f"{base}.port",
                    )
                )


def _check_readouts(
    schema: Schema, ports_by_comp: dict[str, frozenset[str]], out: list[Problem]
) -> None:
    """(d) Readout.at: comp/port existieren ODER {x,y} im Canvas-Bereich."""
    w, h = schema.canvas.width, schema.canvas.height
    for r in schema.readouts:
        base = f"readouts[id={r.id}].at"
        if r.at.is_ref:
            comp = _find_component(schema, r.at.comp)  # type: ignore[arg-type]
            if comp is None:
                out.append(
                    Problem(
                        "ref-component",
                        f"Komponente {r.at.comp!r} existiert nicht",
                        f"{base}.comp",
                    )
                )
                continue
            if r.at.port not in ports_by_comp[comp.id]:
                out.append(
                    Problem(
                        "ref-port",
                        f"Port {r.at.port!r} nicht zulässig für {comp.type!r}",
                        f"{base}.port",
                    )
                )
        else:
            x = r.at.x or 0
            y = r.at.y or 0
            if x > w or y > h:
                out.append(
                    Problem(
                        "out-of-canvas",
                        f"Position ({x},{y}) liegt außerhalb des "
                        f"Canvas {w}×{h}",
                        base,
                    )
                )


def _check_labels(schema: Schema, out: list[Problem]) -> None:
    """(f) Label-Placement (R-32/R-33, S3) + Canvas-Bereich.

    - `at` ODER `comp` (+ optional `port`), aber nicht beides/keines →
      `label-placement`.
    - `at`: exakt im Canvas (x/y dürfen Rand berühren, nicht übertreffen).
    - `comp`: Auto-Slot-Position (place.label_position) im Canvas.
    """
    from . import place

    w, h = schema.canvas.width, schema.canvas.height
    for lbl in schema.labels:
        base = f"labels[id={lbl.id}]"
        if (lbl.at is None) == (lbl.comp is None):
            out.append(
                Problem(
                    "label-placement",
                    "Label braucht entweder `at` ODER `comp` (+ optional "
                    f"`port`), nicht beides und nicht keines (ist: "
                    f"at={lbl.at!r}, comp={lbl.comp!r})",
                    base,
                )
            )
            continue
        pos = place.label_position(lbl, schema)
        if pos is None:
            continue
        if pos[0] > w or pos[1] > h:
            field = "at" if lbl.at is not None else f"comp={lbl.comp!r}"
            out.append(
                Problem(
                    "out-of-canvas",
                    f"Position ({pos[0]},{pos[1]}) liegt außerhalb des "
                    f"Canvas {w}×{h}",
                    f"{base}.{field}",
                )
            )


def _check_label_refs(
    schema: Schema, ports_by_comp: dict[str, frozenset[str]], out: list[Problem]
) -> None:
    """(g) Label.comp/port (S3): Komponente existiert + Port gilt für Typ."""
    for i, lbl in enumerate(schema.labels):
        if lbl.comp is None:
            continue
        base = f"labels[{i}]"
        comp = _find_component(schema, lbl.comp)
        if comp is None:
            out.append(
                Problem(
                    "label-comp-ref",
                    f"Komponente {lbl.comp!r} existiert nicht",
                    f"{base}.comp",
                )
            )
            continue
        if lbl.port is not None and lbl.port not in ports_by_comp[comp.id]:
            allowed = sorted(ports_by_comp[comp.id])
            out.append(
                Problem(
                    "label-port-ref",
                    f"Port {lbl.port!r} nicht zulässig für "
                    f"{comp.type!r} (erlaubt: {', '.join(allowed)})",
                    f"{base}.port",
                )
            )


def _check_canvas(schema: Schema, out: list[Problem]) -> None:
    """(e) Canvas-Größe plausibel (width/height > 100)."""
    for dim in ("width", "height"):
        v = getattr(schema.canvas, dim)
        if v <= MIN_CANVAS:
            out.append(
                Problem(
                    "canvas-too-small",
                    f"canvas.{dim}={v} zu klein (muss > {MIN_CANVAS})",
                    f"canvas.{dim}",
                )
            )


def _check_component_types(schema: Schema, out: list[Problem]) -> None:
    """S1-Erweiterung: Komponententyp bekannt (Katalog in symbols.py)."""
    known = symbols.known_types()
    for i, c in enumerate(schema.components):
        if c.type not in known:
            out.append(
                Problem(
                    "unknown-type",
                    f"Komponententyp {c.type!r} unbekannt "
                    f"(bekannt: {', '.join(sorted(known))})",
                    f"components[{i}].type",
                )
            )
    for i, c in enumerate(schema.components):
        if c.ports is not None:
            known_ports = symbols.port_names(c.type)
            for port in c.ports:
                if port not in known_ports:
                    out.append(
                        Problem(
                            "ref-port",
                            f"Port-Override {port!r} nicht im Typ-Katalog "
                            f"{c.type!r}",
                            f"components[{i}].ports",
                        )
                    )


def _find_component(schema: Schema, comp_id: str) -> Component | None:
    for c in schema.components:
        if c.id == comp_id:
            return c
    return None


def _ports_by_comp(schema: Schema) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for c in schema.components:
        if symbols.is_known_type(c.type):
            out[c.id] = symbols.allowed_ports(c.type, c.ports)
        else:
            out[c.id] = frozenset()
    return out


def validate(schema: Schema) -> list[Problem]:
    """Alle S1-Prüfungen ausführen; leere Liste = valide."""
    out: list[Problem] = []
    _check_canvas(schema, out)
    _check_ids(schema, out)
    _check_component_types(schema, out)
    ports = _ports_by_comp(schema)
    _check_pipe_refs(schema, ports, out)
    _check_readouts(schema, ports, out)
    _check_label_refs(schema, ports, out)
    _check_labels(schema, out)
    return out


def problem_lines(problems: Iterable[Problem]) -> list[str]:
    """CLI-Stderr-Format: eine Zeile je Problem (Kanon: `path: message`)."""
    return [p.line() for p in problems]
