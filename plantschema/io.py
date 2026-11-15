"""YAML-Lade-Stufe der Pipeline (parse): Datei → Pydantic-Schema.

Fehler → `SchemaError` mit Feldpfad + bestmöglicher YAML-Zeilenreferenz
(ableitbar aus `loc` bei list-Items: Top-Level-Key + Index).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .model import Schema, SchemaError

__all__ = ["SchemaLoadError", "load_schema", "load_schema_text"]


class SchemaLoadError(SchemaError):
    """SchemaError-Unterklasser für Lade-IO (CLI-Mapping: Exit 4)."""


def _top_level_key_map(text: str) -> dict[str, int]:
    """Zeilennummern (1-basiert) der Top-Level-Mapping-Keys im YAML-Text."""
    out: dict[str, int] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line[:1].isspace() or line.lstrip().startswith("#"):
            continue
        if ":" in line and line[:1] not in ("-",):
            key = line.split(":", 1)[0].strip().strip("'\"")
            out.setdefault(key, lineno)
    return out


def _line_from_loc(data: Any, loc: tuple[Any, ...], text: str) -> int | None:
    """YAML-Zeile für einen Pydantic-`loc`-Pfad (bestmögliche Ableitung)."""
    if not loc:
        return None
    key_map = _top_level_key_map(text)
    first = loc[0]
    if isinstance(first, str) and first in key_map:
        if len(loc) == 1:
            return key_map[first]
        # list-Index: Zeile des Items = Key-Zeile + Offset der list-Elemente
        if isinstance(data, dict) and first in data:
            sub = data[first]
            if isinstance(sub, list) and isinstance(loc[1], int):
                idx = loc[1]
                if 0 <= idx < len(sub):
                    base = key_map[first]
                    # Anzahl Zeilen bis zum Item (crude: je Item ~1 Zeile ist
                    # zu grob; stattdessen: Schlüsselzeile des Items scannen).
                    return _find_item_line(text, base, idx)
        return key_map[first]
    return None


def _find_item_line(text: str, list_start: int, index: int) -> int:
    """Zeile (1-basiert) des `index`-ten List-Items unter dem Key auf
    `list_start` (1-basiert)."""
    lines = text.splitlines()
    key_line = lines[list_start - 1]
    key_indent = len(key_line) - len(key_line.lstrip())
    seen = 0
    for offset in range(list_start, len(lines)):  # 0-basiert, Zeile NACH dem Key
        line = lines[offset]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= key_indent:
            break  # Dedent → Liste beendet
        stripped = line.lstrip()
        if stripped.startswith("- ") or stripped == "-":
            if seen == index:
                return offset + 1  # 1-basiert
            seen += 1
    return list_start


def _describe_exc(exc: ValidationError) -> list[str]:
    """Einzeilige Meldungen je Fehler (ohne Feldpfad — der steht in
    `SchemaError.path`; `value_error`-Felder tragen die echte Meldung in
    `ctx.error` (Pydantic ≥ 2.14: bare Exception; ältere:
    `PydanticErrorWrapper`-Kette → hier abgewickelt))."""
    out: list[str] = []
    for err in exc.errors():
        msg: str | None = None
        ctx: Any = err.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            value: Any = ctx["error"]
            while hasattr(value, "value") and not isinstance(value, Exception):
                value = value.value
            if isinstance(value, Exception) and value.args:
                msg = str(value.args[0])
        if msg is None:
            msg = err.get("msg", "")
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
        out.append(msg)
    return out


def load_schema_text(text: str) -> Schema:
    """YAML-Text → validiertes Schema.

    `SchemaLoadError` bei: ungültigem YAML (Zeile aus der YAML-Fehlermeldung)
    oder leerem/strukturellem Dokument. `SchemaError` bei Pydantic-
    Validierung (Zeile aus `loc`-Ableitung, wo möglich).
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        line: int | None = None
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        raise SchemaLoadError(
            f"ungültiges YAML: {str(exc).splitlines()[0]}", line=line
        ) from exc
    if data is None:
        raise SchemaLoadError("leere YAML-Datei (kein Dokument)", line=1)
    if not isinstance(data, dict):
        raise SchemaLoadError(
            f"Top-Level muss ein Mapping sein (ist: {type(data).__name__})",
            line=1,
        )
    try:
        return Schema.model_validate(data)
    except ValidationError as exc:
        lines = _describe_exc(exc)
        # Zeile nur für den ersten Fehler (CLI-Kanon: je Problem eine Zeile)
        line = _line_from_loc(data, tuple(exc.errors()[0].get("loc", ())), text)
        joined = "; ".join(lines)
        path = ".".join(str(p) for p in exc.errors()[0].get("loc", ())) or "(root)"
        raise SchemaError(joined, path=path, line=line) from exc
    except TypeError as exc:
        raise SchemaError(f"ungültige Datentypen: {exc}") from exc


def load_schema(path: str | Path) -> Schema:
    """YAML-Datei laden + validieren. Fehlende/unlesbare Datei →
    `SchemaLoadError` (CLI-Exit 4), ungültiges YAML → `SchemaError` (Exit 2)."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaLoadError(
            f"Datei nicht lesbar: {p} ({exc.strerror or exc})", path=str(p)
        ) from exc
    return load_schema_text(text)
