"""P&ID-Symbol-Bibliothek (S2): Seed aus cmi `ui/svg/pid-symbols.svg`.

Kanon (S2, `docs/model-reference.md` § 5, R-30):
- 18 Symbole als `<g id="pid-…">` (klassen-basiert `.pid`/`.pid-t`, exakt
  wie im cmi-Original), jeweils lokal um (0,0) zentriert. `pid-demo` wird
  NICHT portiert (cmi-interner Demo-Block).
- Port-Offsets = **Stiel-Enden** des cmi-Symbols: pump/valve/throttle
  ±20 (horizontal) + Stiel oben (0,−20); collector ±41, heatex-plate ±35,
  heatex-shell ±30, mixing/tap ±14, radiator ±30 (Stiel-Enden). Bei
  Symbolen ohne Stiel (tank-buffer, boiler-*, chimney) = Kanten-Mitte
  (Tank: x=±30, y=±60, Zone-Linien y=±20 — cmi-`loop-svg.js`-Kommentar-Kanon).
- Pipe-Endpunkte treffen exakt auf Port-Positionen (absolut = comp.at +
  Port-Offset) — S4N-2-QA-Regel aus cmi („alle Leitungsendpunkte treffen
  exakt auf Symbol-Kanten").
- Unbekannter Typ → S1-Verhalten: Problem `unknown-type` in validate,
  Rendering = Platzhalter-Rect (`data-symbol="placeholder"`).

`render_component` emittiert die comp-* Gruppe (stable ID, `data-*`-Hooks,
`<use href="#pid-…">` mit x/y-Shift, Label-Texte `.txt-h` + sub `.txt-s`
oben über dem Symbol, Offset je Typ aus `LABEL_OFFSET`).
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Component

__all__ = [
    "Axis",
    "PortGeometry",
    "COMPONENT_PORTS",
    "LABEL_OFFSET",
    "SYMBOL_TYPES",
    "PIPE_PORT_TYPES",
    "allowed_ports",
    "is_known_type",
    "known_types",
    "port_names",
    "port_offset",
    "symbol_id",
    "render_component",
    "render_defs",
]

Axis = str  # "up" | "down" | "left" | "right" | None


@dataclass(frozen=True, slots=True)
class PortGeometry:
    """Ein Port eines Komponententyps: Offset zum Zentrum + Ausrichtungsachse.

    Achse = Ausrichtung für Readout-Offset + Pipe-Anbindung (R-11, R-30).
    """

    name: str
    dx: int
    dy: int
    axis: Axis | None = None  # None = Richtung des Offsets, (0,0)-Offset: up


# ---------------------------------------------------------------------------
# P&ID-<defs> (Seed cmi `ui/svg/pid-symbols.svg`: 18 Symbole, kein pid-demo)
# ---------------------------------------------------------------------------

_PID_SYMBOLS: tuple[tuple[str, str], ...] = (
    # (symbol-id, <g>-Inhalt) — Inhalt exakt wie im cmi-Original.
    (
        "pid-pump-cent",
        """
<g id="pid-pump-cent">
  <circle class="pid" r="13"/>
  <path class="pid" d="M0,7 L0,-5 M0,-5 L-4.5,3 M0,-5 L4.5,3"/>
  <path d="M-13,0 L-20,0 M13,0 L20,0" class="pid"/>
  <text class="pid-t" x="0" y="19">Q</text>
</g>""",
    ),
    (
        "pid-valve-2way",
        """
<g id="pid-valve-2way">
  <path class="pid" d="M-13,-10 L0,0 L-13,10 Z M13,-10 L0,0 L13,10 Z"/>
  <line class="pid" x1="0" y1="0" x2="0" y2="-15"/>
  <circle class="pid" cx="0" cy="-18" r="3"/>
  <path d="M-20,0 L-13,0 M13,0 L20,0" class="pid"/>
</g>""",
    ),
    (
        "pid-valve-3way",
        """
<g id="pid-valve-3way">
  <path class="pid" d="M-12,-9 L0,0 L-12,9 Z M12,-9 L0,0 L12,9 Z"/>
  <line class="pid" x1="0" y1="0" x2="0" y2="12"/>
  <path d="M-20,0 L-12,0 M12,0 L20,0" class="pid"/>
  <path d="M0,12 L0,20" class="pid"/>
</g>""",
    ),
    (
        "pid-valve-actuator",
        """
<g id="pid-valve-actuator">
  <path class="pid" d="M-13,-10 L0,0 L-13,10 Z M13,-10 L0,0 L13,10 Z"/>
  <line class="pid" x1="0" y1="0" x2="0" y2="-15"/>
  <rect class="pid" x="-17" y="-35" width="34" height="17" rx="3"/>
  <text class="pid-t" x="0" y="-24" font-size="9">0–10 V</text>
  <path d="M-20,0 L-13,0 M13,0 L20,0" class="pid"/>
</g>""",
    ),
    (
        "pid-valve-globe",
        """
<g id="pid-valve-globe">
  <path class="pid" d="M-13,-10 L0,0 L-13,10 Z M13,-10 L0,0 L13,10 Z"/>
  <line class="pid" x1="0" y1="0" x2="0" y2="-13"/>
  <circle class="pid" cx="0" cy="-17" r="4"/>
  <line class="pid" x1="0" y1="-17" x2="12" y2="-22"/>
  <path d="M-20,0 L-13,0 M13,0 L20,0" class="pid"/>
</g>""",
    ),
    (
        "pid-heatex-shell",
        """
<g id="pid-heatex-shell">
  <circle class="pid" cx="-13" cy="0" r="11"/>
  <line class="pid" x1="-21.5" y1="-8" x2="-4.5" y2="8"/>
  <circle class="pid" cx="13" cy="0" r="11"/>
  <line class="pid" x1="4.5" y1="8" x2="21.5" y2="-8"/>
  <path d="M-30,0 L-24,0 M24,0 L30,0 M0,0 L0,9 M0,12 L0,20" class="pid"/>
</g>""",
    ),
    (
        "pid-heatex-plate",
        """
<g id="pid-heatex-plate">
  <line class="pid" x1="0" y1="-14" x2="0" y2="14"/>
  <path class="pid" d="M-28,-6 C-18,-15 -9,4 0,-4"/>
  <path class="pid" d="M28,-6 C18,-15 9,4 0,-4"/>
  <path class="pid" d="M-28,8 C-18,-1 -9,18 0,9"/>
  <path class="pid" d="M28,8 C18,-1 9,18 0,9"/>
  <path d="M-35,0 L-28,0 M28,0 L35,0" class="pid"/>
</g>""",
    ),
    (
        "pid-tank-buffer",
        """
<g id="pid-tank-buffer">
  <rect class="pid" x="-30" y="-60" width="60" height="120" rx="12"/>
  <line class="pid" x1="-30" y1="-20" x2="30" y2="-20"/>
  <line class="pid" x1="-30" y1="20" x2="30" y2="20"/>
  <path class="pid" d="M-30,42 L30,42 M-16,38 L-16,46 M16,38 L16,46" stroke-width="1.4" stroke-dasharray="5 4"/>
  <path d="M0,-68 L0,-76 M0,68 L0,76" class="pid"/>
</g>""",
    ),
    (
        "pid-boiler-oil",
        """
<g id="pid-boiler-oil">
  <rect class="pid" x="-28" y="-26" width="56" height="52" rx="4"/>
  <line class="pid" x1="-28" y1="-8" x2="28" y2="-8"/>
  <path d="M0,-32 L0,-40 M0,-44 L-4,-38 L4,-38 Z" class="pid"/>
  <circle class="pid" cx="0" cy="24" r="5"/>
  <path d="M0,24 L0,17 M0,17 L-3,22 M0,17 L3,22" class="pid"/>
  <line class="pid" x1="-14" y1="40" x2="-4" y2="32"/>
</g>""",
    ),
    (
        "pid-boiler-solid",
        """
<g id="pid-boiler-solid">
  <rect class="pid" x="-28" y="-30" width="56" height="50" rx="4"/>
  <rect class="pid" x="-19" y="20" width="38" height="16" rx="2"/>
  <circle class="pid" cx="0" cy="28" r="4.5"/>
  <circle cx="0" cy="28" r="1.2" fill="currentColor" stroke="none"/>
  <line class="pid" x1="-28" y1="-10" x2="28" y2="-10"/>
  <path d="M0,-36 L0,-44 M0,-48 L-4,-42 L4,-42 Z" class="pid"/>
</g>""",
    ),
    (
        "pid-collector-solar",
        """
<g id="pid-collector-solar">
  <rect class="pid" x="-34" y="-14" width="68" height="28" rx="12"/>
  <path class="pid" d="M-26,4 C-21,-6 -17,-6 -12,4 C-7,14 -3,14 2,4 C7,-6 11,-6 16,4 C21,14 25,14 28,8" stroke-width="1.5"/>
  <path d="M-41,0 L-34,0 M34,0 L41,0" class="pid"/>
</g>""",
    ),
    (
        "pid-pt",
        """
<g id="pid-pt">
  <circle class="pid" r="8"/>
  <text class="pid-t" x="0" y="3.5" font-size="10">T</text>
  <line class="pid" x1="0" y1="8" x2="0" y2="16"/>
</g>""",
    ),
    (
        "pid-flow-switch",
        """
<g id="pid-flow-switch">
  <circle class="pid" r="8"/>
  <text class="pid-t" x="0" y="-1" font-size="9">F</text>
  <line class="pid" x1="0" y1="3" x2="0" y2="5.5"/>
  <circle cx="0" cy="6.5" r="1.8" fill="currentColor" stroke="none"/>
  <line class="pid" x1="0" y1="8" x2="0" y2="16"/>
</g>""",
    ),
    (
        "pid-radiator",
        """
<g id="pid-radiator">
  <rect class="pid" x="-22" y="-13" width="44" height="26" rx="4"/>
  <line class="pid" x1="-13" y1="-13" x2="-13" y2="13"/>
  <line class="pid" x1="-4.5" y1="-13" x2="-4.5" y2="13"/>
  <line class="pid" x1="4.5" y1="-13" x2="4.5" y2="13"/>
  <line class="pid" x1="13" y1="-13" x2="13" y2="13"/>
  <path d="M-30,0 L-22,0 M22,0 L30,0" class="pid"/>
</g>""",
    ),
    (
        "pid-throttle",
        """
<g id="pid-throttle">
  <path class="pid" d="M-13,-10 L0,0 L-13,10 Z M13,-10 L0,0 L13,10 Z"/>
  <path d="M-4,0 L0,-4 L4,0" class="pid"/>
  <line class="pid" x1="0" y1="0" x2="0" y2="-12"/>
  <rect class="pid" x="-15" y="-30" width="30" height="15" rx="3"/>
  <text class="pid-t" x="0" y="-20" font-size="8">0–10 V</text>
  <path d="M-20,0 L-13,0 M13,0 L20,0" class="pid"/>
</g>""",
    ),
    (
        "pid-chimney",
        """
<g id="pid-chimney">
  <rect class="pid" x="-9" y="-34" width="18" height="68"/>
  <rect class="pid" x="-14" y="-40" width="28" height="6"/>
  <path d="M18,26 L18,0 M18,-4 L13.5,4 L22.5,4 Z" class="pid"/>
</g>""",
    ),
    (
        "pid-tap",
        """
<g id="pid-tap">
  <path d="M-14,0 L-7,0 M7,0 L14,0" class="pid"/>
  <circle class="pid" r="7"/>
  <line class="pid" x1="0" y1="7" x2="0" y2="17"/>
  <path d="M0,23 L-4,16 L4,16 Z" class="pid"/>
</g>""",
    ),
    (
        "pid-mixing",
        """
<g id="pid-mixing">
  <path d="M-14,0 L-5,0 M5,0 L14,0 M0,-14 L0,-5 M0,14 L0,5" class="pid"/>
  <circle cx="0" cy="0" r="4.5" fill="currentColor" stroke="none"/>
  <path d="M-5,-6.5 A7.5,7.5 0 0 1 5,-6.5" class="pid"/>
  <path d="M5,-6.5 L8.5,-10 L2.2,-9.2 Z" class="pid"/>
</g>""",
    ),
)

#: Marker `<arrow>` (S1-Kompatibilität; S2: Pipes nutzen stattdessen
#: `.pipe-arrow`-Endpunkte, s. R-29 — der Marker bleibt im <defs>).
_ARROW_MARKER = (
    '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto" '
    'markerUnits="userSpaceOnUse">'
    '<path d="M0,0 L10,5 L0,10 Z" fill="#cbd5e1"/>'
    "</marker>"
)


def render_defs() -> str:
    """Kompletter `<defs>`-Inhalt: Marker + alle 18 P&ID-Symbole.

    Deterministisch: feste Katalog-Reihenfolge, keine Iteration über
    unsortierte Sammlungen (R-24).
    """
    parts: list[str] = [_ARROW_MARKER]
    parts.extend(body.strip() for _, body in _PID_SYMBOLS)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Port-Katalog (S2: Stiel-Enden; Tank-Geometrie ±30/±60, Zone-Linien ±20)
# ---------------------------------------------------------------------------


def _ports(*items: tuple[str, int, int, Axis | None]) -> tuple[PortGeometry, ...]:
    return tuple(PortGeometry(name=n, dx=dx, dy=dy, axis=ax) for n, dx, dy, ax in items)


#: Port-Katalog S2 (Kanon `docs/model-reference.md` § 5, R-30).
COMPONENT_PORTS: dict[str, tuple[PortGeometry, ...]] = {
    # Kanten-Mitte (kein Prozess-Stiel): Tank x=±30, y=±60; Zone-Linien y=±20.
    "tank-buffer": _ports(
        ("top", 0, -60, "up"),
        ("mid-top", 0, -20, "up"),
        ("mid-bottom", 0, 20, "down"),
        ("bottom", 0, 60, "down"),
        ("left", -30, 0, "left"),
        ("right", 30, 0, "right"),
    ),
    # Kanten-Mitte des Kessel-Rects (cmi-Loops verbinden an Rect-Kanten).
    "boiler-oil": _ports(
        ("top", 0, -26, "up"),
        ("left", -28, 0, "left"),
        ("right", 28, 0, "right"),
        ("bottom", 0, 26, "down"),
    ),
    "boiler-solid": _ports(
        ("top", 0, -30, "up"),
        ("left", -28, 0, "left"),
        ("right", 28, 0, "right"),
        ("bottom", 0, 20, "down"),  # Kanten-Mitte Haupt-Rect (Feuerungsraum darunter)
    ),
    # Stiel-Enden des cmi-Symbols (±41, cmi loop-svg.js: Anschluss 759 = 800−41).
    "collector-solar": _ports(
        ("in", -41, 0, "left"),
        ("out", 41, 0, "right"),
    ),
    # Stiel-Enden ±35; top/bottom = Trennlinien-Kanten (cmi: Anschluss y=±14).
    "heatex-plate": _ports(
        ("in", -35, 0, "left"),
        ("out", 35, 0, "right"),
        ("top", 0, -14, "up"),
        ("bottom", 0, 14, "down"),
    ),
    # Stiel-Enden ±30; bottom = Stiel-Ende (0,20).
    "heatex-shell": _ports(
        ("in", -30, 0, "left"),
        ("out", 30, 0, "right"),
        ("bottom", 0, 20, "down"),
    ),
    # Stiel-Enden ±14 (P&ID-Verbindungspunkt).
    "mixing": _ports(
        ("in", -14, 0, "left"),
        ("out", 14, 0, "right"),
        ("top", 0, -14, "up"),
        ("bottom", 0, 14, "down"),
    ),
    # Stiel-Enden ±20 (cmi-Loop-Kanon: z. B. O8 340 → 360/320).
    "pump": _ports(
        ("in", -20, 0, "left"),
        ("out", 20, 0, "right"),
    ),
    "valve-2way": _ports(
        ("in", -20, 0, "left"),
        ("out", 20, 0, "right"),
        ("stem", 0, -20, "up"),
    ),
    "valve-3way": _ports(
        ("in", -20, 0, "left"),
        ("out", 20, 0, "right"),
        ("mix", 0, 20, "down"),  # senkrechter Schenkel (Einmischung)
    ),
    "valve-globe": _ports(
        ("in", -20, 0, "left"),
        ("out", 20, 0, "right"),
        ("stem", 0, -20, "up"),
    ),
    "valve-actuator": _ports(
        ("in", -20, 0, "left"),
        ("out", 20, 0, "right"),
        ("stem", 0, -20, "up"),
    ),
    "throttle": _ports(
        ("in", -20, 0, "left"),
        ("out", 20, 0, "right"),
        ("stem", 0, -20, "up"),
    ),
    # Stiel-Enden ±30 (cmi loop E: 720 → 690/750).
    "radiator": _ports(
        ("in", -30, 0, "left"),
        ("out", 30, 0, "right"),
    ),
    # Stiel-Enden ±14; draw = Entnahmepfeil nach unten (0,20).
    "tap": _ports(
        ("in", -14, 0, "left"),
        ("out", 14, 0, "right"),
        ("draw", 0, 20, "down"),
    ),
    # Kanten-Mitte (Kamin-Rect x=±9); Abgas-Anschluss von der Seite.
    "chimney": _ports(
        ("left", -9, 0, "left"),
        ("right", 9, 0, "right"),
        ("bottom", 0, 34, "down"),
    ),
    # Readout-Hosts ohne Pipe-Port (nur {x,y}-Referenz, s. R-13).
    "pt": (),
    "flow-switch": (),
}

#: Typen mit Pipe-Porten (Readout-Hosts wie `pt` dürfen keine Pipes tragen).
PIPE_PORT_TYPES: frozenset[str] = frozenset(
    name for name, ports in COMPONENT_PORTS.items() if ports
)

#: Typ → Symbol-ID (1:1; `valve` = 2-Wege-Default).
_TYPE_TO_SYMBOL: dict[str, str] = {
    "tank-buffer": "pid-tank-buffer",
    "boiler-oil": "pid-boiler-oil",
    "boiler-solid": "pid-boiler-solid",
    "collector-solar": "pid-collector-solar",
    "heatex-plate": "pid-heatex-plate",
    "heatex-shell": "pid-heatex-shell",
    "mixing": "pid-mixing",
    "pump": "pid-pump-cent",
    "valve": "pid-valve-2way",
    "valve-2way": "pid-valve-2way",
    "valve-3way": "pid-valve-3way",
    "valve-globe": "pid-valve-globe",
    "valve-actuator": "pid-valve-actuator",
    "throttle": "pid-throttle",
    "radiator": "pid-radiator",
    "tap": "pid-tap",
    "chimney": "pid-chimney",
    "pt": "pid-pt",
    "flow-switch": "pid-flow-switch",
}

#: Alias-Geometrie: Typ ohne eigene Ports nutzt die Geometrie des Basis-Typs.
_PORT_ALIAS: dict[str, str] = {
    "valve": "valve-2way",
}

#: Label-Offset je Typ (dy über dem Symbolzentrum; Formel: halbe Symbolhöhe
#: + 12 px, bei Aktoren/Aufsätzen die Oberkante + 12 px). Default (S2): 32.
LABEL_OFFSET: dict[str, int] = {
    "tank-buffer": 72,
    "boiler-oil": 38,
    "boiler-solid": 42,
    "collector-solar": 26,
    "heatex-plate": 26,
    "heatex-shell": 23,
    "mixing": 26,
    "pump": 25,
    "valve": 33,
    "valve-2way": 33,
    "valve-3way": 21,
    "valve-globe": 33,
    "valve-actuator": 47,
    "throttle": 42,
    "radiator": 25,
    "tap": 19,
    "chimney": 52,
    "pt": 20,
    "flow-switch": 20,
}

_DEFAULT_LABEL_OFFSET: int = 32

#: Platzhalter-Größe (unbekannter Typ): halbe Breite/Höhe (S1-Fallback).
_PLACEHOLDER_HALF: tuple[int, int] = (20, 20)

_SYMBOL_CLASS = "sym"


# ---------------------------------------------------------------------------
# Zugriff
# ---------------------------------------------------------------------------


def is_known_type(comp_type: str) -> bool:
    """Komponententyp im S2-Katalog (Symbol-Mapping + Ports)."""
    return comp_type in _TYPE_TO_SYMBOL


def known_types() -> frozenset[str]:
    """Alle bekannten Komponententypen (S2-Katalog inkl. Alias `valve`)."""
    return frozenset(_TYPE_TO_SYMBOL)


SYMBOL_TYPES: frozenset[str] = known_types()


def _base_type(comp_type: str) -> str:
    return _PORT_ALIAS.get(comp_type, comp_type)


def port_names(comp_type: str) -> frozenset[str]:
    """Port-Namen eines Typs (Alias-aware; unbekannt → leere Menge)."""
    return frozenset(p.name for p in COMPONENT_PORTS.get(_base_type(comp_type), ()))


def allowed_ports(comp_type: str, override: list[str] | None = None) -> frozenset[str]:
    """Zulässige Port-Namen eines Komponententyps (inkl. Override).

    Override (`component.ports`): wenn gesetzt, dürfen nur diese Ports
    verwendet werden — jedes benannte Port muss im Typ-Katalog existieren
    (Prüfung in `validate`).
    """
    base = port_names(comp_type)
    if override is None:
        return base
    return frozenset(override) & base


def port_offset(comp_type: str, port: str) -> PortGeometry:
    """Port-Geometrie (dx, dy, axis) eines Typs. KeyError bei unbekanntem Port."""
    for p in COMPONENT_PORTS.get(_base_type(comp_type), ()):
        if p.name == port:
            return p
    raise KeyError(f"{comp_type} hat keinen Port {port!r}")


def symbol_id(comp_type: str) -> str:
    """Symbol-ID für einen Komponententyp (1:1 + Alias). KeyError bei unbekannt."""
    return _TYPE_TO_SYMBOL[comp_type]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(value: str) -> str:
    """XML-Attribut/Escapes (deterministisch, ohne ET-Abhängigkeit)."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _label_elements(comp_type: str, comp_at: tuple[int, int], label: object) -> str:
    """Label-Texte (`.txt-h` + sub `.txt-s`) oben über dem Symbol (R-30)."""
    if label is None:
        return ""
    text: str = label.text  # type: ignore[union-attr]
    sub: str | None = getattr(label, "sub", None)
    cx, cy = comp_at
    offset = LABEL_OFFSET.get(comp_type, _DEFAULT_LABEL_OFFSET)
    y = cy - offset
    out = [f'<text class="txt-h" x="{cx}" y="{y}" text-anchor="middle">{_esc(text)}</text>']
    if sub:
        out.append(
            f'<text class="txt-s" x="{cx}" y="{y + 14}" text-anchor="middle">'
            f"{_esc(sub)}</text>"
        )
    return "".join(out)


def render_component(comp: Component) -> str:
    """comp-* Gruppe als SVG-String (byte-deterministisch).

    Bekannter Typ: `<use href="#pid-…">` mit x/y = comp.at (Symbol ist
    (0,0)-zentriert). Unbekannter Typ: S1-Platzhalter-Rect
    (`data-symbol="placeholder"`). Labels (`.txt-h`/`.txt-s`) liegen oben
    über dem Symbol, Offset je Typ aus `LABEL_OFFSET`.
    """
    cx, cy = comp.at
    base = f'<g id="comp-{comp.id}" data-type="{_esc(comp.type)}"'
    if comp.loop:
        base += f' data-loop="{_esc(comp.loop)}"'
    if comp.flow:
        base += f' data-flow="{_esc(comp.flow)}"'
    if is_known_type(comp.type):
        sym = symbol_id(comp.type)
        body = (
            f' data-symbol="{sym}">'
            f'<use href="#{sym}" x="{cx}" y="{cy}" class="{_SYMBOL_CLASS}"/>'
        )
    else:
        w, h = _PLACEHOLDER_HALF
        body = (
            f' data-symbol="placeholder">'
            f'<rect class="comp-ph" x="{cx - w}" y="{cy - h}" '
            f'width="{2 * w}" height="{2 * h}" rx="4"/>'
        )
    return base + body + _label_elements(comp.type, comp.at, comp.label) + "</g>"
