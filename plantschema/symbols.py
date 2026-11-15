"""S1-Platzhalter-Symbolik: Port-Geometrie-Katalog + Zeichen-Boxen.

S1 = schlichte Platzhalter-Geometrie (Rect/Kreis/Pfadsymbole, P&ID-ähnlich),
explizit markiert per `data-symbol="placeholder"` auf der comp-* Gruppe.
S2 portiert die P&ID-<defs> aus cmi `ui/svg/pid-symbols.svg` (read-only
Referenz) und tauscht die Platzhalter gegen die Normsymbole; der
Port-Geometrie-Katalog bleibt als Kanon (Port-Name → Offset, Achse).

Konvention: `at`-Koordinaten einer Komponente = Zentrum des Symbols.
Port-Offset = relative Position zum Zentrum (dx, dy); SVG y = nach unten.
Achse ("axis") = Richtung, in der ein Readout-Label außerhalb des Ports
platziert wird (default: Richtung des Offsets, null = oben).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "PortGeometry",
    "SymbolInfo",
    "PLACEHOLDER_SYMBOLS",
    "allowed_ports",
    "port_offset",
]

Axis = str  # "up" | "down" | "left" | "right" | None


@dataclass(frozen=True, slots=True)
class PortGeometry:
    """Ein Port eines Komponententyps: Offset zum Zentrum + Ausrichtungsachse."""

    name: str
    dx: int
    dy: int
    axis: Axis | None = None  # None = Richtung des Offsets, 0/null = nach oben


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Platzhalter-Zeichnungsgeometrie + Port-Katalog eines Komponententyps."""

    shape: str  # "rect" | "circle" | "pipe-line" | ...
    size: tuple[int, int]  # (halbe Breite, halbe Höhe) bzw. Radius
    ports: tuple[PortGeometry, ...]


def _ports(*items: tuple[str, int, int, Axis | None]) -> tuple[PortGeometry, ...]:
    return tuple(PortGeometry(name=n, dx=dx, dy=dy, axis=ax) for n, dx, dy, ax in items)


#: Port-Geometrie-Katalog S1 (Minimum-Set, Typ → Ports).
PLACEHOLDER_SYMBOLS: dict[str, SymbolInfo] = {
    "tank-buffer": SymbolInfo(
        "rect",
        (30, 60),
        _ports(
            ("top", 0, -60, "up"),
            ("mid", 0, 0, "up"),
            ("bottom", 0, 60, "down"),
            ("left", -30, 0, "left"),
            ("right", 30, 0, "right"),
        ),
    ),
    "boiler-oil": SymbolInfo(
        "rect",
        (28, 26),
        _ports(
            ("top", 0, -26, "up"),
            ("left", -28, 0, "left"),
            ("right", 28, 0, "right"),
            ("bottom", 0, 26, "down"),
        ),
    ),
    "boiler-solid": SymbolInfo(
        "rect",
        (28, 30),
        _ports(
            ("top", 0, -30, "up"),
            ("left", -28, 0, "left"),
            ("right", 28, 0, "right"),
            ("bottom", 0, 30, "down"),
        ),
    ),
    "pump": SymbolInfo(
        "circle",
        (13, 13),
        _ports(("in", -20, 0, "left"), ("out", 20, 0, "right")),
    ),
    "valve-2way": SymbolInfo(
        "pipe-line",
        (20, 10),
        _ports(("in", -20, 0, "left"), ("out", 20, 0, "right")),
    ),
    "heatex-plate": SymbolInfo(
        "rect",
        (35, 14),
        _ports(
            ("in", -35, 0, "left"),
            ("out", 35, 0, "right"),
            ("top", 0, -14, "up"),
            ("bottom", 0, 14, "down"),
        ),
    ),
    "radiator": SymbolInfo(
        "rect",
        (30, 13),
        _ports(("in", -30, 0, "left"), ("out", 30, 0, "right")),
    ),
    "collector-solar": SymbolInfo(
        "rect",
        (34, 14),
        _ports(("in", -34, 0, "left"), ("out", 34, 0, "right")),
    ),
    "chimney": SymbolInfo(
        "rect",
        (9, 34),
        _ports(("bottom", 0, 34, "down")),
    ),
    "tap": SymbolInfo(
        "circle",
        (7, 7),
        _ports(("in", 0, -7, "up")),
    ),
    # Readout-Hosts ohne Pipe-Port (S1):
    "pt": SymbolInfo("circle", (8, 8), ()),
    "flow-switch": SymbolInfo("circle", (8, 8), ()),
}

#: Typen mit Pipe-Porten (Readout-Hosts wie `pt` dürfen keine Pipes tragen).
PIPE_PORT_TYPES = frozenset(
    name for name, info in PLACEHOLDER_SYMBOLS.items() if info.ports
)


def known_types() -> frozenset[str]:
    """Alle bekannten Komponententypen (S1-Katalog)."""
    return frozenset(PLACEHOLDER_SYMBOLS)


def allowed_ports(comp_type: str, override: list[str] | None = None) -> frozenset[str]:
    """Zulässige Port-Namen eines Komponententyps (inkl. Override).

    Override (`component.ports`): wenn gesetzt, dürfen nur diese Ports
    verwendet werden — jedes benannte Port muss im Typ-Katalog existieren
    (Prüfung in `validate`).
    """
    base = frozenset(p.name for p in PLACEHOLDER_SYMBOLS[comp_type].ports)
    if override is None:
        return base
    return frozenset(override) & base


def port_offset(comp_type: str, port: str) -> PortGeometry:
    """Port-Geometrie (dx, dy, axis) eines Typs. KeyError bei unbekanntem Port."""
    for p in PLACEHOLDER_SYMBOLS[comp_type].ports:
        if p.name == port:
            return p
    raise KeyError(f"{comp_type} hat keinen Port {port!r}")
