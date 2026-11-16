"""Mikro-Layout-Engine (S4-L2, R-36): deterministische intra-Gruppen-
Platzierung.

Koordinaten werden GENERIERT, nicht gepflegt: jede Gruppe hat eine
Makro-Box (Autor-`at`/`size`), die Engine platziert die Mitglieder
deterministisch IN die Box, hub-zentriert, mit Port-Ortungs-Erhaltung.
Explizites `at` eines Mitglieds wird NICHT überschrieben
(Override-Hierarchie: explizit-`at` > Engine, R-36).

Algorithmus (rein deterministisch — keine Randomisierung, keine
Iteration/Heuristik mit Zufall; gleiche Eingabe → gleiche Koordinaten,
ganzzahlig gerundet):

1. **Hub-Anker A** = `group.hub_at` ?? Box-Mitte; hat die Hub-Komponente
   ein explizites `at`, gilt das (Author-Override gewinnt). Die Hub-
   Komponente selbst erhält (ohne explizites `at`) den Anker A.
2. **Nicht-Hub-Mitglieder M** in `order`-Reihenfolge (Default: `members`
   minus Hub):
   - **Port-Ortungs-Refinement (Spalten-Zuweisung):** pro Mitglied werden
     die in `pipes` (from+to) genutzten Ports ermittelt; deren Achsen
     aus `symbols.COMPONENT_PORTS` (via `port_offset`):
       - nur `left`-Achsen  → Spalte "left"
       - nur `right`-Achsen → Spalte "right"
       - sonst (keine genutzten Ports / up/down / beides / Typ ohne
         Katalog) → "auto" (Spalten-Split ohne Forcierung).
     Spaltengröße: Spalten-Split = erste Hälfte in die linke Spalte
     (ceil(n/2) Slots), zweite Hälfte in die rechte; auto-Mitglieder
     füllen die restlichen Slots (links zuerst, dann rechts; jeweils in
     `order`-Reihenfolge). Eine Spalte mit mehr gezwungenen Mitgliedern
     als Slots füllt ihre Hälfte, den Überhang in die andere
     (deterministischer Tiebreak über die `order`-Reihenfolge).
   - **Zeilen:** gleichmäßig in `[box.y + 0.25·box.h, box.y + 0.75·box.h]`
     (Einzel-Element = Band-Mitte = Box-Mitte-y); x = `box.x + 0.28·box.w`
     (linke Spalte) bzw. `box.x + 0.72·box.w` (rechte Spalte).
3. Alle Koordinaten = `int(round(·))` (ganzzahlig, deterministisch).

Integration: Pipeline-Schritt ZWISCHEN `io.load` und `validate`
(`__main__.main`): `resolve(load_schema(…))` → danach arbeiten
`validate`, `check`, `render` ALLE auf dem resolved Layout.
"""

from __future__ import annotations

from .model import Schema

__all__ = [
    "COL_LEFT",
    "COL_RIGHT",
    "ROW_TOP",
    "ROW_BOTTOM",
    "resolve",
]

#: Spalten-Faktoren (R-36): x = box.x + Faktor·box.w.
COL_LEFT: float = 0.28
COL_RIGHT: float = 0.72

#: Zeilen-Band (R-36): y ∈ [box.y + ROW_TOP·box.h, box.y + ROW_BOTTOM·box.h].
ROW_TOP: float = 0.25
ROW_BOTTOM: float = 0.75


def _round(v: float) -> int:
    """Deterministisch ganzzahlig (Python-`round` = half-to-even)."""
    return int(round(v))


def _comp_type(schema: Schema, comp: str) -> str:
    for c in schema.components:
        if c.id == comp:
            return c.type
    return ""


def _used_port_axes(comp: str, comp_type: str, schema: Schema) -> set[str]:
    """Genutzte Port-Achsen einer Komponente (alle Pipe-Enden, from+to).

    Achsen aus dem Port-Katalog (`symbols.port_offset`); Ports ohne
    explizite Achse → Achse aus dem Offset-Vektor. Unbekannter Typ /
    Port nicht im Katalog → leer (Refinement inaktiv).
    """
    from . import symbols

    axes: set[str] = set()
    if comp_type not in symbols.COMPONENT_PORTS:
        return axes
    for p in schema.pipes:
        for ref in (p.from_, p.to):
            if ref.comp != comp:
                continue
            try:
                geo = symbols.port_offset(comp_type, ref.port)
            except KeyError:
                continue  # Port nicht im Katalog (Validierungs-Problem)
            axis = geo.axis
            if axis in (None, ""):
                dx, dy = geo.dx, geo.dy
                axis = (
                    "left" if dx < 0 else "right" if dx > 0
                    else "down" if dy > 0 else "up"
                )
            if axis:
                axes.add(axis)
    return axes


def _column_of(axes: set[str]) -> str | None:
    """Port-Ortungs-Refinement (R-36): Spaltengzwungung.

    - nur `left`-Achsen → "left"; nur `right`-Achsen → "right"
    - sonst (keine genutzten Ports / up-down / beides) → None = "auto".
    """
    has_l = "left" in axes
    has_r = "right" in axes
    if has_l and not has_r:
        return "left"
    if has_r and not has_l:
        return "right"
    return None


def _slot_count(n: int) -> tuple[int, int]:
    """Spalten-Split: `n` Mitglieder → (linke, rechte) Slot-Anzahl
    (erste Hälfte links: ceil(n/2), Rest rechts)."""
    left = (n + 1) // 2
    return left, n - left


def _assign_columns(members: list[str], forced: dict[str, str | None]) -> dict[str, str]:
    """Deterministische Spalten-Zuweisung (Spalten-Split + Refinement).

    1. Split-Größe: linke Hälfte = ceil(n/2) Slots, rechts der Rest.
    2. Forcierte Mitglieder (`forced` ≠ None) zuerst in ihre Spalte
       (nach `order`-Reihenfolge); bei vollem Quoten-Topf → andere
       Spalte (deterministischer Tiebreak, weiter in `order`-Reihenfolge).
    3. Auto-Mitglieder füllen die restlichen Slots (links zuerst, dann
       rechts; jeweils in `order`-Reihenfolge).
    """
    cap_l, cap_r = _slot_count(len(members))
    assign: dict[str, str] = {}
    free = {"left": cap_l, "right": cap_r}

    def place(member: str, want: str | None) -> None:
        if want is not None and free[want] > 0:
            assign[member] = want
            free[want] -= 1
        elif free["left"] > 0:
            assign[member] = "left"
            free["left"] -= 1
        else:
            assign[member] = "right"
            free["right"] -= 1

    for m in members:  # Phase 1: Forcierung (order-Reihenfolge).
        f = forced.get(m)
        if f is not None:
            place(m, f)
    for m in members:  # Phase 2: Auto (order-Reihenfolge).
        if m not in assign:
            place(m, None)
    return assign


def _rows(count: int, y0: float, y1: float) -> list[float]:
    """`count` gleichmäßig verteilte y-Werte im Band [y0, y1]
    (Einzel-Element = Band-Mitte = bei Standard-Box die Box-Mitte-y)."""
    if count <= 0:
        return []
    if count == 1:
        return [(y0 + y1) / 2]
    step = (y1 - y0) / (count - 1)
    return [y0 + i * step for i in range(count)]


def _ordered_members(group, hub: str | None) -> list[str]:
    """Mitgliedsreihenfolge für die Spalten-Zuordnung: `order` (falls
    gesetzt), sonst `members`-Reihenfolge; der Hub wird rausgenommen
    (Hub sitzt am Anker, nicht in einer Spalte)."""
    seq = group.order if group.order is not None else list(group.members)
    return [m for m in seq if m != hub]


def resolve(schema: Schema) -> Schema:
    """Mikro-Layout auflösen (S4-L2, R-36): `at` für alle Gruppen-
    Mitglieder OHNE explizites `at` berechnen (mutiert und liefert die
    Schema-Instanz).

    - Explizites `at` wird NICHT überschrieben (Override-Hierarchie:
      explizit-`at` > Engine, R-36).
    - Gruppe ohne Mitglieder (nur Hub) → nur der Hub wird platziert.
    - Reine Deterministik: keine Randomisierung, keine Iteration.
    - Ganzzahlige Koordinaten (Rundung: half-to-even via `round`).

    Vorbedingungen (sonst `validate`-Probleme, s. R-36): Hub ∈ members
    (`group-hub-not-member`), `order` = Permutation von `members`
    (`group-order-member`), Makro-Geometrie > 0 (`group-geometry`).
    """
    comps = {c.id: c for c in schema.components}

    for group in schema.groups:
        hub = group.hub
        if hub is not None and hub not in group.members:
            continue  # `group-hub-not-member` (validate meldet es)
        gx, gy = group.at
        w, h = group.size

        # 1) Hub-Anker A = hub_at ?? Box-Mitte (explizites Hub-`at`
        #    gewinnt: Author-Override).
        if hub is not None:
            comp = comps.get(hub)
            if comp is not None and comp.at is None:
                ax, ay = group.hub_at if group.hub_at is not None \
                    else (gx + w / 2.0, gy + h / 2.0)
                comp.at = (_round(ax), _round(ay))

        # 2) Nicht-Hub-Mitglieder: Spalten-Split + Port-Ortungs-
        #    Refinement, Zeilen im Band [0.25·h, 0.75·h].
        members = _ordered_members(group, hub)
        if not members:
            continue
        forced: dict[str, str | None] = {}
        for m in members:
            forced[m] = _column_of(_used_port_axes(m, _comp_type(schema, m), schema))
        assign = _assign_columns(members, forced)

        y0, y1 = gy + ROW_TOP * h, gy + ROW_BOTTOM * h
        x_left = gx + COL_LEFT * w
        x_right = gx + COL_RIGHT * w
        for col, x in (("left", x_left), ("right", x_right)):
            col_members = [m for m in members if assign[m] == col]
            ys = _rows(len(col_members), y0, y1)
            for k, m in enumerate(col_members):
                comp = comps.get(m)
                if comp is None or comp.at is not None:
                    continue  # ref-Problem / explizites `at` (Override)
                comp.at = (_round(x), _round(ys[k]))
    return schema
