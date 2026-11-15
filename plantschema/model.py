"""Semantisches Schema-Modell (plantschema/v1) — Pydantic v2.

Feldreferenz: `docs/model-reference.md`.
IDs: `^[A-Za-z0-9][A-Za-z0-9._-]*$` (keine Whitespace).
Koordinaten: ganzzahlig, >= 0, genau 2 Komponenten.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

__all__ = [
    "Canvas",
    "Component",
    "Group",
    "Label",
    "LabelSpec",
    "Pipe",
    "PipeKind",
    "PortRef",
    "Readout",
    "ReadoutAt",
    "Schema",
    "SchemaError",
    "TextAnchor",
    "Point",
]

def _point_before(v: Any) -> Any:
    """Before-Coercion-Prüfung: genau 2 Zahlen, >= 0, ganzzahlig."""
    if isinstance(v, (list, tuple)):
        return check_point(v, "coord")
    return v


Point = Annotated[tuple[int, int], BeforeValidator(_point_before)]

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PORT_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


class SchemaError(Exception):
    """Schema- oder IO-Fehler mit Feldpfad und (bestmöglicher) YAML-Zeile.

    Zeilenformat (CLI-Kanon): `[line N] path: message` bzw.
    `[?] path: message`, wenn keine Zeile ableitbar ist.
    """

    def __init__(self, message: str, path: str = "", line: int | None = None) -> None:
        self.message = message
        self.path = path
        self.line = line
        super().__init__(self.format())

    def format(self) -> str:
        loc = f"line {self.line}" if self.line is not None else "?"
        path = f" {self.path}:" if self.path else ""
        return f"[{loc}]{path} {self.message}"


def check_id(value: str, field: str) -> str:
    """ID-Prüfung: 1+ Zeichen, keine Whitespace/Sonderzeichen."""
    if not _ID_RE.fullmatch(value):
        raise ValueError(
            f"{field} muss [A-Za-z0-9][A-Za-z0-9._-]* sein, ohne Whitespace "
            f"(ist: {value!r})"
        )
    return value


def check_point(
    value: tuple | list, field: str
) -> Point:
    """genau 2 Zahlen, >= 0, ganzzahlig → (int, int)."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field} braucht genau 2 Zahlen (ist: {value!r})")
    out: list[int] = []
    for i, v in enumerate(value):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{field}[{i}] muss eine Zahl sein (ist: {v!r})")
        if v < 0:
            raise ValueError(f"{field}[{i}] muss >= 0 sein (ist: {v})")
        if float(v) != float(int(v)):
            raise ValueError(f"{field}[{i}] muss ganzzahlig sein (ist: {v})")
        out.append(int(v))
    return (out[0], out[1])


class _Model(BaseModel):
    """Basis: unbekannte Keys ablehnen (Tippfehler = Schema-Fehler)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PipeKind(StrEnum):
    """Leitungstyp → Farbe im SVG (Emissions-Kanon)."""

    VL = "vl"
    RL = "rl"
    WW = "ww"
    GAS = "gas"
    CTL = "ctl"


class TextAnchor(StrEnum):
    START = "start"
    MIDDLE = "middle"
    END = "end"


class Canvas(_Model):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    background: str = "#0b1220"

    @field_validator("background")
    @classmethod
    def _check_bg(cls, v: str) -> str:
        if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v):
            raise ValueError(f"background muss hex-Farbe sein (ist: {v!r})")
        return v


class LabelSpec(_Model):
    """Optionales Name-Label einer Komponente (emittiert im comp-* Group)."""

    text: str
    sub: str | None = None


class Component(_Model):
    id: str
    type: str
    at: Point
    label: LabelSpec | None = None
    ports: list[str] | None = None  # Override: nur diese Ports zulassen
    loop: str | None = None
    flow: str | None = None

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return check_id(v, "component.id")


class Group(_Model):
    """Makro-Gruppe (S4-L1, R-35): logische Komponentengruppe mit
    Autor-definierter Makro-Box-Geometrie.

    - `at`/`size` PFLLICHT (Makro-Geometrie, Autor-Kanon): obere-linke
      Ecke + Breite/Höhe der gestrichelten Gruppen-Box; alle Werte
      müssen > 0 sein (Validierungs-Problem `group-geometry`, R-35).
    - `members` = Member-Komponenten-IDs (Referenz-Checks in `validate`).
    - `hub` = optionale Zentralkomponente (muss ∈ `members`, falls gesetzt);
      Mikro-Layout-Verankerung für S4-L2 (R-36 folgt).
    """

    id: str
    label: str | None = None
    members: list[str]
    hub: str | None = None
    at: Point
    size: Point

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return check_id(v, "group.id")

    @field_validator("members")
    @classmethod
    def _v_members(cls, v: list[str]) -> list[str]:
        for m in v:
            check_id(m, "group.members[]")
        return v

    @field_validator("hub")
    @classmethod
    def _v_hub(cls, v: str | None) -> str | None:
        return check_id(v, "group.hub") if v is not None else None


class PortRef(_Model):
    """Anschluss-Referenz: Komponente + Port-Name."""

    comp: str
    port: str

    @field_validator("comp")
    @classmethod
    def _v_comp(cls, v: str) -> str:
        return check_id(v, "portref.comp")

    @field_validator("port")
    @classmethod
    def _v_port(cls, v: str) -> str:
        if not _PORT_RE.fullmatch(v):
            raise ValueError(f"port muss Kleinschrift sein (ist: {v!r})")
        return v


class Pipe(_Model):
    id: str
    from_: Annotated[PortRef, Field(alias="from")]
    to: PortRef
    kind: PipeKind
    via: list[Point] | None = None
    flow: str | None = None

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return check_id(v, "pipe.id")


class ReadoutAt(_Model):
    """Readout-Position: entweder {comp, port} ODER {x, y} (exklusiv)."""

    comp: str | None = None
    port: str | None = None
    x: int | None = None
    y: int | None = None

    @field_validator("comp")
    @classmethod
    def _v_comp(cls, v: str | None) -> str | None:
        return check_id(v, "readout.at.comp") if v is not None else None

    @field_validator("port")
    @classmethod
    def _v_port(cls, v: str | None) -> str | None:
        if v is not None and not _PORT_RE.fullmatch(v):
            raise ValueError(f"readout.at.port ungültig (ist: {v!r})")
        return v

    @model_validator(mode="after")
    def _v_exclusive(self) -> ReadoutAt:
        has_xy = (self.x is not None) != (self.y is not None)
        if has_xy:
            raise ValueError("readout.at braucht x und y zusammen")
        if self.x is not None and (self.comp is not None or self.port is not None):
            raise ValueError("readout.at: {x,y} oder {comp,port}, nicht beides")
        if (self.comp is None) != (self.port is None):
            raise ValueError("readout.at: comp und port müssen zusammen auftreten")
        return self

    @property
    def is_ref(self) -> bool:
        return self.comp is not None


class Readout(_Model):
    id: str
    at: ReadoutAt
    label: str
    value_key: str | None = None
    loop: str | None = None
    side: Literal["left", "right"] = "right"

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return check_id(v, "readout.id")

    @property
    def is_ref(self) -> bool:
        return self.at.is_ref


class Label(_Model):
    """Freie Annotation (Zonen-Text, Legende-Item).

    S3 (R-32): Entweder exakte `at`-Koordinate (Override, gewinnt immer)
    ODER `comp` (+ optional `port`) → Auto-Slot um die Host-Komponente
    (4 Richtungen, Preference up → right → down → left, 8 px Mindestabstand).
    Beides oder keines → Validierungsproblem `label-placement` (validate).
    """

    id: str
    at: Point | None = None
    comp: str | None = None
    port: str | None = None
    text: str
    anchor: TextAnchor = TextAnchor.START

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return check_id(v, "label.id")

    @field_validator("comp")
    @classmethod
    def _v_comp(cls, v: str | None) -> str | None:
        return check_id(v, "label.comp") if v is not None else None

    @field_validator("port")
    @classmethod
    def _v_port(cls, v: str | None) -> str | None:
        if v is not None and not _PORT_RE.fullmatch(v):
            raise ValueError(f"label.port ungültig (ist: {v!r})")
        return v


class Schema(_Model):
    """Root-Modell: plantschema/v1 (YAML-Key `schema`)."""

    version: str = Field(alias="schema")
    canvas: Canvas
    components: list[Component] = Field(default_factory=list)
    pipes: list[Pipe] = Field(default_factory=list)
    groups: list[Group] = Field(default_factory=list)
    readouts: list[Readout] = Field(default_factory=list)
    labels: list[Label] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def _v_version(cls, v: str) -> str:
        if v != "plantschema/v1":
            raise ValueError(f"version muss 'plantschema/v1' sein (ist: {v!r})")
        return v

    @property
    def component_ids(self) -> set[str]:
        return {c.id for c in self.components}
