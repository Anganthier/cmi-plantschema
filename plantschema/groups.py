"""Nested-Groups-Helfer (S4-L5a, R-38): transitive Gruppen-Mitgliedschaft.

Modell (s. `model.Group`): `kind="atomic"` (Default) = Gruppe mit
`members`; `kind="composite"` = reiner Container ohne `members`, der
atomare Gruppen per `includes` (YAML-ID-Referenz) einschließt. Tiefe
max. 1 (composite inkludiert nur atomic, geprüft in `validate`). Eine
atomare Gruppe darf von MEHREREN composites inkludiert werden
(Venn-Kind, z. B. Puffer in zwei Eltern).

Alle Helfer sind defensiv (unbekannte/zyklische/composite-Includes
werden übersprungen statt zu crashen — `validate` meldet sie) und
deterministisch (Schema-Reihenfolge).

- `transitive_members(g, groups)`: Komponenten-IDs von `g` flach
  (atomic: `members`; composite: `members` aller inkludierten
  atomaren Gruppen).
- `ancestor_groups(g, groups)`: IDs der composite-Gruppen, die `g`
  (transitiv) inkludieren.
- `owner_index(groups)`: Komponente → Index ihrer (ersten) atomaren
  Gruppe (Mitgliedschafts-Anker der Gates/Routing).
- `membership(comp, groups, owner)`: Gruppen-Indizes der transitiven
  Mitgliedschaft einer Komponente (eigene atomare Gruppe + alle
  composite-Ahnen).
- `pipe_foreign_indices(...)`: R-37-Refinement — Indizes der
  „fremden" Boxen einer inter-gruppigen Pipe.
"""

from __future__ import annotations

from collections.abc import Sequence

from .model import Group

__all__ = [
    "ancestor_groups",
    "ancestor_indices",
    "child_indices",
    "is_composite",
    "membership",
    "owner_index",
    "pipe_foreign_indices",
    "transitive_members",
]


def is_composite(g: Group) -> bool:
    """`kind == "composite"` (reiner Container, R-38)."""
    return g.kind == "composite"


def _index(groups: Sequence[Group]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, g in enumerate(groups):
        idx.setdefault(g.id, i)
    return idx


def child_indices(gi: int, groups: Sequence[Group]) -> list[int]:
    """Indizes der von `groups[gi]` inkludierten ATOMAREN Gruppen
    (Include-Reihenfolge, dedupliziert; unbekannte/composite-Ziele und
    Self-Includes übersprungen — `validate`-Probleme)."""
    g = groups[gi]
    if not is_composite(g):
        return []
    idx = _index(groups)
    out: list[int] = []
    for ref in g.includes:
        ci = idx.get(ref)
        if ci is None or ci == gi or is_composite(groups[ci]) or ci in out:
            continue
        out.append(ci)
    return out


def ancestor_indices(gi: int, groups: Sequence[Group]) -> list[int]:
    """Indizes der composite-Gruppen, die `groups[gi]` inkludieren
    (Schema-Reihenfolge). Tiefe max. 1 → direkte Eltern = alle Ahnen."""
    return [
        i for i, g in enumerate(groups)
        if i != gi and is_composite(g) and gi in child_indices(i, groups)
    ]


def transitive_members(g: Group, groups: Sequence[Group]) -> set[str]:
    """Flache transitive Mitgliedschaft (R-38): `members` + `members`
    aller inkludierten atomaren Gruppen."""
    out = set(g.members)
    gi = next((i for i, x in enumerate(groups) if x is g), None)
    if gi is None:
        gi = _index(groups).get(g.id)
    if gi is None:
        return out
    for ci in child_indices(gi, groups):
        out.update(groups[ci].members)
    return out


def ancestor_groups(g: Group, groups: Sequence[Group]) -> set[str]:
    """IDs der composite-Gruppen, die `g` transitiv inkludieren."""
    gi = next((i for i, x in enumerate(groups) if x is g), None)
    if gi is None:
        gi = _index(groups).get(g.id)
    if gi is None:
        return set()
    return {groups[i].id for i in ancestor_indices(gi, groups)}


def owner_index(groups: Sequence[Group]) -> dict[str, int]:
    """Komponente → Index der ersten Gruppe mit ihr in `members`
    (deterministisch; composites haben keine `members`)."""
    owner: dict[str, int] = {}
    for i, g in enumerate(groups):
        for m in g.members:
            owner.setdefault(m, i)
    return owner


def membership(
    comp_id: str, groups: Sequence[Group], owner: dict[str, int] | None = None,
) -> set[int]:
    """Gruppen-Indizes der transitiven Mitgliedschaft einer Komponente:
    eigene atomare Gruppe + alle composite-Ahnen (leer = nicht-gruppig)."""
    own = (owner if owner is not None else owner_index(groups)).get(comp_id)
    if own is None:
        return set()
    return {own, *ancestor_indices(own, groups)}


def pipe_foreign_indices(
    from_comp: str,
    to_comp: str,
    groups: Sequence[Group],
    owner: dict[str, int] | None = None,
) -> list[int]:
    """R-37-Refinement (R-38): Indizes der FREMDEN Boxen einer Pipe.

    Nur inter-gruppig (beide Enden gruppig, verschiedene atomare
    Gruppen) — sonst `[]` (kein Detour, wie R-37). Nicht fremd sind:
    die atomaren Gruppen beider Enden, deren composite-Ahnen und — für
    composites, die BEIDE Enden enthalten (Pipe „innerhalb" des
    composites) — alle inkludierten atomaren Kinder dieses composites.
    Ohne composites identisch zur bisherigen R-37-Semantik.
    """
    own = owner if owner is not None else owner_index(groups)
    gi, gj = own.get(from_comp), own.get(to_comp)
    if gi is None or gj is None or gi == gj:
        return []
    anc_i = set(ancestor_indices(gi, groups))
    anc_j = set(ancestor_indices(gj, groups))
    exempt = {gi, gj} | anc_i | anc_j
    for ci in sorted(anc_i & anc_j):
        exempt.update(child_indices(ci, groups))
    return [i for i in range(len(groups)) if i not in exempt]
