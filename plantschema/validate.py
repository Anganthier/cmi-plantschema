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
    """(a) IDs eindeutig über alle Arten (component/pipe/readout/label/
    group, S4-L1: zusätzlich `group-id-duplicate`)."""
    seen: dict[str, tuple[str, int]] = {}
    for path_kind, i, ident in _all_id_refs(schema):
        if ident in seen:
            kind0, i0 = seen[ident]
            code = (
                "group-id-duplicate"
                if kind0 == "groups" and path_kind == "groups"
                else "lane-id-duplicate"
                if kind0 == "lanes" and path_kind == "lanes"
                else "dup-id"
            )
            out.append(
                Problem(
                    code,
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
    for i, g in enumerate(schema.groups):
        yield "groups", i, g.id
    for i, lane in enumerate(schema.lanes):
        yield "lanes", i, lane.id
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


def _check_groups(schema: Schema, out: list[Problem]) -> None:
    """(h) Gruppen (S4-L1, R-35): Member-/Hub-Referenzen,
    Doppel-Mitgliedschaft, Makro-Box-Geometrie (> 0).

    Gruppen-IDs: doppelte Group-IDs (nur Group×Group) →
    `group-id-duplicate` (via `_check_ids`); Group×fremd-ID bleibt
    `dup-id` (R-5: IDs eindeutig über alle Arten).
    """
    comp_ids = schema.component_ids
    member_owners: dict[str, int] = {}
    for i, g in enumerate(schema.groups):
        base = f"groups[{i}]"
        for m in g.members:
            if m not in comp_ids:
                out.append(Problem(
                    "group-member-ref",
                    f"Member {m!r} existiert nicht als Komponente",
                    f"{base}.members",
                ))
            else:
                owner = member_owners.setdefault(m, i)
                if owner != i:
                    out.append(Problem(
                        "group-double-membership",
                        f"Komponente {m!r} ist Mitglied zweier Gruppen "
                        f"(groups[{owner}] und groups[{i}])",
                        f"{base}.members",
                    ))
        if g.hub is not None:
            if g.hub not in comp_ids:
                out.append(Problem(
                    "group-hub-ref",
                    f"Hub {g.hub!r} existiert nicht als Komponente",
                    f"{base}.hub",
                ))
            elif g.hub not in g.members:
                out.append(Problem(
                    "group-hub-not-member",
                    f"Hub {g.hub!r} muss ∈ members sein "
                    f"(members: {', '.join(g.members)})",
                    f"{base}.hub",
                ))
        # R-36: `order` (falls gesetzt) = Permutation von `members`.
        if g.order is not None and (
            set(g.order) != set(g.members) or len(g.order) != len(g.members)
        ):
                out.append(Problem(
                    "group-order-member",
                    f"`order` muss eine Permutation von `members` sein "
                    f"(members: {', '.join(g.members)}, "
                    f"order: {', '.join(g.order)})",
                    f"{base}.order",
                ))
        if g.at[0] <= 0 or g.at[1] <= 0:
            out.append(Problem(
                "group-geometry",
                f"group.at muss > 0 sein (ist: {g.at!r})",
                f"{base}.at",
            ))
        if g.size[0] <= 0 or g.size[1] <= 0:
            out.append(Problem(
                "group-geometry",
                f"group.size muss > 0 sein (ist: {g.size!r})",
                f"{base}.size",
            ))


def _check_group_nesting(schema: Schema, out: list[Problem]) -> None:
    """(h2) Nested Groups (S4-L5a, R-38): Shape + Include-Referenzen.

    - `group-kind-shape`: composite mit `members`/`hub`/`order`/
      `hub_at` oder ohne `includes`; atomic mit `includes`.
    - `group-include-ref`: `includes`-ID existiert nicht als Gruppe.
    - `group-include-composite`: composite inkludiert composite
      (Tiefe max. 1).
    - `group-include-cycle`: Gruppe liegt auf einem `includes`-Zyklus
      (defensiv; inkl. Self-Include).

    Containment (composite-Box ⊇ Kind-Boxen) ist Geometrie →
    Kollisions-Gate `group-containment` (qa, Exit 3), nicht hier.
    """
    by_id: dict[str, int] = {}
    for i, g in enumerate(schema.groups):
        by_id.setdefault(g.id, i)
    for i, g in enumerate(schema.groups):
        base = f"groups[{i}]"
        if g.kind == "composite":
            if g.members:
                out.append(Problem(
                    "group-kind-shape",
                    "composite-Gruppe darf keine `members` haben (reiner "
                    f"Container, R-38; ist: {', '.join(g.members)})",
                    f"{base}.members",
                ))
            if not g.includes:
                out.append(Problem(
                    "group-kind-shape",
                    "composite-Gruppe braucht nicht-leere `includes` (R-38)",
                    f"{base}.includes",
                ))
            for field in ("hub", "order", "hub_at"):
                if getattr(g, field) is not None:
                    out.append(Problem(
                        "group-kind-shape",
                        f"composite-Gruppe darf kein `{field}` haben "
                        "(reiner Container, R-38)",
                        f"{base}.{field}",
                    ))
        elif g.includes:
            out.append(Problem(
                "group-kind-shape",
                "atomic-Gruppe darf keine `includes` haben (nur "
                f"kind: composite, R-38; ist: {', '.join(g.includes)})",
                f"{base}.includes",
            ))
        for ref in g.includes:
            ci = by_id.get(ref)
            if ci is None:
                out.append(Problem(
                    "group-include-ref",
                    f"Include {ref!r} existiert nicht als Gruppe (R-38)",
                    f"{base}.includes",
                ))
            elif (g.kind == "composite"
                  and schema.groups[ci].kind == "composite"):
                out.append(Problem(
                    "group-include-composite",
                    f"composite {g.id!r} inkludiert composite {ref!r} "
                    "(Tiefe max. 1: nur atomare Gruppen, R-38)",
                    f"{base}.includes",
                ))
    # Zyklus-Erkennung (defensiv): Gruppe g liegt auf einem Zyklus,
    # wenn g von sich selbst über includes-Kanten erreichbar ist.
    edges = {
        i: [by_id[r] for r in g.includes if r in by_id]
        for i, g in enumerate(schema.groups)
    }
    for i, g in enumerate(schema.groups):
        seen: set[int] = set()
        stack = list(edges[i])
        while stack:
            n = stack.pop()
            if n == i:
                out.append(Problem(
                    "group-include-cycle",
                    f"Gruppe {g.id!r} liegt auf einem `includes`-Zyklus "
                    "(R-38)",
                    f"groups[{i}].includes",
                ))
                break
            if n in seen:
                continue
            seen.add(n)
            stack.extend(edges[n])


def _check_lanes(schema: Schema, out: list[Problem]) -> None:
    """(h3) Lanes (S4-L5b, R-39): Geometrie + Pipe-Referenzen.

    - `lane-geometry`: `at`/`size` fehlen oder <= 0.
    - `lane-pipe-ref`: Pipe-ID in `lane.pipes` existiert nicht.
    - `lane-pipe-duplicate`: Pipe steht in > 1 Lane (oder doppelt in
      derselben Lane).
    (`lane-id-duplicate` via `_check_ids`; Lane-Overlap ist Geometrie
    → Kollisions-Gate `lane-box`, Exit 3.)
    """
    pipe_ids = {p.id for p in schema.pipes}
    owners: dict[str, int] = {}
    for i, lane in enumerate(schema.lanes):
        base = f"lanes[{i}]"
        for field in ("at", "size"):
            v = getattr(lane, field)
            if v is None or v[0] <= 0 or v[1] <= 0:
                out.append(Problem(
                    "lane-geometry",
                    f"lane.{field} fehlt oder ist <= 0 (ist: {v!r}; R-39)",
                    f"{base}.{field}",
                ))
        for pid in lane.pipes:
            if pid not in pipe_ids:
                out.append(Problem(
                    "lane-pipe-ref",
                    f"Pipe {pid!r} existiert nicht (R-39)",
                    f"{base}.pipes",
                ))
                continue
            owner = owners.setdefault(pid, i)
            if owner != i or lane.pipes.count(pid) > 1:
                out.append(Problem(
                    "lane-pipe-duplicate",
                    f"Pipe {pid!r} steht in mehreren Lanes "
                    f"(lanes[{owner}] und lanes[{i}]; max. 1, R-39)",
                    f"{base}.pipes",
                ))


def _check_hidden_kinds(schema: Schema, out: list[Problem]) -> None:
    """(h4) S4-L5c: `hidden-pipe-in-lane` — eine Pipe, deren `kind` in
    `hidden_kinds` steht, darf keiner Lane zugeordnet sein (unsichtbare
    Pipe würde eine sichtbare Spur reservieren)."""
    hidden = schema.hidden_kind_values
    if not hidden:
        return
    kinds = {p.id: p.kind.value for p in schema.pipes}
    for i, lane in enumerate(schema.lanes):
        for pid in lane.pipes:
            if kinds.get(pid) in hidden:
                out.append(Problem(
                    "hidden-pipe-in-lane",
                    f"Pipe {pid!r} (kind={kinds[pid]}) ist per "
                    f"hidden_kinds ausgeblendet, steht aber in einer Lane "
                    f"(S4-L5c)",
                    f"lanes[{i}].pipes",
                ))


def _check_component_placement(schema: Schema, out: list[Problem]) -> None:
    """(i) R-36 (S4-L2): Komponente ohne `at` braucht EINAUTIGE
    Gruppenzugehörigkeit (Engine-Placement via `layout.resolve`).

    `at: None` + keine bzw. nicht-eindeutige Gruppenzugehörigkeit
    (Doppel-Mitgliedschaft) → `component-placement-missing`
    (Validierungs-Problem, CLI-Exit 2).
    """
    owners: dict[str, int] = {}
    for i, g in enumerate(schema.groups):
        for m in g.members:
            owners.setdefault(m, i)
    for i, c in enumerate(schema.components):
        if c.at is not None:
            continue
        owner = owners.get(c.id)
        if owner is None:
            out.append(Problem(
                "component-placement-missing",
                "Komponente ohne `at` und ohne Gruppenzugehörigkeit "
                "(braucht `at` ODER Mitglied EINER Gruppe, R-36)",
                f"components[{i}].at",
            ))
        else:
            dup = sum(1 for g in schema.groups if c.id in g.members)
            if dup > 1:
                out.append(Problem(
                    "component-placement-missing",
                    f"Komponente ohne `at` ist Mitglied mehrerer Gruppen "
                    f"({dup} Gruppen) — Gruppenzugehörigkeit nicht eindeutig "
                    f"(R-36)",
                    f"components[{i}].at",
                ))


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
    _check_groups(schema, out)
    _check_group_nesting(schema, out)
    _check_lanes(schema, out)
    _check_hidden_kinds(schema, out)
    _check_component_placement(schema, out)
    _check_readouts(schema, ports, out)
    _check_label_refs(schema, ports, out)
    _check_labels(schema, out)
    return out


def problem_lines(problems: Iterable[Problem]) -> list[str]:
    """CLI-Stderr-Format: eine Zeile je Problem (Kanon: `path: message`)."""
    return [p.line() for p in problems]
